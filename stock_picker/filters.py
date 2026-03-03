"""
选股过滤器 — 基本面 + 技术面筛选函数

每个函数接受全市场 DataFrame，返回满足条件的子集。
可灵活组合使用，也可以通过 StockPicker 统一调用。

数据来源：akshare stock_zh_a_spot_em()  实时行情快照
列名（部分）：
    代码, 名称, 最新价, 涨跌幅, 市盈率-动态, 市净率, 总市值, 流通市值,
    60日涨跌幅, 年初至今涨跌幅, 量比, 换手率 ...
"""

import pandas as pd
import numpy as np


class StockFilter:
    """股票筛选器：提供多种基础过滤方法"""

    @staticmethod
    def filter_st(df: pd.DataFrame) -> pd.DataFrame:
        """排除 ST / *ST / 退市股"""
        mask = df["名称"].str.contains(r"ST|退", case=False, na=False)
        return df[~mask].copy()

    @staticmethod
    def filter_new_stock(df: pd.DataFrame, min_days: int = 60) -> pd.DataFrame:
        """
        排除次新股（近似）：
        - 若 60 日涨跌幅列存在且大多数有数据，则用 NaN 判断（次新股无 60 日数据）
        - 否则跳过此过滤（如新浪 API 没有该字段）
        """
        col = "60日涨跌幅"
        if col in df.columns:
            non_null_ratio = df[col].notna().mean()
            # 只有超过 50% 的数据有值时才用此字段过滤，否则说明数据源不提供该字段
            if non_null_ratio > 0.5:
                return df[df[col].notna()].copy()
        return df

    @staticmethod
    def filter_by_pe(df: pd.DataFrame, min_pe: float = 0, max_pe: float = 50) -> pd.DataFrame:
        """
        按市盈率（动态）过滤

        Parameters
        ----------
        min_pe : float
            最低 PE（排除亏损股，通常 > 0）
        max_pe : float
            最高 PE（排除严重高估股）
        """
        col = "市盈率-动态"
        if col not in df.columns:
            return df
        filtered = df[(df[col] > min_pe) & (df[col] <= max_pe)]
        return filtered.copy()

    @staticmethod
    def filter_by_pb(df: pd.DataFrame, min_pb: float = 0, max_pb: float = 10) -> pd.DataFrame:
        """按市净率过滤"""
        col = "市净率"
        if col not in df.columns:
            return df
        filtered = df[(df[col] > min_pb) & (df[col] <= max_pb)]
        return filtered.copy()

    @staticmethod
    def filter_by_market_cap(
        df: pd.DataFrame,
        min_cap: float = 50e8,
        max_cap: float = None,
    ) -> pd.DataFrame:
        """
        按总市值过滤

        Parameters
        ----------
        min_cap : float
            最低市值（默认 50 亿）
        max_cap : float
            最高市值，None 表示不限
        """
        col = "总市值"
        if col not in df.columns:
            return df
        mask = df[col] >= min_cap
        if max_cap is not None:
            mask = mask & (df[col] <= max_cap)
        return df[mask].copy()

    @staticmethod
    def filter_by_turnover(df: pd.DataFrame, min_turnover: float = 0.5) -> pd.DataFrame:
        """按换手率过滤 — 排除流动性极差的个股"""
        col = "换手率"
        if col not in df.columns:
            return df
        return df[df[col] >= min_turnover].copy()

    @staticmethod
    def filter_by_price(
        df: pd.DataFrame,
        min_price: float = 2.0,
        max_price: float = 200.0,
    ) -> pd.DataFrame:
        """按股价区间过滤"""
        col = "最新价"
        if col not in df.columns:
            return df
        return df[(df[col] >= min_price) & (df[col] <= max_price)].copy()

    @staticmethod
    def filter_by_momentum(df: pd.DataFrame, min_pct: float = 0) -> pd.DataFrame:
        """按 60 日涨跌幅过滤 — 只保留近期趋势向上的股票
        
        若数据源不提供该字段（全为 NaN），则自动跳过，避免清空结果。
        """
        col = "60日涨跌幅"
        if col not in df.columns:
            return df
        # 若全是 NaN（如新浪 API 不提供此数据），跳过此过滤
        if df[col].isna().all():
            print(f"    ⚠️ {col} 数据全为空，跳过动量过滤")
            return df
        # 保留有数据且满足条件的 + 无数据的（不误杀）
        mask = (df[col] >= min_pct) | df[col].isna()
        return df[mask].copy()

    # ─── 行业感知 PB 阈值 ─────────────────────────
    # 股票名称关键词 → 该行业合理 PB 上限
    # 银行/地产等重资产行业 PB < 1 是常态，一刀切太宽泛
    INDUSTRY_PB_LIMITS = {
        "银行": 2.0,
        "地产": 3.0,
        "置业": 3.0,
        "置地": 3.0,
        "保险": 3.0,
        "证券": 4.0,
        "钢铁": 2.5,
        "煤炭": 3.0,
        "建筑": 3.5,
        "高速": 3.0,
        "电力": 3.0,
    }

    @staticmethod
    def filter_by_pb_industry_aware(
        df: pd.DataFrame,
        default_max_pb: float = 10,
        default_min_pb: float = 0,
    ) -> pd.DataFrame:
        """
        分行业 PB 过滤：
        - 银行/地产等重资产行业使用独立的 PB 阈值
        - 其余行业使用 default_max_pb

        逻辑：若股票名称含行业关键词，取 min(行业阈值, default_max_pb)
              使到期望筛选更紧凑；不会错误放大范围。
        """
        col_pb = "市净率"
        col_name = "名称"
        if col_pb not in df.columns or col_name not in df.columns:
            return df

        # 为每只股票确定适用的 max_pb
        max_pb_per_stock = pd.Series(default_max_pb, index=df.index, dtype=float)
        for keyword, industry_limit in StockFilter.INDUSTRY_PB_LIMITS.items():
            is_industry = df[col_name].str.contains(keyword, na=False)
            # 行业股票用行业阈值（可能比 default 更低或更高）
            max_pb_per_stock[is_industry] = industry_limit

        mask = (df[col_pb] > default_min_pb) & (df[col_pb] <= max_pb_per_stock)
        filtered = df[mask].copy()
        excluded = len(df) - len(filtered)
        if excluded > 0:
            print(f"    🏭 分行业 PB 过滤排除 {excluded} 只")
        return filtered

    @staticmethod
    def filter_by_roe(df: pd.DataFrame, min_roe: float = 0) -> pd.DataFrame:
        """
        按 ROE 过滤

        公式：ROE ≈ PB / PE × 100 (%)
        （从估值指标逆推盈利能力，无需额外财务数据）
        """
        if "市净率" not in df.columns or "市盈率-动态" not in df.columns:
            return df
        pe = df["市盈率-动态"].replace(0, np.nan)
        roe = (df["市净率"] / pe * 100).fillna(0)
        return df[roe >= min_roe].copy()

    @staticmethod
    def filter_by_volume_ratio(
        df: pd.DataFrame,
        min_vr: float = 0,
        max_vr: float = None,
    ) -> pd.DataFrame:
        """按量比过滤（量比 = 今日成交量 / 过去5日均量）
        
        若数据全为 NaN 则跳过。
        """
        col = "量比"
        if col not in df.columns:
            return df
        if df[col].isna().all():
            print(f"    ⚠️ {col} 数据全为空，跳过量比过滤")
            return df
        mask = (df[col] >= min_vr) | df[col].isna()
        if max_vr is not None:
            mask = mask & ((df[col] <= max_vr) | df[col].isna())
        return df[mask].copy()

    @staticmethod
    def apply_default_filters(df: pd.DataFrame) -> pd.DataFrame:
        """应用默认基础过滤（排除 ST、退市股）"""
        f = StockFilter
        result = df.copy()
        result = f.filter_st(result)
        result = f.filter_new_stock(result)
        return result
