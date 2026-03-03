"""
双均线策略（Golden Cross / Death Cross）

策略逻辑：
- 短期均线上穿长期均线（金叉）→ 买入信号
- 短期均线下穿长期均线（死叉）→ 卖出信号

参数：
- short_window: 短期均线周期（默认5日）
- long_window: 长期均线周期（默认20日）
"""

import pandas as pd
import numpy as np
from .base import StrategyBase


class DualMAStrategy(StrategyBase):
    """双均线交叉策略"""

    name = "双均线策略"
    description = "短期均线上穿长期均线买入，下穿卖出"

    def __init__(self, short_window: int = 5, long_window: int = 20):
        super().__init__(short_window=short_window, long_window=long_window)
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成双均线交叉信号

        Parameters
        ----------
        data : pd.DataFrame
            必须包含 close 列

        Returns
        -------
        pd.DataFrame
            包含 signal, short_ma, long_ma 列
        """
        signals = pd.DataFrame(index=data.index)

        # 计算均线
        signals["short_ma"] = data["close"].rolling(window=self.short_window).mean()
        signals["long_ma"] = data["close"].rolling(window=self.long_window).mean()

        # 初始化信号为0
        signals["signal"] = 0

        # 计算金叉和死叉
        # 金叉：短期均线从下方穿越长期均线
        # 死叉：短期均线从上方穿越长期均线
        short_above = signals["short_ma"] > signals["long_ma"]

        # 使用 shift 比较前一天和当天的关系来判断交叉
        # 今天短均线在上方，昨天短均线在下方 → 金叉（买入）
        golden_cross = short_above & (~short_above.shift(1).fillna(False))
        # 今天短均线在下方，昨天短均线在上方 → 死叉（卖出）
        death_cross = (~short_above) & short_above.shift(1).fillna(False)

        signals.loc[golden_cross, "signal"] = 1   # 买入
        signals.loc[death_cross, "signal"] = -1   # 卖出

        # 去掉均线尚未形成的区间（前 long_window 天）
        signals.iloc[: self.long_window] = np.nan
        signals = signals.dropna()
        signals["signal"] = signals["signal"].astype(int)

        print(f"[{self.name}] 短期均线={self.short_window}日, 长期均线={self.long_window}日")
        print(f"  买入信号: {(signals['signal'] == 1).sum()} 次")
        print(f"  卖出信号: {(signals['signal'] == -1).sum()} 次")

        return signals
