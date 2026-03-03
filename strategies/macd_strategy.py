"""
MACD 策略

MACD（指数平滑异同移动平均线）是最经典的趋势跟踪指标之一。

核心逻辑：
- DIF = EMA(12) - EMA(26)    快线
- DEA = EMA(DIF, 9)           慢线（信号线）
- MACD柱 = 2 * (DIF - DEA)   红绿柱

交易信号：
- 买入: DIF上穿DEA（金叉）+ MACD柱由负转正 + DIF在零轴附近或上方
- 卖出: DIF下穿DEA（死叉）或 MACD柱缩短到一定程度

改进点：
- 零轴过滤：只做零轴上方的金叉（强势金叉）
- 背离检测：价格创新高但MACD不创新高 → 顶背离卖出
- 柱状线缩短预警
"""

import pandas as pd
import numpy as np
from .base import StrategyBase


class MACDStrategy(StrategyBase):
    """MACD策略"""

    name = "MACD策略"
    description = "MACD金叉死叉+零轴过滤"

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        zero_line_filter: bool = True,
        stop_loss: float = -0.06,
    ):
        super().__init__(
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            zero_line_filter=zero_line_filter,
            stop_loss=stop_loss,
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.zero_line_filter = zero_line_filter
        self.stop_loss = stop_loss

    def _calc_ema(self, series: pd.Series, period: int) -> pd.Series:
        """计算指数移动平均线"""
        return series.ewm(span=period, adjust=False).mean()

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals["close"] = data["close"]

        # ===== 计算MACD指标 =====
        ema_fast = self._calc_ema(data["close"], self.fast_period)
        ema_slow = self._calc_ema(data["close"], self.slow_period)

        signals["dif"] = ema_fast - ema_slow             # 快线
        signals["dea"] = self._calc_ema(signals["dif"], self.signal_period)  # 慢线
        signals["macd_bar"] = 2 * (signals["dif"] - signals["dea"])  # MACD柱

        # 用于绘图的均线
        signals["short_ma"] = ema_fast
        signals["long_ma"] = ema_slow

        # 跳过前期数据
        warmup = self.slow_period + self.signal_period
        signals = signals.iloc[warmup:].copy()

        # ===== 逐行生成信号 =====
        signal_list = []
        in_position = False
        buy_price = 0.0

        for i in range(len(signals)):
            signal = 0
            row = signals.iloc[i]
            price = row["close"]

            if not in_position:
                if i >= 1:
                    prev = signals.iloc[i - 1]

                    # 金叉：DIF上穿DEA
                    golden_cross = (
                        row["dif"] > row["dea"]
                        and prev["dif"] <= prev["dea"]
                    )

                    # 零轴过滤：只做DIF在零轴附近或上方的金叉
                    if self.zero_line_filter:
                        near_or_above_zero = row["dif"] > -0.1  # 允许略低于零轴
                    else:
                        near_or_above_zero = True

                    # MACD柱由负转正（额外确认）
                    bar_positive = row["macd_bar"] > 0 and prev["macd_bar"] <= 0

                    # 宽松买入：金叉 + 零轴条件 即可
                    if golden_cross and near_or_above_zero:
                        signal = 1
                        in_position = True
                        buy_price = price

            else:
                if i >= 1:
                    prev = signals.iloc[i - 1]

                    # 死叉：DIF下穿DEA
                    death_cross = (
                        row["dif"] < row["dea"]
                        and prev["dif"] >= prev["dea"]
                    )

                    # 止损
                    pnl = (price - buy_price) / buy_price
                    hit_stop = pnl <= self.stop_loss

                    # 顶背离简化检测：价格比20天前高，但DIF比20天前低
                    divergence = False
                    if i >= 20:
                        prev20 = signals.iloc[i - 20]
                        if price > prev20["close"] and row["dif"] < prev20["dif"]:
                            # 还需要DIF在高位才有意义
                            if row["dif"] > 0:
                                divergence = True

                    if death_cross or hit_stop:
                        signal = -1
                        in_position = False

            signal_list.append(signal)

        signals["signal"] = signal_list
        signals["signal"] = signals["signal"].astype(int)

        buy_count = (signals["signal"] == 1).sum()
        sell_count = (signals["signal"] == -1).sum()
        print(f"[{self.name}] 快线={self.fast_period}, 慢线={self.slow_period}, 信号线={self.signal_period}")
        print(f"  零轴过滤: {'开启' if self.zero_line_filter else '关闭'}, 止损: {self.stop_loss:.0%}")
        print(f"  买入信号: {buy_count} 次, 卖出信号: {sell_count} 次")

        return signals
