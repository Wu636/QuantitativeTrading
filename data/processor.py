"""
数据处理模块 - 数据清洗、技术指标计算
"""

import pandas as pd
import numpy as np


class DataProcessor:
    """数据预处理器"""

    @staticmethod
    def add_moving_averages(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
        """
        添加移动平均线

        Parameters
        ----------
        df : pd.DataFrame
            包含 close 列的DataFrame
        windows : list[int]
            均线窗口列表，默认 [5, 10, 20, 60]
        """
        if windows is None:
            windows = [5, 10, 20, 60]

        df = df.copy()
        for w in windows:
            df[f"ma{w}"] = df["close"].rolling(window=w).mean()
        return df

    @staticmethod
    def add_volume_ma(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
        """添加成交量均线"""
        if windows is None:
            windows = [5, 20]

        df = df.copy()
        for w in windows:
            df[f"vol_ma{w}"] = df["volume"].rolling(window=w).mean()
        return df

    @staticmethod
    def add_pct_change(df: pd.DataFrame) -> pd.DataFrame:
        """添加日收益率列"""
        df = df.copy()
        if "pct_change" not in df.columns:
            df["pct_change"] = df["close"].pct_change() * 100
        return df

    @staticmethod
    def detect_limit_up(df: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
        """
        标记涨跌停板

        A股涨跌停规则：
        - 主板：±10%
        - 创业板(300xxx)、科创板(688xxx)：±20%
        - ST股：±5%（此处简化不做区分）
        """
        df = df.copy()
        daily_return = df["close"].pct_change()

        # 根据股票代码判断涨跌停阈值
        if symbol.startswith("300") or symbol.startswith("688"):
            limit_threshold = 0.195  # 创业板/科创板 ±20%
        else:
            limit_threshold = 0.095  # 主板 ±10%

        df["is_limit_up"] = daily_return >= limit_threshold
        df["is_limit_down"] = daily_return <= -limit_threshold

        return df

    @staticmethod
    def detect_suspension(df: pd.DataFrame) -> pd.DataFrame:
        """
        标记停牌日和复牌日
        
        - is_suspended: 当日停牌（成交量为0）
        - is_resume: 复牌日（前一日停牌，今日不停牌）
        
        注意：复牌日通常波动剧烈，策略可选择跳过。
        """
        df = df.copy()
        df["is_suspended"] = df["volume"] == 0
        # 复牌日 = 前一天停牌，今天不停牌
        df["is_resume"] = df["is_suspended"].shift(1).fillna(False) & ~df["is_suspended"]
        return df

    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗：去除空值、异常值"""
        df = df.copy()

        # 删除全空的行
        df = df.dropna(how="all")

        # 前向填充小量缺失值
        df = df.ffill()

        # 删除成交量为0的行（停牌日）
        if "volume" in df.columns:
            df = df[df["volume"] > 0]

        return df

    @staticmethod
    def prepare_backtest_data(
        df: pd.DataFrame,
        ma_windows: list[int] = None,
        symbol: str = "",
    ) -> pd.DataFrame:
        """
        准备回测数据：清洗 + 添加常用指标

        Parameters
        ----------
        df : pd.DataFrame
            原始行情数据
        ma_windows : list[int]
            需要计算的均线窗口
        symbol : str
            股票代码，用于判断涨跌停阈值
        """
        df = DataProcessor.clean_data(df)
        df = DataProcessor.add_pct_change(df)
        df = DataProcessor.add_moving_averages(df, ma_windows)
        df = DataProcessor.add_volume_ma(df)
        df = DataProcessor.detect_suspension(df)  # 新增：停牌检测
        df = DataProcessor.detect_limit_up(df, symbol)  # 增强：按板块判断涨跌停
        return df
