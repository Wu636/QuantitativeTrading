"""
选股主流程 — StockPicker

使用方式：
    picker = StockPicker()
    result = picker.run(top_n=20)  # 使用默认筛选条件

    # 自定义筛选和权重：
    result = picker.run(
        filters={"max_pe": 30, "min_market_cap": 100e8},
        weights={"value": 0.4, "momentum": 0.3, "quality": 0.3},
        top_n=10,
    )
"""

import os
import pandas as pd
from .filters import StockFilter
from .scorer import FactorScorer


def _clear_proxy():
    """清除代理环境变量，避免国内 API 走代理连不上"""
    for key in ["http_proxy", "https_proxy", "all_proxy",
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        os.environ.pop(key, None)


def _safe_float(val):
    """安全地将值转换为 float，处理 None / 空字符串 / 非数值"""
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class StockPicker:
    """A股选股器"""

    def __init__(self):
        self.filter = StockFilter()
        self._raw_data = None

    def fetch_market_snapshot(self) -> pd.DataFrame:
        """
        获取全市场实时行情快照

        使用新浪财经 API 获取数据（而非东方财富 push2 API）。

        Returns
        -------
        pd.DataFrame
            全 A 股最新行情数据
        """
        import subprocess
        import json
        import time

        print("📡 正在获取全市场行情快照（新浪财经）...")

        all_data = []
        page = 1
        page_size = 100  # 新浪 API 每页最大 100 条

        while True:
            url = (
                f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                f"Market_Center.getHQNodeData?"
                f"page={page}&num={page_size}&sort=mktcap&asc=0&node=hs_a&symbol=&_s_r_a=page"
            )

            max_retries = 3
            items = None
            
            for attempt in range(max_retries):
                try:
                    result = subprocess.run(
                        [
                            "curl", "-s", "-m", "15",
                            "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                            "-H", "Referer: https://finance.sina.com.cn/",
                            url,
                        ],
                        capture_output=True, text=True, timeout=20,
                    )
                    
                    if result.returncode != 0 or not result.stdout.strip():
                        raise ConnectionError(f"curl failed: rc={result.returncode}")
    
                    # Sina may return blocked HTML
                    if "拒绝访问" in result.stdout:
                        raise ConnectionError("新浪财经 API 拒绝访问 (IP 限制)")

                    items = json.loads(result.stdout)
                    break # Success
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"  ⚠️ 第 {page} 页获取失败 (尝试 {attempt+1}/{max_retries}): {e}，正在重试...")
                        time.sleep(1)
                    else:
                        print(f"  ❌ 第 {page} 页获取彻底失败: {e}")
                        items = None
            
            if items is None:
                if page == 1:
                    print("  ⚠️ 新浪财经 API 拒绝访问或连接失败，将返回空数据。")
                    return pd.DataFrame()
                print(f"  ⚠️ 终止抓取，使用已获取的 {len(all_data)} 条数据")
                break
                
            if not items:
                break

            all_data.extend(items)
            print(f"  📥 第 {page} 页，已获取 {len(all_data)} 条...")

            if len(items) < page_size:
                break  # 最后一页

            page += 1
            time.sleep(0.3)

        if not all_data:
            return pd.DataFrame()

        print(f"  获取到 {len(all_data)} 条原始数据，正在解析...")

        # 新浪 API 字段 → 统一中文列名
        rows = []
        for item in all_data:
            code = item.get("code", item.get("symbol", ""))
            # 去掉 sh/sz 前缀
            if code.startswith(("sh", "sz")):
                code = code[2:]

            rows.append({
                "代码": code,
                "名称": item.get("name", ""),
                "最新价": _safe_float(item.get("trade", item.get("price"))),
                "涨跌幅": _safe_float(item.get("changepercent")),
                "涨跌额": _safe_float(item.get("pricechange")),
                "成交量": _safe_float(item.get("volume")),
                "成交额": _safe_float(item.get("amount")),
                "振幅": _safe_float(item.get("amplitude")),
                "最高": _safe_float(item.get("high")),
                "最低": _safe_float(item.get("low")),
                "今开": _safe_float(item.get("open")),
                "昨收": _safe_float(item.get("settlement")),
                "量比": _safe_float(item.get("volume_ratio")),
                "换手率": _safe_float(item.get("turnoverratio")),
                "市盈率-动态": _safe_float(item.get("per")),
                "市净率": _safe_float(item.get("pb")),
                "总市值": _safe_float(item.get("mktcap", 0)) * 10000,  # 新浪单位是万元
                "流通市值": _safe_float(item.get("nmc", 0)) * 10000,
                "60日涨跌幅": None,  # 新浪 API 不提供，后续可计算
                "年初至今涨跌幅": None,
            })

        df = pd.DataFrame(rows)

        # 确保数值列是数值类型
        numeric_cols = [
            "最新价", "涨跌幅", "涨跌额", "成交量", "成交额",
            "振幅", "最高", "最低", "今开", "昨收",
            "量比", "换手率", "市盈率-动态", "市净率",
            "总市值", "流通市值",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        self._raw_data = df
        print(f"✅ 获取到 {len(df)} 只股票数据")
        return df

    def run(
        self,
        filters: dict = None,
        weights: dict = None,
        top_n: int = 20,
        data: pd.DataFrame = None,
    ) -> pd.DataFrame:
        """
        运行选股流程：获取数据 → 筛选过滤 → 多因子打分 → 返回 Top N

        Parameters
        ----------
        filters : dict
            筛选参数，支持的键：
            - max_pe: 最大市盈率（默认 50）
            - min_pe: 最小市盈率（默认 0）
            - max_pb: 最大市净率（默认 10）
            - min_market_cap: 最小市值（默认 30 亿）
            - max_market_cap: 最大市值（默认 None）
            - min_price: 最低股价（默认 2）
            - max_price: 最高股价（默认 500）
            - min_turnover: 最低换手率（默认 0.3）
            - min_momentum: 最低 60 日涨幅（默认 None）
        weights : dict
            因子权重（传给 FactorScorer）
        top_n : int
            返回前 N 只股票
        data : pd.DataFrame
            可选，直接传入数据而非重新获取

        Returns
        -------
        pd.DataFrame
            Top N 候选股票，包含各项因子分数
        """
        filters = filters or {}

        # ===== 1. 获取数据 =====
        if data is not None:
            df = data.copy()
        elif self._raw_data is not None:
            df = self._raw_data.copy()
        else:
            df = self.fetch_market_snapshot()

        total_stocks = len(df)

        # ===== 2. 基础过滤 =====
        print("\n🔍 Step 1: 基础过滤...")
        df = self.filter.filter_st(df)
        df = self.filter.filter_new_stock(df)
        print(f"  排除 ST/次新后: {len(df)} 只")

        # ===== 3. 条件过滤 =====
        print("🔍 Step 2: 条件筛选...")

        df = self.filter.filter_by_pe(
            df,
            min_pe=filters.get("min_pe", 0),
            max_pe=filters.get("max_pe", 50),
        )

        # 分行业智能 PB 过滤（银行/地产等用行业阈值，其余用 default_max_pb）
        use_industry_pb = filters.get("industry_pb_aware", False)
        if use_industry_pb:
            df = self.filter.filter_by_pb_industry_aware(
                df,
                default_max_pb=filters.get("max_pb", 10),
                default_min_pb=filters.get("min_pb", 0),
            )
        else:
            df = self.filter.filter_by_pb(
                df,
                max_pb=filters.get("max_pb", 10),
            )

        df = self.filter.filter_by_market_cap(
            df,
            min_cap=filters.get("min_market_cap", 30e8),
            max_cap=filters.get("max_market_cap"),
        )
        df = self.filter.filter_by_price(
            df,
            min_price=filters.get("min_price", 2.0),
            max_price=filters.get("max_price", 500.0),
        )
        df = self.filter.filter_by_turnover(
            df,
            min_turnover=filters.get("min_turnover", 0.3),
        )

        if "min_momentum" in filters and filters["min_momentum"] is not None:
            df = self.filter.filter_by_momentum(df, min_pct=filters["min_momentum"])

        # ROE 过滤（困境反转 / 量价背离策略需要）
        if filters.get("min_roe") is not None and filters["min_roe"] > 0:
            df = self.filter.filter_by_roe(df, min_roe=filters["min_roe"])

        # 量比过滤（缩量横盘 / 放量突破筛选）
        if filters.get("min_volume_ratio") is not None:
            df = self.filter.filter_by_volume_ratio(
                df,
                min_vr=filters.get("min_volume_ratio", 0),
                max_vr=filters.get("max_volume_ratio"),
            )

        print(f"  条件筛选后: {len(df)} 只 (从 {total_stocks} 只中筛选)")

        if df.empty:
            print("⚠️ 筛选后无符合条件的股票，请放宽条件")
            return pd.DataFrame()

        # ===== 4. 多因子打分 =====
        print("📊 Step 3: 多因子打分...")
        scorer = FactorScorer(weights=weights)
        scored = scorer.score(df)

        # ===== 5. 取 Top N =====
        result = scored.head(top_n).copy()
        result.index = range(1, len(result) + 1)
        result.index.name = "排名"

        # 选择展示列
        display_cols = [
            "代码", "名称", "最新价", "涨跌幅", "市盈率-动态", "市净率",
            "总市值", "换手率",
            "factor_value", "factor_momentum", "factor_quality",
            "factor_liquidity", "factor_size", "total_score",
        ]
        display_cols = [c for c in display_cols if c in result.columns]

        print(f"\n{'=' * 90}")
        print(f"  🏆 选股结果 Top {len(result)} (共筛选 {len(scored)} 只)")
        print(f"{'=' * 90}")
        print(result[display_cols].to_string())
        print(f"{'=' * 90}")

        return result


if __name__ == "__main__":
    picker = StockPicker()
    result = picker.run(
        filters={"max_pe": 30, "min_market_cap": 50e8},
        top_n=20,
    )
