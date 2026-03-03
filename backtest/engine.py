"""
轻量级回测引擎

特性：
- 支持A股 T+1 交易规则（买入当天不能卖出）
- 支持涨跌停限制（涨停不能买入，跌停不能卖出）
- 佣金和滑点模拟
- 逐日模拟，记录完整交易日志
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field


@dataclass
class TradeRecord:
    """交易记录"""
    date: pd.Timestamp
    action: str          # "buy" or "sell"
    price: float         # 成交价
    shares: int          # 成交股数
    amount: float        # 成交金额
    commission: float    # 手续费
    reason: str = ""     # 交易原因


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 100000.0   # 初始资金（10万）
    commission_rate: float = 0.0003     # 佣金费率（万三）
    min_commission: float = 5.0         # 最低佣金（5元）
    stamp_tax_rate: float = 0.0005      # 印花税（卖出时收取，万五）
    slippage: float = 0.002             # 滑点（0.2%），接近实盘
    position_ratio: float = 1.0         # 每次买入仓位比例（1.0 = 满仓）
    min_shares: int = 100               # 最小交易单位（1手 = 100股）
    use_next_open: bool = True          # True = T+1开盘价执行（消除未来函数），False = 当日收盘价


class BacktestEngine:
    """
    轻量级回测引擎

    使用方式：
        engine = BacktestEngine(config)
        result = engine.run(data, signals)

    Parameters
    ----------
    config : BacktestConfig
        回测配置参数
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.reset()

    def reset(self):
        """重置引擎状态"""
        self.cash = self.config.initial_capital
        self.position = 0           # 持仓股数
        self.position_cost = 0.0    # 持仓成本
        self.trades: list[TradeRecord] = []
        self.daily_records: list[dict] = []
        self._buy_date = None       # 最近一次买入日期（用于T+1判断）

    def _calc_commission(self, amount: float, is_sell: bool = False) -> float:
        """
        计算交易费用

        买入：佣金
        卖出：佣金 + 印花税
        """
        commission = max(amount * self.config.commission_rate, self.config.min_commission)
        if is_sell:
            commission += amount * self.config.stamp_tax_rate
        return round(commission, 2)

    def _can_buy(self, row: pd.Series) -> bool:
        """判断是否可以买入"""
        # 涨停不能买入
        if row.get("is_limit_up", False):
            return False
        return True

    def _can_sell(self, row: pd.Series, current_date: pd.Timestamp) -> bool:
        """判断是否可以卖出（考虑T+1）"""
        # 跌停不能卖出
        if row.get("is_limit_down", False):
            return False
        # T+1：买入当天不能卖出
        if self._buy_date is not None and current_date <= self._buy_date:
            return False
        return True

    def _execute_buy(self, date: pd.Timestamp, price: float, reason: str = ""):
        """执行买入"""
        # 加入滑点：买入价格略高
        actual_price = price * (1 + self.config.slippage)

        # 计算可买入股数（取整到100的倍数）
        available_cash = self.cash * self.config.position_ratio
        max_shares = int(available_cash / actual_price)
        shares = (max_shares // self.config.min_shares) * self.config.min_shares

        if shares <= 0:
            return

        amount = shares * actual_price
        commission = self._calc_commission(amount, is_sell=False)

        # 检查资金是否充足
        if amount + commission > self.cash:
            shares -= self.config.min_shares
            if shares <= 0:
                return
            amount = shares * actual_price
            commission = self._calc_commission(amount, is_sell=False)

        # 执行买入
        self.cash -= (amount + commission)
        self.position += shares
        self.position_cost = actual_price  # 简化：记录最新买入成本
        self._buy_date = date

        self.trades.append(TradeRecord(
            date=date,
            action="buy",
            price=actual_price,
            shares=shares,
            amount=amount,
            commission=commission,
            reason=reason,
        ))

    def _execute_sell(self, date: pd.Timestamp, price: float, reason: str = ""):
        """执行卖出"""
        if self.position <= 0:
            return

        # 加入滑点：卖出价格略低
        actual_price = price * (1 - self.config.slippage)
        shares = self.position
        amount = shares * actual_price
        commission = self._calc_commission(amount, is_sell=True)

        # 执行卖出
        self.cash += (amount - commission)
        self.position = 0
        self.position_cost = 0.0

        self.trades.append(TradeRecord(
            date=date,
            action="sell",
            price=actual_price,
            shares=shares,
            amount=amount,
            commission=commission,
            reason=reason,
        ))

    def run(self, data: pd.DataFrame, signals: pd.DataFrame) -> dict:
        """
        运行回测

        Parameters
        ----------
        data : pd.DataFrame
            行情数据，index为日期，至少包含 open, close, high, low 列
        signals : pd.DataFrame
            信号数据，index为日期，包含 signal 列
            signal: 1=买入信号, -1=卖出信号, 0=无操作

        Returns
        -------
        dict
            回测结果，包含：
            - daily_df: 每日持仓和净值记录
            - trades: 交易记录列表
            - config: 回测配置
        """
        self.reset()

        # 合并数据和信号
        df = data.join(signals[["signal"]], how="inner")

        # T+1模式：将信号向后移动一天，用第二天开盘价执行
        if self.config.use_next_open:
            df["pending_signal"] = df["signal"].shift(1).fillna(0).astype(int)
        else:
            df["pending_signal"] = df["signal"]

        for date, row in df.iterrows():
            signal = row["pending_signal"]  # 使用延迟后的信号

            # 根据模式选择执行价格
            if self.config.use_next_open:
                exec_price = row["open"]  # T+1模式：用开盘价执行
            else:
                exec_price = row["close"]  # 旧模式：用收盘价执行（有未来函数风险）

            # 处理买入信号
            if signal == 1 and self.position == 0:
                if self._can_buy(row):
                    self._execute_buy(date, exec_price, reason="均线金叉买入")

            # 处理卖出信号
            elif signal == -1 and self.position > 0:
                if self._can_sell(row, date):
                    self._execute_sell(date, exec_price, reason="均线死叉卖出")

            # 记录每日状态
            market_value = self.position * row["close"]
            total_value = self.cash + market_value

            self.daily_records.append({
                "date": date,
                "close": row["close"],
                "cash": round(self.cash, 2),
                "position": self.position,
                "market_value": round(market_value, 2),
                "total_value": round(total_value, 2),
                "signal": row["signal"],  # 记录原始信号（用于绘图）
            })

        # 构建每日记录DataFrame
        daily_df = pd.DataFrame(self.daily_records)
        if not daily_df.empty:
            daily_df = daily_df.set_index("date")
            daily_df["net_value"] = daily_df["total_value"] / self.config.initial_capital
            daily_df["daily_return"] = daily_df["total_value"].pct_change()
            # 基准收益（买入持有）
            daily_df["benchmark"] = daily_df["close"] / daily_df["close"].iloc[0]

        return {
            "daily_df": daily_df,
            "trades": self.trades,
            "config": self.config,
            "initial_capital": self.config.initial_capital,
            "final_value": daily_df["total_value"].iloc[-1] if not daily_df.empty else self.config.initial_capital,
        }
