"""
选股 API — 运行全市场选股筛选 + 模板管理
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import traceback
import math

router = APIRouter(tags=["选股"])


# ────────────────────────────────────────
# 请求/响应 模型
# ────────────────────────────────────────

class StockPickerRequest(BaseModel):
    top_n: int = Field(20, description="返回前 N 只股票")
    max_pe: float = Field(50, description="最大市盈率")
    min_pe: float = Field(0, description="最小市盈率")
    max_pb: float = Field(10, description="最大市净率")
    min_market_cap: float = Field(30e8, description="最低市值（元）")
    max_market_cap: float | None = Field(None, description="最高市值（元）")
    min_price: float = Field(2.0, description="最低股价")
    max_price: float = Field(500.0, description="最高股价")
    min_turnover: float = Field(0.3, description="最低换手率")
    min_momentum: float | None = Field(None, description="最低 60 日涨幅")
    min_roe: float | None = Field(None, description="最低 ROE（%），由 PB/PE 近似")
    min_volume_ratio: float | None = Field(None, description="最低量比")
    max_volume_ratio: float | None = Field(None, description="最高量比（缩量筛选用）")
    industry_pb_aware: bool = Field(False, description="是否启用分行业 PB 阈值")
    weights: dict | None = Field(None, description="因子权重")
    template_id: str | None = Field(None, description="模板 ID（可选，传入则用模板参数）")


class TemplateCreateRequest(BaseModel):
    name: str = Field(..., description="模板名称")
    description: str = Field("", description="模板描述")
    filters: dict = Field(..., description="筛选条件")
    weights: dict = Field(..., description="因子权重")
    top_n: int = Field(20, description="返回数量")


# ────────────────────────────────────────
# 选股 API
# ────────────────────────────────────────

@router.post("/stock-picker")
def run_stock_picker(req: StockPickerRequest):
    """运行选股"""
    try:
        from stock_picker import StockPicker
        from stock_picker.templates import get_template

        # 如果传了模板 ID，优先用模板参数
        if req.template_id:
            tmpl = get_template(req.template_id)
            if tmpl:
                f = tmpl["filters"]
                req.max_pe = f.get("max_pe", req.max_pe)
                req.min_pe = f.get("min_pe", req.min_pe)
                req.max_pb = f.get("max_pb", req.max_pb)
                # 模板里市值单位是亿元，API 期望元
                req.min_market_cap = f.get("min_market_cap", 50) * 1e8
                max_mc = f.get("max_market_cap")
                req.max_market_cap = max_mc * 1e8 if max_mc else None
                req.min_price = f.get("min_price", req.min_price)
                req.max_price = f.get("max_price", req.max_price)
                req.min_turnover = f.get("min_turnover", req.min_turnover)
                req.min_momentum = f.get("min_momentum", req.min_momentum)
                req.min_roe = f.get("min_roe", req.min_roe)
                req.min_volume_ratio = f.get("min_volume_ratio", req.min_volume_ratio)
                req.max_volume_ratio = f.get("max_volume_ratio", req.max_volume_ratio)
                req.industry_pb_aware = f.get("industry_pb_aware", req.industry_pb_aware)
                req.weights = tmpl.get("weights")
                req.top_n = tmpl.get("top_n", req.top_n)

        picker = StockPicker()
        result = picker.run(
            filters={
                "max_pe": req.max_pe,
                "min_pe": req.min_pe,
                "max_pb": req.max_pb,
                "min_market_cap": req.min_market_cap,
                "max_market_cap": req.max_market_cap,
                "min_price": req.min_price,
                "max_price": req.max_price,
                "min_turnover": req.min_turnover,
                "min_momentum": req.min_momentum,
                "min_roe": req.min_roe,
                "min_volume_ratio": req.min_volume_ratio,
                "max_volume_ratio": req.max_volume_ratio,
                "industry_pb_aware": req.industry_pb_aware,
            },
            weights=req.weights,
            top_n=req.top_n,
        )

        if result.empty:
            return {"stocks": [], "total": 0}

        # 构造返回数据
        display_cols = [
            "代码", "名称", "最新价", "涨跌幅", "市盈率-动态", "市净率",
            "总市值", "换手率", "量比",
            "factor_value", "factor_momentum", "factor_quality",
            "factor_liquidity", "factor_size", "factor_capital_flow",
            "factor_roe", "total_score",
        ]
        display_cols = [c for c in display_cols if c in result.columns]

        stocks = []
        for _, row in result[display_cols].iterrows():
            stock = {}
            for col in display_cols:
                val = row[col]
                if isinstance(val, float):
                    if math.isnan(val) or math.isinf(val):
                        stock[col] = None
                    else:
                        stock[col] = round(val, 2)
                else:
                    stock[col] = val
            stocks.append(stock)

        return {
            "stocks": stocks,
            "total": len(stocks),
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────
# 模板 CRUD API
# ────────────────────────────────────────

@router.get("/stock-picker/templates")
def list_templates():
    """返回所有选股模板（内置 + 自定义）"""
    from stock_picker.templates import list_all_templates
    return {"templates": list_all_templates()}


@router.post("/stock-picker/templates")
def create_template(req: TemplateCreateRequest):
    """创建自定义选股模板"""
    from stock_picker.templates import create_template as _create
    template = _create(
        name=req.name,
        description=req.description,
        filters=req.filters,
        weights=req.weights,
        top_n=req.top_n,
    )
    return {"template": template}


@router.delete("/stock-picker/templates/{template_id}")
def delete_template(template_id: str):
    """删除自定义选股模板"""
    from stock_picker.templates import delete_template as _delete, get_template
    tmpl = get_template(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    if tmpl.get("builtin"):
        raise HTTPException(status_code=400, detail="内置模板不可删除")
    if _delete(template_id):
        return {"success": True}
    raise HTTPException(status_code=500, detail="删除失败")
