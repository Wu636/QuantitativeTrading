"""
策略对比工具 - 在同一数据集上对比多个策略的表现

功能：
1. 同时运行多个策略
2. 生成对比表格和对比图
3. 支持参数优化
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

from data.fetcher import DataFetcher
from data.processor import DataProcessor
from backtest.engine import BacktestEngine, BacktestConfig
from utils.metrics import calc_metrics, print_metrics
from utils.plotting import plot_backtest_report

# 中文字体
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "Heiti TC", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False


def run_strategy_comparison(
    symbol: str = "000001",
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000.0,
    strategies: list = None,
):
    """
    运行多策略对比

    Parameters
    ----------
    symbol : str
        股票代码
    strategies : list
        策略实例列表，如 [DualMAStrategy(5,20), MACDStrategy(), ...]
    """
    from strategies import (
        DualMAStrategy,
        EnhancedDualMAStrategy,
        MACDStrategy,
        BollingerStrategy,
        MultiFactorStrategy,
    )

    print("=" * 70)
    print("  🏆 A股量化策略对比系统")
    print("=" * 70)

    # ===== 获取数据 =====
    fetcher = DataFetcher()
    raw_data = fetcher.get_stock_daily(symbol, start_date, end_date)
    stock_name = fetcher.get_stock_name(symbol)
    processor = DataProcessor()
    data = processor.prepare_backtest_data(raw_data, symbol=symbol)

    print(f"\n📋 对比标的: {stock_name}({symbol})")
    print(f"   时间范围: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")

    # ===== 默认策略组合 =====
    if strategies is None:
        strategies = [
            DualMAStrategy(short_window=5, long_window=20),
            DualMAStrategy(short_window=10, long_window=30),
            EnhancedDualMAStrategy(short_window=10, long_window=30),
            MACDStrategy(zero_line_filter=True),
            BollingerStrategy(bb_period=20, bb_std=2.0),
            MultiFactorStrategy(min_factors=4),
        ]

    # ===== 运行每个策略 =====
    all_results = []
    config = BacktestConfig(initial_capital=initial_capital)

    for strategy in strategies:
        print(f"\n{'─' * 70}")
        try:
            signals = strategy.generate_signals(data)
            engine = BacktestEngine(config)
            result = engine.run(data, signals)
            metrics = calc_metrics(result)

            all_results.append({
                "strategy": strategy,
                "signals": signals,
                "result": result,
                "metrics": metrics,
            })
        except Exception as e:
            print(f"  ❌ {strategy.name} 运行失败: {e}")

    # ===== 打印对比表格 =====
    print(f"\n\n{'=' * 90}")
    print(f"  📊 策略对比总表 - {stock_name}({symbol})")
    print(f"{'=' * 90}")

    header = f"{'策略':<22} {'总收益':>8} {'年化':>8} {'最大回撤':>8} {'夏普':>6} {'胜率':>6} {'盈亏比':>6} {'交易次数':>8}"
    print(header)
    print("-" * 90)

    # 基准行
    benchmark_ret = all_results[0]["metrics"]["benchmark_return"] if all_results else 0
    print(f"{'📌 基准(买入持有)':<22} {benchmark_ret:>7.2%} {'--':>8} {'--':>8} {'--':>6} {'--':>6} {'--':>6} {'--':>8}")
    print("-" * 90)

    for item in all_results:
        m = item["metrics"]
        name = str(item["strategy"])
        if len(name) > 20:
            name = name[:18] + ".."
        total_ret_str = f"{m['total_return']:>7.2%}"
        annual_str = f"{m['annual_return']:>7.2%}"
        dd_str = f"{m['max_drawdown']:>7.2%}"
        sharpe_str = f"{m['sharpe_ratio']:>5.2f}"
        wr_str = f"{m['win_rate']:>5.1%}"
        plr_str = f"{m['profit_loss_ratio']:>5.2f}"
        trades_str = f"{m['total_trades']:>7d}"

        # 超越基准的用绿色标记
        marker = "🟢" if m["total_return"] > benchmark_ret else "🔴"
        print(f"{marker} {name:<20} {total_ret_str} {annual_str} {dd_str} {sharpe_str} {wr_str} {plr_str} {trades_str}")

    print(f"{'=' * 90}")

    # 找出最优策略
    best_idx = max(range(len(all_results)), key=lambda i: all_results[i]["metrics"]["sharpe_ratio"])
    best = all_results[best_idx]
    print(f"\n  🏆 综合最优（夏普比率最高）: {best['strategy']}")
    print(f"     总收益={best['metrics']['total_return']:.2%}, 夏普={best['metrics']['sharpe_ratio']:.2f}, 最大回撤={best['metrics']['max_drawdown']:.2%}")

    # ===== 生成对比图 =====
    _plot_comparison(all_results, stock_name, symbol)

    # ===== 为最优策略生成详细报告 =====
    print(f"\n📝 生成最优策略详细报告...")
    print_metrics(best["metrics"], str(best["strategy"]))
    plot_backtest_report(
        data=data,
        signals=best["signals"],
        result=best["result"],
        metrics=best["metrics"],
        strategy_name=str(best["strategy"]),
        stock_name=f"{stock_name}({symbol})",
        save_path=f"output/{symbol}_best_strategy_report.png",
    )

    return all_results


def _plot_comparison(all_results: list, stock_name: str, symbol: str):
    """生成策略净值对比图"""
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))

    # --- 净值对比 ---
    ax1 = axes[0]
    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", "#C9B1FF", "#FFD93D", "#6BCB77"]

    for i, item in enumerate(all_results):
        daily = item["result"]["daily_df"]
        name = str(item["strategy"])
        if len(name) > 25:
            name = name[:23] + ".."
        ret = item["metrics"]["total_return"]
        color = colors[i % len(colors)]
        ax1.plot(daily.index, daily["net_value"], color=color, linewidth=1.5,
                 label=f"{name} ({ret:.1%})", alpha=0.85)

    # 基准
    if all_results:
        daily0 = all_results[0]["result"]["daily_df"]
        ax1.plot(daily0.index, daily0["benchmark"], color="gray", linewidth=2,
                 linestyle="--", label=f"基准-买入持有", alpha=0.6)

    ax1.axhline(y=1.0, color="black", linewidth=0.5, linestyle=":")
    ax1.set_title(f"{stock_name}({symbol}) - 多策略净值对比", fontsize=14, fontweight="bold")
    ax1.set_ylabel("净值")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # --- 回撤对比 ---
    ax2 = axes[1]
    for i, item in enumerate(all_results):
        daily = item["result"]["daily_df"]
        cummax = daily["total_value"].cummax()
        dd = (daily["total_value"] - cummax) / cummax
        name = str(item["strategy"])
        if len(name) > 25:
            name = name[:23] + ".."
        color = colors[i % len(colors)]
        ax2.plot(dd.index, dd.values, color=color, linewidth=1.0,
                 label=f"{name} (最大回撤{item['metrics']['max_drawdown']:.1%})", alpha=0.7)

    ax2.set_title("回撤对比", fontsize=14, fontweight="bold")
    ax2.set_ylabel("回撤幅度")
    ax2.set_xlabel("日期")
    ax2.legend(loc="lower left", fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    os.makedirs("output", exist_ok=True)
    save_path = f"output/{symbol}_strategy_comparison.png"
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"\n📊 策略对比图已保存至: {save_path}")
    plt.show()
    plt.close()


if __name__ == "__main__":
    run_strategy_comparison(
        symbol="601212",
        initial_capital=100000,
    )
