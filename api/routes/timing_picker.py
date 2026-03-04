from fastapi import APIRouter, Query

from stock_picker.auction_picker import AuctionPicker
from stock_picker.overnight_picker import OvernightPicker

router = APIRouter(
    prefix="/timing-picker",
    tags=["时机选股"],
)


@router.get("/auction")
def run_auction_picker(
    mode: str = Query("attack", description="attack=攻势追强 | bargain=低吸抄底"),
    top_n: int = Query(20, ge=1, le=50),
):
    """盘前竞价选股 — 9:25 后运行效果最佳"""
    picker = AuctionPicker()
    return picker.run(mode=mode, top_n=top_n)


@router.get("/overnight")
def run_overnight_picker(
    mode: str = Query("attack", description="attack=强势隔夜 | bargain=跌幅捡筹"),
    top_n: int = Query(20, ge=1, le=50),
):
    """尾盘一夜法选股 — 14:30 后运行效果最佳"""
    picker = OvernightPicker()
    return picker.run(mode=mode, top_n=top_n)
