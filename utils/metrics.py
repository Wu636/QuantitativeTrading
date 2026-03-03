"""
绩效指标计算模块

包含量化交易中常用的评估指标：
- 总收益率
- 年化收益率
- 最大回撤
- 夏普比率
- 胜率
- 盈亏比
"""

import pandas as pd
import numpy as np


def calc_metrics(result: dict) -> dict:
    """
    计算回测绩效指标

    Parameters
    ----------
    result : dict
        BacktestEngine.run() 的返回结果

    Returns
    -------
    dict
        各项绩效指标
    """
    daily_df = result["daily_df"]
    trades = result["trades"]
    initial_capital = result["initial_capital"]
    final_value = result["final_value"]

    # ---------- 基础收益 ----------
    total_return = (final_value - initial_capital) / initial_capital
    trading_days = len(daily_df)
    years = trading_days / 252  # A股每年约252个交易日
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    # ---------- 最大回撤 ----------
    cummax = daily_df["total_value"].cummax()
    drawdown = (daily_df["total_value"] - cummax) / cummax
    max_drawdown = drawdown.min()
    # 最大回撤发生的日期
    max_dd_end = drawdown.idxmin()
    max_dd_start = daily_df["total_value"][:max_dd_end].idxmax()

    # ---------- 夏普比率 ----------
    # 无风险利率按年化2.5%（近似一年期国债收益率）
    risk_free_rate = 0.025
    daily_rf = risk_free_rate / 252
    daily_returns = daily_df["daily_return"].dropna()
    excess_returns = daily_returns - daily_rf

    if daily_returns.std() > 0:
        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / daily_returns.std()
    else:
        sharpe_ratio = 0

    # ---------- 交易统计 ----------
    buy_trades = [t for t in trades if t.action == "buy"]
    sell_trades = [t for t in trades if t.action == "sell"]
    total_trades = min(len(buy_trades), len(sell_trades))  # 完整交易对数

    # 计算每笔交易盈亏
    trade_profits = []
    for i in range(total_trades):
        buy_amount = buy_trades[i].amount + buy_trades[i].commission
        sell_amount = sell_trades[i].amount - sell_trades[i].commission
        profit = sell_amount - buy_amount
        trade_profits.append(profit)

    trade_profits = np.array(trade_profits)
    win_trades = trade_profits[trade_profits > 0]
    lose_trades = trade_profits[trade_profits <= 0]

    win_rate = len(win_trades) / total_trades if total_trades > 0 else 0

    avg_win = win_trades.mean() if len(win_trades) > 0 else 0
    avg_lose = abs(lose_trades.mean()) if len(lose_trades) > 0 else 0
    profit_loss_ratio = avg_win / avg_lose if avg_lose > 0 else float("inf")

    # 总手续费
    total_commission = sum(t.commission for t in trades)

    # ---------- 基准对比 ----------
    benchmark_return = (daily_df["benchmark"].iloc[-1] - 1) if not daily_df.empty else 0
    excess_return = total_return - benchmark_return

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "benchmark_return": benchmark_return,
        "excess_return": excess_return,
        "max_drawdown": max_drawdown,
        "max_dd_start": max_dd_start,
        "max_dd_end": max_dd_end,
        "sharpe_ratio": sharpe_ratio,
        "trading_days": trading_days,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_loss_ratio": profit_loss_ratio,
        "avg_win": avg_win,
        "avg_lose": avg_lose,
        "total_commission": total_commission,
        "initial_capital": initial_capital,
        "final_value": final_value,
        "trade_profits": trade_profits.tolist(),
    }


def print_metrics(metrics: dict, strategy_name: str = ""):
    """
    打印回测指标报告

    Parameters
    ----------
    metrics : dict
        calc_metrics() 的返回结果
    strategy_name : str
        策略名称
    """
    print("\n" + "=" * 60)
    print(f"  📊 回测报告 {f'- {strategy_name}' if strategy_name else ''}")
    print("=" * 60)

    print(f"\n  💰 资金概况")
    print(f"  {'初始资金:':<15} ¥{metrics['initial_capital']:>12,.2f}")
    print(f"  {'最终资产:':<15} ¥{metrics['final_value']:>12,.2f}")
    print(f"  {'总手续费:':<15} ¥{metrics['total_commission']:>12,.2f}")

    print(f"\n  📈 收益指标")
    print(f"  {'总收益率:':<15} {metrics['total_return']:>10.2%}")
    print(f"  {'年化收益率:':<13} {metrics['annual_return']:>10.2%}")
    print(f"  {'基准收益率:':<13} {metrics['benchmark_return']:>10.2%}")
    print(f"  {'超额收益:':<15} {metrics['excess_return']:>10.2%}")

    print(f"\n  ⚠️  风险指标")
    print(f"  {'最大回撤:':<15} {metrics['max_drawdown']:>10.2%}")
    print(f"  {'夏普比率:':<15} {metrics['sharpe_ratio']:>10.2f}")

    print(f"\n  🔄 交易统计")
    print(f"  {'交易天数:':<15} {metrics['trading_days']:>10d}")
    print(f"  {'完整交易次数:':<11} {metrics['total_trades']:>10d}")
    print(f"  {'胜率:':<15} {metrics['win_rate']:>10.2%}")
    print(f"  {'盈亏比:':<15} {metrics['profit_loss_ratio']:>10.2f}")
    print(f"  {'平均盈利:':<15} ¥{metrics['avg_win']:>10,.2f}")
    print(f"  {'平均亏损:':<15} ¥{metrics['avg_lose']:>10,.2f}")

    print("\n" + "=" * 60)
