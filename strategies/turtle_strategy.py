"""
海龟交易策略（Turtle Trading Strategy）

经典趋势跟踪策略，由 Richard Dennis 和 William Eckhardt 提出。

核心规则：
1. 入场：价格突破 20 日 Donchian 通道上沿（20日最高价）→ 买入
2. 出场：价格跌破 10 日 Donchian 通道下沿（10日最低价）→ 卖出
3. 止损：入场价回落 2 × ATR → 止损卖出
4. 仓位：使用 ATR 控制风险（本版简化为全仓进出）

Donchian 通道：
- 上沿 = 过去 N 日最高价中的最大值
- 下沿 = 过去 N 日最低价中的最小值

ATR（Average True Range）：
- TR = max(H-L, |H-C_prev|, |L-C_prev|)
- ATR = TR 的 N 日简单移动平均
"""

import pandas as pd
import numpy as np
from .base import StrategyBase


class TurtleStrategy(StrategyBase):
    """海龟交易策略"""

    name = "海龟策略"
    description = "Donchian通道突破+ATR止损"

    def __init__(
        self,
        entry_window: int = 20,
        exit_window: int = 10,
        atr_period: int = 20,
        atr_stop_multiplier: float = 2.0,
    ):
        """
        Parameters
        ----------
        entry_window : int
            入场通道周期（默认 20 日 Donchian 上沿）
        exit_window : int
            出场通道周期（默认 10 日 Donchian 下沿）
        atr_period : int
            ATR 计算周期
        atr_stop_multiplier : float
            止损倍数（入场价 - N × ATR）
        """
        super().__init__(
            entry_window=entry_window,
            exit_window=exit_window,
            atr_period=atr_period,
            atr_stop_multiplier=atr_stop_multiplier,
        )
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.atr_period = atr_period
        self.atr_stop_multiplier = atr_stop_multiplier

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals["close"] = data["close"]

        # ===== 计算 Donchian 通道 =====
        signals["donchian_upper"] = data["high"].rolling(self.entry_window).max()
        signals["donchian_lower"] = data["low"].rolling(self.exit_window).min()

        # ===== 计算 ATR =====
        high = data["high"]
        low = data["low"]
        prev_close = data["close"].shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        signals["atr"] = tr.rolling(self.atr_period).mean()

        # 绘图兼容
        signals["short_ma"] = signals["donchian_upper"]
        signals["long_ma"] = signals["donchian_lower"]

        # 跳过 warmup
        warmup = max(self.entry_window, self.atr_period) + 2
        signals = signals.iloc[warmup:].copy()

        # ===== 逐行生成信号 =====
        signal_list = []
        in_position = False
        entry_price = 0.0
        stop_price = 0.0

        for i in range(len(signals)):
            signal = 0
            row = signals.iloc[i]
            price = row["close"]
            atr = row["atr"]

            if not in_position:
                # ---- 买入条件：价格突破 Donchian 上沿 ----
                if i >= 1:
                    prev_close = signals.iloc[i - 1]["close"]
                    # 今天收盘突破上沿，且昨天没有突破（确认突破）
                    if price > row["donchian_upper"] and prev_close <= signals.iloc[i - 1]["donchian_upper"]:
                        signal = 1
                        in_position = True
                        entry_price = price
                        stop_price = price - self.atr_stop_multiplier * atr
            else:
                # ---- 卖出条件 ----
                # 条件 A: 价格跌破 Donchian 下沿（趋势结束）
                exit_channel = price < row["donchian_lower"]

                # 条件 B: ATR 止损
                hit_stop = price <= stop_price

                if exit_channel or hit_stop:
                    signal = -1
                    in_position = False

            signal_list.append(signal)

        signals["signal"] = signal_list
        signals["signal"] = signals["signal"].astype(int)

        buy_count = (signals["signal"] == 1).sum()
        sell_count = (signals["signal"] == -1).sum()
        print(f"[{self.name}] 入场窗口={self.entry_window}, 出场窗口={self.exit_window}, "
              f"ATR周期={self.atr_period}, 止损倍数={self.atr_stop_multiplier}")
        print(f"  买入信号: {buy_count} 次, 卖出信号: {sell_count} 次")

        return signals
