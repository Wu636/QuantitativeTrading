"""
异动计算 API。
"""

from datetime import datetime, timedelta
import io
import sys
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from analyst.abnormal_movement import calculate_abnormal_movement, resolve_board_rule
from data.fetcher import DataFetcher

router = APIRouter(prefix="/abnormal", tags=["异动计算"])


class AbnormalRequest(BaseModel):
    query: str = Field("000001", description="股票名称或 6 位代码")
    lookahead_days: int = Field(10, ge=1, le=60, description="向后估算交易日数量")
    history_days: int = Field(80, ge=20, le=260, description="图表历史交易日数量")


@router.get("/rules")
def list_rules():
    return {
        "rules": [
            {"board": "沪深主板", "ordinary": "3 日累计偏离 ±20%", "severe": "10 日 4 次同向 / +100% / -50%，30 日 +200% / -70%"},
            {"board": "创业板 / 科创板", "ordinary": "3 日累计偏离 ±30%", "severe": "10 日 3 次同向 / +100% / -50%，30 日 +200% / -70%"},
            {"board": "ST / *ST 主板", "ordinary": "3 日累计偏离 ±12%", "severe": "沿用主板严重异动阈值"},
        ]
    }


@router.post("/calculate")
def calculate(req: AbnormalRequest):
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=max(520, (req.history_days + 120) * 2))).strftime("%Y%m%d")

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            symbol, stock_name = DataFetcher.resolve_stock_symbol(req.query)
            board_rule = resolve_board_rule(symbol, stock_name)
            daily = DataFetcher.get_stock_daily(symbol=symbol, start_date=start_date, end_date=end_date)
            index_daily = DataFetcher.get_market_index_daily(
                symbol=board_rule.index_symbol,
                start_date=start_date,
                end_date=end_date,
            )
            daily = DataFetcher.append_realtime_quote(daily, symbol)
            index_daily = DataFetcher.append_realtime_quote(index_daily, board_rule.index_symbol)
        finally:
            sys.stdout = old_stdout

        result = calculate_abnormal_movement(
            stock_daily=daily,
            index_daily=index_daily,
            board_rule=board_rule,
            lookahead_days=req.lookahead_days,
            history_days=req.history_days,
        )
        return {
            "symbol": symbol,
            "stock_name": stock_name,
            **result,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))
