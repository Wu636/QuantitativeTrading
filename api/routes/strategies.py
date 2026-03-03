"""
策略 API — 列出可用策略 + 多策略对比
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import traceback
import io
import sys

router = APIRouter(tags=["策略"])


class CompareRequest(BaseModel):
    symbol: str = Field("000001", description="股票代码")
    strategy_names: list[str] = Field(
        default_factory=lambda: ["dual_ma", "enhanced_dual_ma", "macd", "bollinger", "multi_factor", "turtle"],
        description="策略名称列表",
    )
    initial_capital: float = Field(100000, description="初始资金")
    start_date: str | None = Field(None, description="开始日期 YYYYMMDD")
    end_date: str | None = Field(None, description="结束日期 YYYYMMDD")


def _get_all_strategies():
    """获取所有策略信息"""
    from strategies import (
        DualMAStrategy, EnhancedDualMAStrategy,
        MACDStrategy, BollingerStrategy,
        MultiFactorStrategy, TurtleStrategy,
    )
    return {
        "dual_ma": {
            "class": DualMAStrategy,
            "name": "双均线策略",
            "description": "经典双均线金叉/死叉",
            "default_params": {"short_window": 5, "long_window": 20},
        },
        "enhanced_dual_ma": {
            "class": EnhancedDualMAStrategy,
            "name": "增强双均线策略",
            "description": "双均线+趋势过滤+量能确认+止损止盈",
            "default_params": {"short_window": 10, "long_window": 30, "trend_window": 60},
        },
        "macd": {
            "class": MACDStrategy,
            "name": "MACD策略",
            "description": "MACD 金叉/死叉",
            "default_params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        },
        "bollinger": {
            "class": BollingerStrategy,
            "name": "布林带策略",
            "description": "布林带超买超卖+RSI确认",
            "default_params": {"bb_period": 20, "bb_std": 2.0},
        },
        "multi_factor": {
            "class": MultiFactorStrategy,
            "name": "多因子策略",
            "description": "趋势+动量+均线+量能+RSI多因子投票",
            "default_params": {"min_factors": 4},
        },
        "turtle": {
            "class": TurtleStrategy,
            "name": "海龟策略",
            "description": "Donchian通道突破+ATR止损",
            "default_params": {"entry_window": 20, "exit_window": 10, "atr_period": 20},
        },
    }


@router.get("/strategies")
def list_strategies():
    """列出所有可用策略"""
    strategies = _get_all_strategies()
    result = []
    for key, info in strategies.items():
        result.append({
            "key": key,
            "name": info["name"],
            "description": info["description"],
            "default_params": info["default_params"],
        })
    return {"strategies": result}


@router.post("/compare")
def compare_strategies(req: CompareRequest):
    """多策略对比"""
    try:
        from data.fetcher import DataFetcher
        from data.processor import DataProcessor
        from backtest.engine import BacktestEngine, BacktestConfig
        from utils.metrics import calc_metrics

        all_strategies = _get_all_strategies()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            fetcher = DataFetcher()
            raw_data = fetcher.get_stock_daily(
                symbol=req.symbol,
                start_date=req.start_date,
                end_date=req.end_date,
            )
            stock_name = fetcher.get_stock_name(req.symbol)
            processor = DataProcessor()
            data = processor.prepare_backtest_data(raw_data, symbol=req.symbol)

            results = []
            config = BacktestConfig(initial_capital=req.initial_capital)

            for sname in req.strategy_names:
                if sname not in all_strategies:
                    continue

                info = all_strategies[sname]
                try:
                    strategy = info["class"](**info["default_params"])
                    signals = strategy.generate_signals(data)
                    engine = BacktestEngine(config)
                    result = engine.run(data, signals)
                    metrics = calc_metrics(result)

                    daily_df = result["daily_df"]
                    daily_list = []
                    for date, row in daily_df.iterrows():
                        daily_list.append({
                            "date": date.strftime("%Y-%m-%d"),
                            "net_value": round(row["net_value"], 4),
                            "benchmark": round(row["benchmark"], 4),
                        })

                    results.append({
                        "key": sname,
                        "name": info["name"],
                        "metrics": {
                            "total_return": round(metrics["total_return"], 4),
                            "annual_return": round(metrics["annual_return"], 4),
                            "max_drawdown": round(metrics["max_drawdown"], 4),
                            "sharpe_ratio": round(metrics["sharpe_ratio"], 3),
                            "win_rate": round(metrics["win_rate"], 4),
                            "profit_loss_ratio": round(metrics["profit_loss_ratio"], 3),
                            "total_trades": metrics["total_trades"],
                        },
                        "daily": daily_list,
                    })
                except Exception:
                    continue
        finally:
            sys.stdout = old_stdout

        # 基准
        benchmark_return = results[0]["daily"][-1]["benchmark"] - 1 if results else 0

        return {
            "stock_name": stock_name,
            "symbol": req.symbol,
            "benchmark_return": round(benchmark_return, 4),
            "results": results,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
