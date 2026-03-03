"""
参数优化示例 - 为增强双均线策略寻找最优参数

运行: python optimize_params.py
"""

from data.fetcher import DataFetcher
from data.processor import DataProcessor
from strategies.enhanced_dual_ma import EnhancedDualMAStrategy
from strategies.macd_strategy import MACDStrategy
from backtest.engine import BacktestConfig
from utils.optimizer import StrategyOptimizer


def optimize_enhanced_dual_ma(symbol: str = "000001"):
    """优化增强双均线策略的参数"""
    print("=" * 60)
    print("  🔍 参数优化 - 增强双均线策略")
    print("=" * 60)

    # 获取数据
    fetcher = DataFetcher()
    raw_data = fetcher.get_stock_daily(symbol)
    processor = DataProcessor()
    data = processor.prepare_backtest_data(raw_data, symbol=symbol)

    # 定义参数搜索空间
    param_grid = {
        "short_window": [5, 8, 10, 13, 15],
        "long_window": [20, 25, 30, 40, 60],
        "trend_window": [40, 60, 90],
        "stop_loss": [-0.04, -0.05, -0.07],
    }

    config = BacktestConfig(initial_capital=100000)
    optimizer = StrategyOptimizer(data, EnhancedDualMAStrategy, config)

    best_params, results_df = optimizer.optimize(
        param_grid,
        sort_by="sharpe_ratio",
        top_n=15,
    )

    # 保存结果
    results_df.to_csv(f"output/{symbol}_optimization_results.csv", index=False)
    print(f"\n📁 优化结果已保存至: output/{symbol}_optimization_results.csv")

    return best_params, results_df


def optimize_macd(symbol: str = "000001"):
    """优化MACD策略的参数"""
    print("\n" + "=" * 60)
    print("  🔍 参数优化 - MACD策略")
    print("=" * 60)

    fetcher = DataFetcher()
    raw_data = fetcher.get_stock_daily(symbol)
    processor = DataProcessor()
    data = processor.prepare_backtest_data(raw_data, symbol=symbol)

    param_grid = {
        "fast_period": [8, 10, 12, 15],
        "slow_period": [20, 24, 26, 30],
        "signal_period": [7, 9, 11],
        "stop_loss": [-0.04, -0.06, -0.08],
    }

    config = BacktestConfig(initial_capital=100000)
    optimizer = StrategyOptimizer(data, MACDStrategy, config)

    best_params, results_df = optimizer.optimize(
        param_grid,
        sort_by="sharpe_ratio",
        top_n=15,
    )

    return best_params, results_df


if __name__ == "__main__":
    import os
    os.makedirs("output", exist_ok=True)

    # 优化增强双均线
    best_ema, _ = optimize_enhanced_dual_ma("601212")

    # 优化MACD
    best_macd, _ = optimize_macd("601212")

    print("\n\n" + "=" * 60)
    print("  ✅ 所有优化完成！")
    print("=" * 60)
    print(f"  增强双均线最优参数: {best_ema}")
    print(f"  MACD最优参数: {best_macd}")
    print("\n  💡 提示: 可以将最优参数填入 compare_strategies.py 中进行最终对比")
