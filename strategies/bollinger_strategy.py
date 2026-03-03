"""
布林带均值回归策略

布林带（Bollinger Bands）由三条线组成：
- 中轨 = N日移动平均线（默认20日）
- 上轨 = 中轨 + K倍标准差（默认2倍）
- 下轨 = 中轨 - K倍标准差

核心思想：价格总会回归到均值附近
- 价格触及下轨 → 超卖，考虑买入
- 价格触及上轨 → 超买，考虑卖出

改进：
- 结合 %B 指标（价格在布林带中的相对位置）
- 结合带宽（Bandwidth）判断波动性
- RSI辅助确认超买超卖
- 缩口后扩口 → 趋势启动信号
"""

import pandas as pd
import numpy as np
from .base import StrategyBase


class BollingerStrategy(StrategyBase):
    """布林带均值回归策略"""

    name = "布林带策略"
    description = "布林带超买超卖+RSI确认"

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 35,
        rsi_overbought: float = 65,
        stop_loss: float = -0.05,
    ):
        super().__init__(
            bb_period=bb_period,
            bb_std=bb_std,
            rsi_period=rsi_period,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            stop_loss=stop_loss,
        )
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.stop_loss = stop_loss

    def _calc_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """计算RSI指标"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals["close"] = data["close"]

        # ===== 计算布林带 =====
        signals["bb_mid"] = data["close"].rolling(self.bb_period).mean()
        bb_std = data["close"].rolling(self.bb_period).std()
        signals["bb_upper"] = signals["bb_mid"] + self.bb_std * bb_std
        signals["bb_lower"] = signals["bb_mid"] - self.bb_std * bb_std

        # %B 指标：价格在布林带中的相对位置 (0=下轨, 1=上轨)
        signals["pct_b"] = (data["close"] - signals["bb_lower"]) / (
            signals["bb_upper"] - signals["bb_lower"]
        )

        # 带宽
        signals["bandwidth"] = (signals["bb_upper"] - signals["bb_lower"]) / signals["bb_mid"]

        # RSI
        signals["rsi"] = self._calc_rsi(data["close"], self.rsi_period)

        # 用于绘图兼容（绘图模块会读 short_ma, long_ma）
        signals["short_ma"] = signals["bb_upper"]
        signals["long_ma"] = signals["bb_lower"]

        # 跳过warmup
        warmup = max(self.bb_period, self.rsi_period) + 5
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
                # ---- 买入条件 ----
                # 条件1: 价格触及或跌破布林带下轨（%B < 0.05）
                touch_lower = row["pct_b"] < 0.05
                # 条件2: RSI处于超卖区间
                rsi_oversold = row["rsi"] < self.rsi_oversold
                # 条件3: 价格开始回升（比昨天收盘价高 - 确认反弹）
                if i >= 1:
                    prev = signals.iloc[i - 1]
                    bouncing = price > prev["close"]
                else:
                    bouncing = False

                # 触及下轨 + RSI超卖 + 价格反弹
                if touch_lower and rsi_oversold and bouncing:
                    signal = 1
                    in_position = True
                    buy_price = price

            else:
                # ---- 卖出条件 ----
                pnl = (price - buy_price) / buy_price

                # 条件A: 价格触及布林带上轨（%B > 0.95）
                touch_upper = row["pct_b"] > 0.95
                # 条件B: RSI超买
                rsi_overbought = row["rsi"] > self.rsi_overbought
                # 条件C: 止损
                hit_stop = pnl <= self.stop_loss
                # 条件D: 价格回到中轨且RSI中性偏高（保守止盈）
                back_to_mid = price > row["bb_mid"] and row["rsi"] > 55

                if (touch_upper and rsi_overbought) or hit_stop or (back_to_mid and pnl > 0.03):
                    signal = -1
                    in_position = False

            signal_list.append(signal)

        signals["signal"] = signal_list
        signals["signal"] = signals["signal"].astype(int)

        buy_count = (signals["signal"] == 1).sum()
        sell_count = (signals["signal"] == -1).sum()
        print(f"[{self.name}] 周期={self.bb_period}, 标准差={self.bb_std}, RSI={self.rsi_period}")
        print(f"  RSI超卖<{self.rsi_oversold}, RSI超买>{self.rsi_overbought}, 止损{self.stop_loss:.0%}")
        print(f"  买入信号: {buy_count} 次, 卖出信号: {sell_count} 次")

        return signals
