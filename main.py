"""
A股量化交易学习项目 - 主入口

运行示例：使用双均线策略回测平安银行(000001)
"""

from data.fetcher import DataFetcher
from data.processor import DataProcessor
from strategies.dual_ma import DualMAStrategy
from backtest.engine import BacktestEngine, BacktestConfig
from utils.metrics import calc_metrics, print_metrics
from utils.plotting import plot_backtest_report, plot_trade_distribution


def run_dual_ma_backtest(
    symbol: str = "000001",
    start_date: str = None,
    end_date: str = None,
    short_window: int = 5,
    long_window: int = 20,
    initial_capital: float = 100000.0,
):
    """
    运行双均线策略回测

    Parameters
    ----------
    symbol : str
        股票代码，默认 "000001"（平安银行）
    start_date : str
        开始日期 "YYYYMMDD"，默认2年前
    end_date : str
        结束日期 "YYYYMMDD"，默认今天
    short_window : int
        短期均线天数
    long_window : int
        长期均线天数
    initial_capital : float
        初始资金
    """
    print("=" * 60)
    print("  🚀 A股量化回测系统")
    print("=" * 60)

    # ========== 1. 获取数据 ==========
    print("\n📡 Step 1: 获取行情数据...")
    fetcher = DataFetcher()
    raw_data = fetcher.get_stock_daily(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )
    stock_name = fetcher.get_stock_name(symbol)
    print(f"股票名称: {stock_name}")

    # ========== 2. 数据处理 ==========
    print("\n🔧 Step 2: 数据预处理...")
    processor = DataProcessor()
    data = processor.prepare_backtest_data(
        raw_data,
        ma_windows=[short_window, long_window],
        symbol=symbol,  # 传入股票代码，用于判断涨跌停阈值
    )
    print(f"处理后数据范围: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"共 {len(data)} 个交易日")

    # ========== 3. 生成策略信号 ==========
    print("\n📊 Step 3: 生成交易信号...")
    strategy = DualMAStrategy(short_window=short_window, long_window=long_window)
    signals = strategy.generate_signals(data)

    # ========== 4. 运行回测 ==========
    print("\n⚙️  Step 4: 运行回测引擎...")
    config = BacktestConfig(initial_capital=initial_capital)
    engine = BacktestEngine(config)
    result = engine.run(data, signals)

    # 将策略参数存入结果（供绘图使用）
    result["short_window"] = short_window
    result["long_window"] = long_window

    # ========== 5. 计算指标 ==========
    print("\n📈 Step 5: 计算绩效指标...")
    metrics = calc_metrics(result)
    print_metrics(metrics, strategy_name=str(strategy))

    # ========== 6. 输出交易明细 ==========
    print("\n📋 交易明细:")
    print("-" * 80)
    print(f"{'日期':<12} {'操作':<6} {'价格':>8} {'数量':>8} {'金额':>12} {'手续费':>8} {'原因'}")
    print("-" * 80)
    for t in result["trades"]:
        action_str = "🔴买入" if t.action == "buy" else "🟢卖出"
        print(
            f"{t.date.strftime('%Y-%m-%d'):<12} {action_str:<6} "
            f"{t.price:>8.2f} {t.shares:>8d} "
            f"¥{t.amount:>10,.2f} ¥{t.commission:>6.2f}  {t.reason}"
        )
    print("-" * 80)

    # ========== 7. 可视化 ==========
    print("\n🎨 Step 6: 生成可视化报告...")
    plot_backtest_report(
        data=data,
        signals=signals,
        result=result,
        metrics=metrics,
        strategy_name=str(strategy),
        stock_name=f"{stock_name}({symbol})",
        save_path=f"output/{symbol}_backtest_report.png",
    )

    plot_trade_distribution(
        metrics=metrics,
        save_path=f"output/{symbol}_trade_distribution.png",
    )

    print("\n✅ 回测完成！")
    return result, metrics


if __name__ == "__main__":
    # ============================
    #  在这里修改回测参数
    # ============================
    result, metrics = run_dual_ma_backtest(
        symbol="601212",          # 平安银行
        short_window=5,           # 5日均线
        long_window=20,           # 20日均线
        initial_capital=100000,   # 10万初始资金
    )
