"""
多因子综合策略

单一指标容易产生假信号，多因子策略通过"投票机制"提高信号可靠性。

使用的因子：
1. 趋势因子：价格 > MA60（大趋势向上）
2. 动量因子：MACD柱 > 0（中期动量向上）
3. 均线因子：MA10 > MA30（短期趋势向上）
4. 量能因子：成交量 > 5日均量（有资金进场）
5. 超卖因子：RSI从超卖区回升（反弹确认）

买入规则：至少满足N个因子（默认4个）
卖出规则：趋势因子转空 或 满足止损/止盈条件
"""

import pandas as pd
import numpy as np
from .base import StrategyBase


class MultiFactorStrategy(StrategyBase):
    """多因子综合策略"""

    name = "多因子策略"
    description = "趋势+动量+均线+量能+RSI多因子投票"

    def __init__(
        self,
        min_factors: int = 4,
        trend_ma: int = 60,
        fast_ma: int = 10,
        slow_ma: int = 30,
        rsi_period: int = 14,
        rsi_buy_threshold: float = 45,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        stop_loss: float = -0.06,
        take_profit: float = 0.15,
        trailing_stop: float = -0.04,
    ):
        super().__init__(
            min_factors=min_factors,
            trend_ma=trend_ma,
            fast_ma=fast_ma,
            slow_ma=slow_ma,
            rsi_period=rsi_period,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        self.min_factors = min_factors
        self.trend_ma = trend_ma
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.rsi_period = rsi_period
        self.rsi_buy_threshold = rsi_buy_threshold
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_stop = trailing_stop

    def _calc_rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals["close"] = data["close"]
        signals["volume"] = data["volume"]

        # ===== 计算所有因子指标 =====
        # 趋势因子
        signals["ma_trend"] = data["close"].rolling(self.trend_ma).mean()

        # 均线因子
        signals["ma_fast"] = data["close"].rolling(self.fast_ma).mean()
        signals["ma_slow"] = data["close"].rolling(self.slow_ma).mean()

        # MACD因子
        ema_fast = data["close"].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = data["close"].ewm(span=self.macd_slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=self.macd_signal, adjust=False).mean()
        signals["macd_bar"] = 2 * (dif - dea)

        # 量能因子
        signals["vol_ma5"] = data["volume"].rolling(5).mean()

        # RSI因子
        signals["rsi"] = self._calc_rsi(data["close"], self.rsi_period)

        # 绘图用
        signals["short_ma"] = signals["ma_fast"]
        signals["long_ma"] = signals["ma_slow"]

        # 跳过warmup
        warmup = max(self.trend_ma, self.macd_slow + self.macd_signal) + 5
        signals = signals.iloc[warmup:].copy()

        # ===== 计算每日因子得分 =====
        scores = pd.DataFrame(index=signals.index)
        scores["f_trend"] = (signals["close"] > signals["ma_trend"]).astype(int)
        scores["f_momentum"] = (signals["macd_bar"] > 0).astype(int)
        scores["f_ma_cross"] = (signals["ma_fast"] > signals["ma_slow"]).astype(int)
        scores["f_volume"] = (signals["volume"] > signals["vol_ma5"] * 1.1).astype(int)
        scores["f_rsi"] = (
            (signals["rsi"] > self.rsi_buy_threshold) & (signals["rsi"] < 70)
        ).astype(int)

        scores["total_score"] = scores.sum(axis=1)
        signals["factor_score"] = scores["total_score"]

        # ===== 逐行生成信号 =====
        signal_list = []
        in_position = False
        buy_price = 0.0
        max_price = 0.0

        for i in range(len(signals)):
            signal = 0
            row = signals.iloc[i]
            score = scores.iloc[i]
            price = row["close"]

            if not in_position:
                # 买入：因子得分 >= 阈值
                if score["total_score"] >= self.min_factors:
                    # 额外确认：今天的因子得分比昨天高（趋势在加强）
                    if i >= 1:
                        prev_score = scores.iloc[i - 1]["total_score"]
                        if score["total_score"] >= prev_score:
                            signal = 1
                            in_position = True
                            buy_price = price
                            max_price = price
            else:
                max_price = max(max_price, price)
                pnl = (price - buy_price) / buy_price
                drawdown = (price - max_price) / max_price

                # 卖出条件
                # A: 趋势反转（价格跌破趋势线 且 MACD转负）
                trend_reversal = (
                    price < row["ma_trend"] and row["macd_bar"] < 0
                )
                # B: 止损
                hit_stop = pnl <= self.stop_loss
                # C: 止盈
                hit_profit = pnl >= self.take_profit
                # D: 移动止盈
                hit_trailing = drawdown <= self.trailing_stop and pnl > 0.02
                # E: 因子大幅恶化（得分降到2以下）
                factor_weak = score["total_score"] <= 1

                if trend_reversal or hit_stop or hit_profit or hit_trailing or factor_weak:
                    signal = -1
                    in_position = False

            signal_list.append(signal)

        signals["signal"] = signal_list
        signals["signal"] = signals["signal"].astype(int)

        buy_count = (signals["signal"] == 1).sum()
        sell_count = (signals["signal"] == -1).sum()
        print(f"[{self.name}] 最低因子数={self.min_factors}/5")
        print(f"  因子: 趋势MA{self.trend_ma} | MACD({self.macd_fast},{self.macd_slow},{self.macd_signal}) "
              f"| 均线{self.fast_ma}/{self.slow_ma} | 量能 | RSI{self.rsi_period}")
        print(f"  止损{self.stop_loss:.0%}, 止盈{self.take_profit:.0%}, 移动止盈{self.trailing_stop:.0%}")
        print(f"  买入信号: {buy_count} 次, 卖出信号: {sell_count} 次")

        return signals
