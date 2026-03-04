"""
盘前竞价选股引擎 — 9:25 后基于开盘数据精选标的

支持两种模式：
  - attack (攻势追强): 高开 + 放量 → 追强势股
  - bargain (低吸抄底): 低开 + 有承接 → 超跌反弹
"""
import math
import pandas as pd
import numpy as np
from .picker import StockPicker
from .filters import StockFilter


# 两种模式的筛选参数
AUCTION_CONFIGS = {
    "attack": {
        "label": "🔥 攻势追强",
        "desc": "高开放量抢筹，追击竞价强势股",
        "open_pct_min": 1.0,
        "open_pct_max": 7.0,
        "min_volume_ratio": 2.0,
        "min_turnover": 1.0,
        "max_turnover": 10.0,
        "min_market_cap": 30e8,
        "max_market_cap": 500e8,
        "min_pe": 0,
        "max_pe": 100,
    },
    "bargain": {
        "label": "💎 低吸抄底",
        "desc": "低开错杀有承接，捡均值回归筹码",
        "open_pct_min": -5.0,
        "open_pct_max": -1.0,
        "min_volume_ratio": 1.5,
        "min_turnover": 0.5,
        "max_turnover": 8.0,
        "min_market_cap": 50e8,
        "max_market_cap": 800e8,
        "min_pe": 0,
        "max_pe": 40,
    },
}


class AuctionPicker:
    """盘前竞价选股器"""

    def __init__(self):
        self.picker = StockPicker()

    def run(self, mode: str = "attack", top_n: int = 20, snapshot_df=None) -> dict:
        """
        运行竞价选股

        Parameters
        ----------
        mode : str
            "attack" 攻势追强 | "bargain" 低吸抄底
        top_n : int
            返回前 N 只
        snapshot_df : DataFrame, optional
            预取的全市场快照，传入则跳过抓取
        """
        config = AUCTION_CONFIGS.get(mode, AUCTION_CONFIGS["attack"])
        print(f"\n🔔 盘前竞价选股 [{config['label']}] 启动...")

        # 1. 获取全市场快照（支持外部传入）
        if snapshot_df is not None:
            df = snapshot_df.copy()
        else:
            df = self.picker.fetch_market_snapshot()
        total = len(df)

        # 2. 计算开盘涨跌幅 = (今开 - 昨收) / 昨收 * 100
        if "今开" in df.columns and "昨收" in df.columns:
            df["开盘涨跌幅"] = ((df["今开"] - df["昨收"]) / df["昨收"]) * 100
        else:
            return {"error": "数据缺少 今开/昨收 字段", "stocks": []}

        # 3. 基础过滤
        f = StockFilter
        df = f.filter_st(df)
        df = f.filter_new_stock(df)

        # 排除涨停跌停 (涨跌幅 >= 9.5% 或 <= -9.5%)
        if "涨跌幅" in df.columns:
            df = df[(df["涨跌幅"].abs() < 9.5) | df["涨跌幅"].isna()]

        # 排除停牌 (最新价为 0 或 NaN)
        df = df[df["最新价"].notna() & (df["最新价"] > 0)]

        # 4. 条件筛选
        # 开盘涨跌幅范围
        df = df[
            (df["开盘涨跌幅"] >= config["open_pct_min"])
            & (df["开盘涨跌幅"] <= config["open_pct_max"])
        ]

        # 量比
        if "量比" in df.columns:
            df = df[(df["量比"] >= config["min_volume_ratio"]) | df["量比"].isna()]

        # 换手率
        if "换手率" in df.columns:
            df = df[
                (df["换手率"] >= config["min_turnover"])
                & (df["换手率"] <= config["max_turnover"])
            ]

        # 市值
        if "流通市值" in df.columns:
            mask = df["流通市值"] >= config["min_market_cap"]
            if config["max_market_cap"]:
                mask = mask & (df["流通市值"] <= config["max_market_cap"])
            df = df[mask]

        # PE
        if "市盈率-动态" in df.columns and config["max_pe"]:
            df = df[
                (df["市盈率-动态"] > config["min_pe"])
                & (df["市盈率-动态"] <= config["max_pe"])
            ]

        print(f"  筛选后: {len(df)} 只 (从 {total} 只中)")

        if df.empty:
            return {
                "mode": mode,
                "config": config,
                "total_scanned": total,
                "stocks": [],
            }

        # 5. 打分
        df = self._score(df, mode)

        # 6. 取 Top N
        result = df.head(top_n).copy()

        # 格式化输出
        stocks = []
        for _, row in result.iterrows():
            def _s(val, default=0):
                v = float(val) if val is not None else default
                return default if math.isnan(v) else round(v, 2)
            stocks.append({
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "price": _s(row.get("最新价")),
                "open_pct": _s(row.get("开盘涨跌幅")),
                "change_pct": _s(row.get("涨跌幅")),
                "volume_ratio": _s(row.get("量比")),
                "turnover": _s(row.get("换手率")),
                "market_cap": _s(row.get("流通市值", 0) / 1e8 if row.get("流通市值") else 0, 0),
                "pe": _s(row.get("市盈率-动态"), 0),
                "score": _s(row.get("auction_score")),
            })

        return {
            "mode": mode,
            "config": {"label": config["label"], "desc": config["desc"]},
            "total_scanned": total,
            "total_matched": len(df),
            "stocks": stocks,
        }

    def _score(self, df: pd.DataFrame, mode: str) -> pd.DataFrame:
        """竞价综合打分"""
        df = df.copy()
        score = pd.Series(0.0, index=df.index)

        open_pct = df["开盘涨跌幅"].fillna(0)
        volume_ratio = df["量比"].fillna(1) if "量比" in df.columns else 1
        turnover = df["换手率"].fillna(1) if "换手率" in df.columns else 1

        if mode == "attack":
            # 追强：高开幅度越大越好（但不要太高），量比越大越好
            score += np.clip(open_pct * 10, 0, 50)       # 高开 → 最多 50 分
            score += np.clip(volume_ratio * 8, 0, 30)     # 量比 → 最多 30 分
            score += np.clip(turnover * 2, 0, 20)         # 换手 → 最多 20 分
        else:
            # 抄底：低开幅度适中（不要太深），量比表示有承接
            score += np.clip(-open_pct * 8, 0, 40)        # 低开程度 → 最多 40 分
            score += np.clip(volume_ratio * 10, 0, 30)    # 有承接量 → 最多 30 分
            # PE 偏低加分（安全边际）
            if "市盈率-动态" in df.columns:
                pe = df["市盈率-动态"].fillna(30)
                score += np.clip((40 - pe) * 0.5, 0, 15)  # PE低 → 最多 15 分
            score += np.clip(turnover * 2, 0, 15)

        df["auction_score"] = score
        df = df.sort_values("auction_score", ascending=False)
        return df
