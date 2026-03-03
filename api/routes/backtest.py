"""
回测 API — 运行单标的回测
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import traceback
import io
import sys

router = APIRouter(tags=["回测"])


class BacktestRequest(BaseModel):
    symbol: str = Field("000001", description="股票代码")
    strategy_name: str = Field("dual_ma", description="策略名称")
    params: dict = Field(default_factory=dict, description="策略参数")
    initial_capital: float = Field(100000, description="初始资金")
    start_date: str | None = Field(None, description="开始日期 YYYYMMDD")
    end_date: str | None = Field(None, description="结束日期 YYYYMMDD")


# 策略名 → 策略类的映射
def _get_strategy_class(name: str):
    from strategies import (
        DualMAStrategy, EnhancedDualMAStrategy,
        MACDStrategy, BollingerStrategy,
        MultiFactorStrategy, TurtleStrategy,
    )
    mapping = {
        "dual_ma": DualMAStrategy,
        "enhanced_dual_ma": EnhancedDualMAStrategy,
        "macd": MACDStrategy,
        "bollinger": BollingerStrategy,
        "multi_factor": MultiFactorStrategy,
        "turtle": TurtleStrategy,
    }
    cls = mapping.get(name)
    if cls is None:
        raise HTTPException(status_code=400, detail=f"未知策略: {name}，可用: {list(mapping.keys())}")
    return cls


@router.post("/backtest")
def run_backtest(req: BacktestRequest):
    """运行单标的回测"""
    try:
        from data.fetcher import DataFetcher
        from data.processor import DataProcessor
        from backtest.engine import BacktestEngine, BacktestConfig
        from utils.metrics import calc_metrics

        # 静默运行
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            # 获取数据
            fetcher = DataFetcher()
            raw_data = fetcher.get_stock_daily(
                symbol=req.symbol,
                start_date=req.start_date,
                end_date=req.end_date,
            )
            stock_name = fetcher.get_stock_name(req.symbol)

            processor = DataProcessor()
            data = processor.prepare_backtest_data(raw_data, symbol=req.symbol)

            # 构建策略
            strategy_class = _get_strategy_class(req.strategy_name)
            strategy = strategy_class(**req.params)
            signals = strategy.generate_signals(data)

            # 回测
            config = BacktestConfig(initial_capital=req.initial_capital)
            engine = BacktestEngine(config)
            result = engine.run(data, signals)
            metrics = calc_metrics(result)
        finally:
            sys.stdout = old_stdout

        # 构造返回数据
        daily_df = result["daily_df"]
        daily_list = []
        for date, row in daily_df.iterrows():
            daily_list.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": round(row["close"], 2),
                "net_value": round(row["net_value"], 4),
                "benchmark": round(row["benchmark"], 4),
                "total_value": round(row["total_value"], 2),
                "cash": round(row["cash"], 2),
                "position": int(row["position"]),
                "signal": int(row["signal"]),
            })

        trades_list = []
        for t in result["trades"]:
            trades_list.append({
                "date": t.date.strftime("%Y-%m-%d"),
                "action": t.action,
                "price": round(t.price, 2),
                "shares": t.shares,
                "amount": round(t.amount, 2),
                "commission": round(t.commission, 2),
                "reason": t.reason,
            })

        return {
            "stock_name": stock_name,
            "symbol": req.symbol,
            "strategy": str(strategy),
            "metrics": {
                "total_return": round(metrics["total_return"], 4),
                "annual_return": round(metrics["annual_return"], 4),
                "benchmark_return": round(metrics["benchmark_return"], 4),
                "excess_return": round(metrics["excess_return"], 4),
                "max_drawdown": round(metrics["max_drawdown"], 4),
                "sharpe_ratio": round(metrics["sharpe_ratio"], 3),
                "win_rate": round(metrics["win_rate"], 4),
                "profit_loss_ratio": round(metrics["profit_loss_ratio"], 3),
                "total_trades": metrics["total_trades"],
                "total_commission": round(metrics["total_commission"], 2),
                "initial_capital": metrics["initial_capital"],
                "final_value": round(metrics["final_value"], 2),
            },
            "daily": daily_list,
            "trades": trades_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
