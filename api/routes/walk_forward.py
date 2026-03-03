"""
Walk-Forward API — 前推优化分析
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import traceback
import io
import sys

router = APIRouter(tags=["Walk-Forward"])


class WalkForwardRequest(BaseModel):
    symbol: str = Field("000001", description="股票代码")
    strategy_name: str = Field("dual_ma", description="策略名称")
    param_grid: dict = Field(
        default_factory=lambda: {
            "short_window": [5, 10, 15],
            "long_window": [20, 30, 60],
        },
        description="参数搜索空间",
    )
    train_days: int = Field(252, description="训练集天数")
    test_days: int = Field(126, description="测试集天数")
    initial_capital: float = Field(100000, description="初始资金")
    start_date: str | None = Field(None, description="开始日期 YYYYMMDD")
    end_date: str | None = Field(None, description="结束日期 YYYYMMDD")


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
        raise HTTPException(
            status_code=400,
            detail=f"未知策略: {name}，可用: {list(mapping.keys())}",
        )
    return cls


@router.post("/walk-forward")
def run_walk_forward(req: WalkForwardRequest):
    """运行 Walk-Forward 分析"""
    try:
        from data.fetcher import DataFetcher
        from data.processor import DataProcessor
        from backtest.engine import BacktestConfig
        from utils.walk_forward import WalkForwardAnalyzer

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            fetcher = DataFetcher()
            raw_data = fetcher.get_stock_daily(
                symbol=req.symbol,
                start_date=req.start_date,
                end_date=req.end_date,
            )
            processor = DataProcessor()
            data = processor.prepare_backtest_data(raw_data, symbol=req.symbol)

            strategy_class = _get_strategy_class(req.strategy_name)
            config = BacktestConfig(initial_capital=req.initial_capital)

            analyzer = WalkForwardAnalyzer(data, strategy_class, config)
            summary, details_df = analyzer.run(
                param_grid=req.param_grid,
                train_days=req.train_days,
                test_days=req.test_days,
            )
        finally:
            sys.stdout = old_stdout

        if details_df.empty:
            return {"summary": {}, "details": [], "message": "数据不足以进行Walk-Forward分析"}

        details_list = details_df.to_dict(orient="records")
        # Round float values
        for d in details_list:
            for k, v in d.items():
                if isinstance(v, float):
                    d[k] = round(v, 4)

        return {
            "symbol": req.symbol,
            "strategy": req.strategy_name,
            "summary": summary,
            "details": details_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
