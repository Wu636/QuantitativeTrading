"""
WebSocket 连接管理器 + 后台实时行情轮询

架构：
  MarketDataFeed (后台协程) ──▶ ConnectionManager ──▶ 所有 WebSocket 客户端

内存：只保留最新一份快照，每次新数据覆盖旧数据。
"""

import os
import json
import asyncio
import subprocess
import time as _time
from datetime import datetime, time
from fastapi import WebSocket

# ─── 工具函数 ──────────────────────────────────────

def _is_trading_hours() -> bool:
    """判断当前是否在A股交易时段"""
    now = datetime.now()
    weekday = now.weekday()
    if weekday >= 5:  # 周末
        return False
    t = now.time()
    morning = time(9, 15) <= t <= time(11, 31)
    afternoon = time(12, 58) <= t <= time(15, 1)
    return morning or afternoon


def _safe_float(val):
    if val is None or val == "" or val == "-":
        return None
    try:
        v = float(val)
        import math
        return None if math.isnan(v) else v
    except (ValueError, TypeError):
        return None


# ─── 连接管理器 ──────────────────────────────────────

class ConnectionManager:
    """管理所有 WebSocket 连接，支持广播"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"🔌 WebSocket 连接 +1，当前 {len(self.active_connections)} 个客户端")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"🔌 WebSocket 断开 -1，当前 {len(self.active_connections)} 个客户端")

    async def broadcast(self, message: dict):
        """向所有连接的客户端广播消息"""
        msg_text = json.dumps(message, ensure_ascii=False)
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_text(msg_text)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect(d)

    @property
    def has_clients(self) -> bool:
        return len(self.active_connections) > 0


# ─── 行情数据源 ──────────────────────────────────────

class MarketDataFeed:
    """后台定时拉取全市场行情快照，推送给所有客户端"""

    def __init__(self, manager: ConnectionManager, interval: int = 10):
        self.manager = manager
        self.interval = interval  # 秒
        self.latest_snapshot = None
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self):
        """启动后台任务"""
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            print(f"📡 行情推送服务已启动 (间隔 {self.interval}s)")

    def stop(self):
        """停止后台任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
            print("📡 行情推送服务已停止")

    async def _loop(self):
        """主循环"""
        while self._running:
            try:
                # 没 client 就休息
                if not self.manager.has_clients:
                    await asyncio.sleep(2)
                    continue

                # 非交易时段，低频心跳
                if not _is_trading_hours():
                    await self.manager.broadcast({
                        "type": "heartbeat",
                        "trading": False,
                        "message": "非交易时段",
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    })
                    await asyncio.sleep(30)
                    continue

                # 盘中：抓取 + 分析 + 推送
                result = await asyncio.to_thread(self._fetch_and_analyze)
                if result is not None:
                    self.latest_snapshot = result.get("summary")
                    await self.manager.broadcast(result)

                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ 行情轮询异常: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(self.interval)

    def _fetch_and_analyze(self) -> dict | None:
        """抓取快照 + 运行选股 + 统计市场概况 (同步)"""
        import pandas as pd
        from stock_picker.picker import StockPicker
        from stock_picker.auction_picker import AuctionPicker
        from stock_picker.overnight_picker import OvernightPicker

        # 1. 用 StockPicker 获取全市场 DataFrame（和手动点击选股一样的数据源）
        picker = StockPicker()
        df = picker.fetch_market_snapshot()
        if df.empty:
            return None

        total = len(df)
        ts = datetime.now().strftime("%H:%M:%S")

        # 2. 市场概况统计
        summary = self._compute_market_summary(df, total)

        # 3. 运行 4 种时机选股模式
        auction = AuctionPicker()
        overnight = OvernightPicker()
        timing = {
            "auction_attack": auction.run(mode="attack", top_n=20, snapshot_df=df),
            "auction_bargain": auction.run(mode="bargain", top_n=20, snapshot_df=df),
            "overnight_attack": overnight.run(mode="attack", top_n=20, snapshot_df=df),
            "overnight_bargain": overnight.run(mode="bargain", top_n=20, snapshot_df=df),
        }

        print(f"  📊 推送: {summary['up_count']}涨 {summary['down_count']}跌 | "
              f"竞价追强{len(timing['auction_attack']['stocks'])}只 "
              f"竞价抄底{len(timing['auction_bargain']['stocks'])}只 | "
              f"隔夜追强{len(timing['overnight_attack']['stocks'])}只 "
              f"隔夜抄底{len(timing['overnight_bargain']['stocks'])}只")

        return {
            "type": "realtime_update",
            "timestamp": ts,
            "summary": summary,
            "timing": timing,
        }

    def _compute_market_summary(self, df, total) -> dict:
        """从快照 DataFrame 计算市场概况"""
        up = df[df["涨跌幅"] > 0] if "涨跌幅" in df.columns else df.head(0)
        down = df[df["涨跌幅"] < 0] if "涨跌幅" in df.columns else df.head(0)
        flat = total - len(up) - len(down)

        avg_change = df["涨跌幅"].mean() if "涨跌幅" in df.columns else 0
        limit_up = len(df[df["涨跌幅"] >= 9.5]) if "涨跌幅" in df.columns else 0
        limit_down = len(df[df["涨跌幅"] <= -9.5]) if "涨跌幅" in df.columns else 0

        import math
        return {
            "total": total,
            "up_count": len(up),
            "down_count": len(down),
            "flat_count": flat,
            "avg_change": 0 if math.isnan(avg_change) else round(float(avg_change), 2),
            "limit_up": limit_up,
            "limit_down": limit_down,
        }

    def _fetch_snapshot(self) -> list | None:
        """使用新浪财经 API 获取全A股快照 (同步，在线程中运行)"""
        all_data = []
        page = 1
        page_size = 100

        while True:
            url = (
                f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                f"Market_Center.getHQNodeData?"
                f"page={page}&num={page_size}&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=page"
            )
            try:
                result = subprocess.run(
                    [
                        "curl", "-s", "-m", "10",
                        "--noproxy", "*",
                        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        "-H", "Referer: https://finance.sina.com.cn/",
                        url,
                    ],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    break
                items = json.loads(result.stdout)
                if not items:
                    break
                all_data.extend(items)
                if len(items) < page_size:
                    break
                page += 1
                _time.sleep(0.1)
            except Exception:
                break

        if not all_data:
            return None

        # 转换为前端友好的列表
        stocks = []
        for item in all_data:
            code = item.get("code", item.get("symbol", ""))
            if code.startswith(("sh", "sz")):
                code = code[2:]
            name = item.get("name", "")
            # 排除 ST / 退市
            if "ST" in name or "退" in name:
                continue

            stocks.append({
                "code": code,
                "name": name,
                "price": _safe_float(item.get("trade", item.get("price"))),
                "change_pct": _safe_float(item.get("changepercent")),
                "open": _safe_float(item.get("open")),
                "settlement": _safe_float(item.get("settlement")),  # 昨收
                "volume_ratio": _safe_float(item.get("volume_ratio")),
                "turnover": _safe_float(item.get("turnoverratio")),
                "pe": _safe_float(item.get("per")),
                "pb": _safe_float(item.get("pb")),
                "market_cap": (_safe_float(item.get("nmc", 0)) or 0) / 1e4,  # 万→亿
                "amount": _safe_float(item.get("amount")),
            })

        return stocks


# ─── 全局单例 ──────────────────────────────────────

manager = ConnectionManager()
data_feed = MarketDataFeed(manager, interval=10)
