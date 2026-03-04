"""
自选股管理与个性化分析 API
"""

import json
import os
import traceback
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["自选分析"])

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "watchlist.json")

# ────────────────────────────────────────
# 数据存取 Helper
# ────────────────────────────────────────

def load_watchlist() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"stocks": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"stocks": []}

def save_watchlist(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ────────────────────────────────────────
# 请求/响应模型
# ────────────────────────────────────────

class WatchlistStock(BaseModel):
    code: str
    name: str = ""
    holding: bool = False
    cost_price: float = 0.0
    position_pct: float = 0.0
    horizon: str = ""  # short/mid/long
    group: str = ""    # default, overnight, auction, etc
    added_at: str = ""

class SingleAnalyzeRequest(BaseModel):
    code: str
    days: int = 365
    holding: bool = False
    cost_price: float = 0.0
    position_pct: float = 0.0
    horizon: str = ""

class PortfolioAnalyzeRequest(BaseModel):
    days: int = 365
    codes: list[str] = []

# ────────────────────────────────────────
# CRUD 接口
# ────────────────────────────────────────

@router.get("/watchlist")
def get_watchlist():
    return load_watchlist()

@router.post("/watchlist")
def add_or_update_stock(stock: WatchlistStock):
    data = load_watchlist()
    stocks = data.get("stocks", [])
    
    # Check if exists
    for i, s in enumerate(stocks):
        if s["code"] == stock.code:
            stock.added_at = s.get("added_at", datetime.now().strftime("%Y-%m-%d"))
            stocks[i] = stock.model_dump()
            save_watchlist(data)
            return {"status": "ok", "message": "已更新"}
            
    # Add new
    stock.added_at = datetime.now().strftime("%Y-%m-%d")
    stocks.append(stock.model_dump())
    data["stocks"] = stocks
    save_watchlist(data)
    return {"status": "ok", "message": "已添加"}

class BatchAddRequest(BaseModel):
    stocks: list[WatchlistStock]

@router.post("/watchlist/batch")
def batch_add_stocks(req: BatchAddRequest):
    data = load_watchlist()
    existing_stocks = data.get("stocks", [])
    
    added_count = 0
    now_str = datetime.now().strftime("%Y-%m-%d")
    
    for new_stock in req.stocks:
        # Check if exists
        exists = False
        for i, s in enumerate(existing_stocks):
            if s["code"] == new_stock.code:
                exists = True
                new_stock.added_at = s.get("added_at", now_str)
                existing_stocks[i] = new_stock.model_dump()
                break
        
        if not exists:
            new_stock.added_at = now_str
            existing_stocks.append(new_stock.model_dump())
            added_count += 1
            
    data["stocks"] = existing_stocks
    save_watchlist(data)
    return {"status": "ok", "message": f"成功添加/更新 {len(req.stocks)} 只股票"}


@router.delete("/watchlist/{code}")
def remove_stock(code: str):
    data = load_watchlist()
    stocks = data.get("stocks", [])
    filtered = [s for s in stocks if s["code"] != code]
    if len(filtered) == len(stocks):
        raise HTTPException(status_code=404, detail="未找到该股票")
        
    data["stocks"] = filtered
    save_watchlist(data)
    return {"status": "ok", "message": "已移除"}

class BatchDeleteRequest(BaseModel):
    codes: list[str]

@router.post("/watchlist/batch-delete")
def batch_remove_stocks(req: BatchDeleteRequest):
    data = load_watchlist()
    stocks = data.get("stocks", [])
    
    to_delete = set(req.codes)
    filtered = [s for s in stocks if s["code"] not in to_delete]
    
    data["stocks"] = filtered
    save_watchlist(data)
    return {"status": "ok", "message": f"成功移除 {len(stocks) - len(filtered)} 只股票"}


# ────────────────────────────────────────
# 分析 Helper
# ────────────────────────────────────────

def _sse(event: str, data: dict | str) -> str:
    payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"

# ────────────────────────────────────────
# 单股分析分析
# ────────────────────────────────────────

@router.post("/watchlist/analyze/single")
async def analyze_single(req: SingleAnalyzeRequest):
    """
    单股流式分析（注入持仓上下文）
    """
    from analyst.engine import StockAnalyst
    analyst = StockAnalyst()

    async def event_generator():
        try:
            yield _sse("event", {"type": "status", "message": f"正在采集 {req.code} 的行情数据..."})
            data = analyst.collect_data(req.code, req.days)

            # Metadata for frontend UI
            meta = {
                "type": "meta",
                "code": data.get("code"),
                "name": data.get("name"),
            }
            tech = data.get("technical", {})
            if "error" not in tech:
                meta["indicators"] = tech.get("indicators", {})
                meta["support_resistance"] = tech.get("support_resistance", {})
                meta["trend"] = tech.get("trend")
                meta["tech_score"] = tech.get("score")
                meta["signals"] = tech.get("signals", [])

            fund = data.get("fundamental", {})
            if "error" not in fund:
                meta["price"] = fund.get("price")
                meta["change_pct"] = fund.get("change_pct")
                meta["valuation"] = fund.get("valuation", {})
                meta["market"] = fund.get("market", {})

            news = data.get("news", {})
            if isinstance(news, dict) and "error" not in news:
                meta["news_count"] = {
                    "stock_news": len(news.get("stock_news", [])),
                    "announcements": len(news.get("announcements", [])),
                    "market_news": len(news.get("market_news", [])),
                }
                meta["latest_news"] = [
                    {"title": n["title"], "date": n["date"][:10]}
                    for n in news.get("stock_news", [])[:3]
                ]

            yield _sse("event", meta)
            yield _sse("event", {"type": "status", "message": "正在调用 AI 进行个性化分析..."})

            # Base prompt
            user_prompt = analyst.build_prompt(data)
            
            # Inject holding context if hold
            if req.holding:
                horizon_map = {"short": "短线交易 (<2周)", "mid": "中线波段 (1-3个月)", "long": "长线投资 (>半年)"}
                horizon_text = horizon_map.get(req.horizon, "未指定")
                
                context = f"""

## 🚨 用户持仓状态 (重要上下文)
用户目前持有该股票，持仓信息如下：
- 持仓均价：{req.cost_price} 元
- 仓位占比：{req.position_pct}%
- 投资周期：{horizon_text}

请在[操作建议]和[风险提示]部分，**务必针对用户的持仓均价、仓位和周期给出个性化建议**。例如：
- 结合当前价和持仓均价的盈亏情况，建议逢高减仓还是逢低加仓。
- 结合阻力支撑位，说明加/减仓甚至止损的具体点位。
- 结合其仓位占比，评估仓位风险是否过高，是否需要控制回撤。"""
                user_prompt += context

            from analyst.llm_client import call_llm
            from analyst.engine import SYSTEM_PROMPT
            
            stream_gen = await call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=4096,
                stream=True,
            )

            async for chunk in stream_gen:
                yield _sse("event", {"type": "token", "content": chunk})

            yield _sse("event", {"type": "done"})

        except Exception as e:
            traceback.print_exc()
            yield _sse("event", {"type": "error", "message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# ────────────────────────────────────────
# 组合分析
# ────────────────────────────────────────

PORTFOLIO_SYSTEM_PROMPT = """你是一位资深的基金经理和财富管理专家，擅长资产配置和投资组合优化。

## 分析要求
你需要对用户目前的股票持仓组合进行全面的"体检"和分析，严格按照以下 Markdown 格式输出：

### 📊 组合健康度
给出总结性的一句话评价（如"仓位偏重且高度集中于新能源，风险极高"），并给出综合健康度评分（1-100分）。

### 🧩 结构与配置分析
- 行业板块集中度评估（是否过于集中单一赛道）。
- 持仓个股间的联动性与同质化风险。
- **总仓位水平**是否合理，是轻仓/重仓/满仓。

### 📋 个股诊断摘要
- 简短点评每只持仓股当前所处的位置（趋势、盈亏情况）。
- 重点指出哪只股票是"定时炸弹"（破位/高估等），哪只是"压舱石"。

### 🎯 调仓与优化建议
- 给出明确的调仓动作（加仓/减仓/清仓/换股）。
- 标明具体的代码和调节方向。
- 建议预留多少现金/可用资金比例。

## 分析原则
1. 必须基于用户提供的所有持仓股数据和仓位信息进行全局视角的分析，而非孤立地看待每一只股票。
2. 毒舌且犀利：如果发现用户的配置显然有重大缺陷（如满仓追高同质化题材），请直言不讳地指出。
3. 给出具有实操性的具体建议。"""

@router.post("/watchlist/analyze/portfolio")
async def analyze_portfolio(req: PortfolioAnalyzeRequest):
    """
    组合流式分析，汇集所有持仓股（或选中的股票）的数据
    """
    from analyst.engine import StockAnalyst
    from stock_picker.picker import StockPicker
    
    analyst = StockAnalyst()
    
    data = load_watchlist()
    
    # 筛选待分析的股票
    if req.codes:
        holdings = [s for s in data.get("stocks", []) if s.get("code") in req.codes]
    else:
        holdings = [s for s in data.get("stocks", []) if s.get("holding")]

    async def event_generator():
        if not holdings:
            yield _sse("event", {"type": "error", "message": "当前没有设置持仓股票，无法进行组合分析"})
            return

        try:
            total_pct = sum(s.get("position_pct", 0) for s in holdings)
            
            yield _sse("event", {"type": "status", "message": f"正在采集合计 {len(holdings)} 只持仓股的数据 (总占比 {total_pct}%)..."})
            
            # Collect data for all holding stocks
            import asyncio
            
            tasks = [asyncio.to_thread(analyst.collect_data, s["code"], req.days) for s in holdings]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Prepare fast market price and summarize holding metrics
            meta_holdings = []
            prompt_data_blocks = []
            
            for i, s in enumerate(holdings):
                res = results[i]
                if isinstance(res, Exception) or res.get("status") != "ok":
                    curr_price = 0.0
                    tech_trend = "未知"
                    fund_pe = "未知"
                else:
                    curr_price = res.get("fundamental", {}).get("price", 0)
                    tech_trend = res.get("technical", {}).get("trend", "未知")
                    fund_pe = res.get("fundamental", {}).get("valuation", {}).get("pe_ttm", "未知")
                    
                    # Cut down news to save prompt tokens
                    tech_snippet = {
                        "trend": res.get("technical", {}).get("trend"),
                        "signals": res.get("technical", {}).get("signals", [])[:3]
                    }
                    
                    block = f"### 股票 {s['code']} ({s['name']})\n"
                    block += f"- 用户建仓成本: {s['cost_price']}元, 当前价: {curr_price}元, 仓位: {s['position_pct']}%, 周期: {s['horizon']}\n"
                    block += f"- 技术面摘要: {json.dumps(tech_snippet, ensure_ascii=False)}\n"
                    block += f"- 基本面市盈率: {fund_pe}\n"
                    prompt_data_blocks.append(block)
                
                meta_holdings.append({
                    "code": s["code"],
                    "name": s["name"],
                    "position_pct": s["position_pct"],
                    "cost_price": s["cost_price"],
                    "curr_price": curr_price,
                    "trend": tech_trend
                })
                
            yield _sse("event", {
                "type": "meta",
                "holdings": meta_holdings,
                "total_pct": total_pct
            })
            
            # Fetch market summary context
            market_context = ""
            try:
                picker = StockPicker()
                df = await asyncio.to_thread(picker.fetch_market_snapshot)
                if not df.empty:
                    up = len(df[df["涨跌幅"] > 0])
                    down = len(df[df["涨跌幅"] < 0])
                    limit_up = len(df[df["涨跌幅"] >= 9.5])
                    limit_down = len(df[df["涨跌幅"] <= -9.5])
                    market_context = f"\n\n**当前市场大盘概况 (实时)**:\n- 全市场上涨: {up} 只，下跌: {down} 只\n- 涨停: {limit_up} 只，跌停: {limit_down} 只\n(以上大盘情绪数据供你参考，以辅助对组合进行整体风控和指导)"
            except Exception as e:
                pass
            
            try:
                from analyst.market_analyzer import MarketAnalyzer
                ma_engine = MarketAnalyzer(days=60)
                ma_result = await asyncio.to_thread(ma_engine.analyze)
                if "error" not in ma_result:
                    market_context += f"\n\n**当前市场深度状态 (多维量化模型)**:\n"
                    market_context += f"- 综合得分: {ma_result.get('total_score', 0):.1f} ({ma_result.get('regime', '未知')})\n"
                    market_context += f"- 趋势得分: {ma_result.get('trend', 0):.1f} | 波动得分: {ma_result.get('volatility', 0):.1f} | 情绪得分: {ma_result.get('sentiment', 0):.1f} | 资金得分: {ma_result.get('capital', 0):.1f}\n"
                    market_context += f"- 量化建议: {ma_result.get('suggestions', {}).get('desc', '')}\n"
            except Exception as e:
                pass
            
            yield _sse("event", {"type": "status", "message": "正在调用 AI 进行组合配置分析..."})
            
            user_prompt = "以下是用户当前的股票持仓组合详情：\n\n"
            user_prompt += f"**总计仓位使用率**: {total_pct}%\n\n"
            user_prompt += "\n".join(prompt_data_blocks)
            user_prompt += market_context
            user_prompt += "\n\n请按照系统设定的专家身份，对上述整个持仓组合进行深度的健康体检和调仓建议。"

            from analyst.llm_client import call_llm
            stream_gen = await call_llm(
                system_prompt=PORTFOLIO_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=4096,
                stream=True,
            )

            async for chunk in stream_gen:
                yield _sse("event", {"type": "token", "content": chunk})

            yield _sse("event", {"type": "done"})

        except Exception as e:
            traceback.print_exc()
            yield _sse("event", {"type": "error", "message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
