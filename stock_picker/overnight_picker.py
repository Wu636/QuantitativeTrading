"""
尾盘一夜持股法选股引擎 — 14:30 后精选次日高概率盈利标的

支持两种模式：
  - attack (强势隔夜): 尾盘放量上涨 → 次日惯性冲高
  - bargain (跌幅捡筹): 尾盘跌幅企稳 → 次日修复反弹
"""
import math
import pandas as pd
import numpy as np
from .picker import StockPicker
from .filters import StockFilter


OVERNIGHT_CONFIGS = {
    "attack": {
        "label": "🔥 强势隔夜",
        "desc": "尾盘量价齐升，次日惯性冲高",
        "change_pct_min": 2.0,
        "change_pct_max": 7.0,
        "min_volume_ratio": 1.0,
        "min_turnover": 3.0,
        "max_turnover": 10.0,
        "min_market_cap": 50e8,
        "max_market_cap": 300e8,
        "min_pe": 0,
        "max_pe": 60,
    },
    "bargain": {
        "label": "💎 跌幅捡筹",
        "desc": "尾盘超跌但基本面扎实，次日修复反弹",
        "change_pct_min": -5.0,
        "change_pct_max": -1.0,
        "min_volume_ratio": 0.8,
        "min_turnover": 1.0,
        "max_turnover": 8.0,
        "min_market_cap": 80e8,
        "max_market_cap": 1000e8,
        "min_pe": 0,
        "max_pe": 30,
    },
}


class OvernightPicker:
    """尾盘一夜法选股器"""

    def __init__(self):
        self.picker = StockPicker()

    def run(self, mode: str = "attack", top_n: int = 20, snapshot_df=None) -> dict:
        """
        运行尾盘选股

        Parameters
        ----------
        mode : str
            "attack" 强势隔夜 | "bargain" 跌幅捡筹
        top_n : int
            返回前 N 只
        snapshot_df : DataFrame, optional
            预取的全市场快照，传入则跳过抓取
        """
        config = OVERNIGHT_CONFIGS.get(mode, OVERNIGHT_CONFIGS["attack"])
        print(f"\n🌙 尾盘一夜法选股 [{config['label']}] 启动...")

        # 1. 获取全市场快照（支持外部传入）
        if snapshot_df is not None:
            df = snapshot_df.copy()
        else:
            df = self.picker.fetch_market_snapshot()
        total = len(df)

        # 2. 基础过滤
        f = StockFilter
        df = f.filter_st(df)
        df = f.filter_new_stock(df)

        # 排除涨停跌停
        if "涨跌幅" in df.columns:
            df = df[(df["涨跌幅"].abs() < 9.5) | df["涨跌幅"].isna()]

        # 排除停牌
        df = df[df["最新价"].notna() & (df["最新价"] > 0)]

        # 3. 条件筛选
        # 涨跌幅范围
        if "涨跌幅" in df.columns:
            df = df[
                (df["涨跌幅"] >= config["change_pct_min"])
                & (df["涨跌幅"] <= config["change_pct_max"])
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

        # 流通市值
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

        # 4. 打分
        df = self._score(df, mode)

        # 5. 取 Top N
        result = df.head(top_n).copy()

        stocks = []
        for _, row in result.iterrows():
            def _s(val, default=0):
                v = float(val) if val is not None else default
                return default if math.isnan(v) else round(v, 2)
            stocks.append({
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "price": _s(row.get("最新价")),
                "change_pct": _s(row.get("涨跌幅")),
                "volume_ratio": _s(row.get("量比")),
                "turnover": _s(row.get("换手率")),
                "market_cap": _s(row.get("流通市值", 0) / 1e8 if row.get("流通市值") else 0, 0),
                "pe": _s(row.get("市盈率-动态"), 0),
                "amplitude": _s(row.get("振幅")),
                "score": _s(row.get("overnight_score")),
            })

        return {
            "mode": mode,
            "config": {"label": config["label"], "desc": config["desc"]},
            "total_scanned": total,
            "total_matched": len(df),
            "stocks": stocks,
        }

    def _score(self, df: pd.DataFrame, mode: str) -> pd.DataFrame:
        """尾盘综合打分"""
        df = df.copy()
        score = pd.Series(0.0, index=df.index)

        change_pct = df["涨跌幅"].fillna(0) if "涨跌幅" in df.columns else 0
        volume_ratio = df["量比"].fillna(1) if "量比" in df.columns else 1
        turnover = df["换手率"].fillna(1) if "换手率" in df.columns else 1

        if mode == "attack":
            # 强势：涨幅适中最优（3-5%比2%和7%好），量价配合
            score += np.clip(change_pct * 8, 0, 40)       # 涨幅 → 40 分
            score += np.clip(volume_ratio * 10, 0, 30)     # 量比 → 30 分
            score += np.clip(turnover * 2, 0, 15)          # 换手 → 15 分
            # 振幅小 → 走势更稳健（不是暴涨暴跌型）
            if "振幅" in df.columns:
                amp = df["振幅"].fillna(5)
                score += np.clip((10 - amp) * 2, 0, 15)   # 振幅低 → 15 分
        else:
            # 抄底：跌幅适中 + 低 PE + 有承接
            score += np.clip(-change_pct * 8, 0, 35)      # 跌幅 → 35 分
            score += np.clip(volume_ratio * 8, 0, 20)      # 有承接 → 20 分
            # PE 低 → 安全边际
            if "市盈率-动态" in df.columns:
                pe = df["市盈率-动态"].fillna(20)
                score += np.clip((30 - pe) * 0.8, 0, 20)  # PE低 → 20 分
            # 市值大 → 更抗跌，反弹确定性高
            if "流通市值" in df.columns:
                cap = df["流通市值"].fillna(100e8) / 1e8
                score += np.clip(cap * 0.03, 0, 10)       # 大市值加分 → 10 分
            score += np.clip(turnover * 2, 0, 15)

        df["overnight_score"] = score
        df = df.sort_values("overnight_score", ascending=False)
        return df
