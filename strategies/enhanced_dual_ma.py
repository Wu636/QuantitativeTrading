"""
增强版双均线策略

相比基础双均线的改进：
1. 趋势过滤：加入60日均线判断大趋势，只做顺势交易
2. 量能确认：金叉时成交量必须放大（超过5日均量1.2倍）
3. 止损止盈：固定比例止损(-5%)，移动止盈（从最高点回落3%止盈）
4. 信号冷却：两次交易之间至少间隔N天，避免频繁交易
"""

import pandas as pd
import numpy as np
from .base import StrategyBase


class EnhancedDualMAStrategy(StrategyBase):
    """增强版双均线策略"""

    name = "增强双均线策略"
    description = "双均线+趋势过滤+量能确认+止损止盈"

    def __init__(
        self,
        short_window: int = 10,
        long_window: int = 30,
        trend_window: int = 60,
        volume_ratio: float = 1.2,
        stop_loss: float = -0.05,
        trailing_stop: float = -0.03,
        cooldown_days: int = 5,
    ):
        super().__init__(
            short_window=short_window,
            long_window=long_window,
            trend_window=trend_window,
            volume_ratio=volume_ratio,
            stop_loss=stop_loss,
            trailing_stop=trailing_stop,
            cooldown_days=cooldown_days,
        )
        self.short_window = short_window
        self.long_window = long_window
        self.trend_window = trend_window
        self.volume_ratio = volume_ratio
        self.stop_loss = stop_loss
        self.trailing_stop = trailing_stop
        self.cooldown_days = cooldown_days

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals["close"] = data["close"]

        # ===== 计算技术指标 =====
        signals["short_ma"] = data["close"].rolling(self.short_window).mean()
        signals["long_ma"] = data["close"].rolling(self.long_window).mean()
        signals["trend_ma"] = data["close"].rolling(self.trend_window).mean()
        signals["vol_ma5"] = data["volume"].rolling(5).mean()
        signals["volume"] = data["volume"]

        # 去掉指标未形成的区间
        signals = signals.dropna().copy()

        # ===== 逐行生成信号（需要追踪状态） =====
        signal_list = []
        in_position = False
        buy_price = 0.0
        max_price_since_buy = 0.0
        last_trade_idx = -999

        for i in range(len(signals)):
            signal = 0
            row = signals.iloc[i]
            price = row["close"]

            if not in_position:
                # ---- 买入条件 ----
                if i >= 1:
                    prev = signals.iloc[i - 1]
                    # 条件1: 金叉（短均线上穿长均线）
                    golden_cross = (
                        row["short_ma"] > row["long_ma"]
                        and prev["short_ma"] <= prev["long_ma"]
                    )
                    # 条件2: 趋势过滤（价格在60日均线上方 = 上升趋势）
                    trend_up = price > row["trend_ma"]
                    # 条件3: 量能确认（成交量 > 5日均量的1.2倍）
                    volume_confirm = row["volume"] > row["vol_ma5"] * self.volume_ratio
                    # 条件4: 冷却期（距离上次交易至少N天）
                    cooled = (i - last_trade_idx) >= self.cooldown_days

                    if golden_cross and trend_up and volume_confirm and cooled:
                        signal = 1
                        in_position = True
                        buy_price = price
                        max_price_since_buy = price
                        last_trade_idx = i
            else:
                # 更新持仓期间最高价
                max_price_since_buy = max(max_price_since_buy, price)

                # ---- 卖出条件（任一触发即卖） ----
                if i >= 1:
                    prev = signals.iloc[i - 1]

                    # 条件A: 死叉卖出
                    death_cross = (
                        row["short_ma"] < row["long_ma"]
                        and prev["short_ma"] >= prev["long_ma"]
                    )
                    # 条件B: 固定止损（亏损超过5%）
                    pnl = (price - buy_price) / buy_price
                    hit_stop_loss = pnl <= self.stop_loss
                    # 条件C: 移动止盈（从最高点回落超过3%）
                    drawdown_from_peak = (price - max_price_since_buy) / max_price_since_buy
                    hit_trailing_stop = drawdown_from_peak <= self.trailing_stop and pnl > 0

                    if death_cross or hit_stop_loss or hit_trailing_stop:
                        signal = -1
                        in_position = False
                        last_trade_idx = i

                        reason = []
                        if death_cross:
                            reason.append("死叉")
                        if hit_stop_loss:
                            reason.append(f"止损({pnl:.1%})")
                        if hit_trailing_stop:
                            reason.append(f"移动止盈(回撤{drawdown_from_peak:.1%})")

            signal_list.append(signal)

        signals["signal"] = signal_list
        signals["signal"] = signals["signal"].astype(int)

        buy_count = (signals["signal"] == 1).sum()
        sell_count = (signals["signal"] == -1).sum()
        print(f"[{self.name}] 短MA={self.short_window}, 长MA={self.long_window}, 趋势MA={self.trend_window}")
        print(f"  过滤条件: 量比>{self.volume_ratio}, 止损{self.stop_loss:.0%}, 移动止盈回撤{self.trailing_stop:.0%}")
        print(f"  买入信号: {buy_count} 次, 卖出信号: {sell_count} 次")

        return signals
