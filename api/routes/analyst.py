"""
AI 分析师 API — 流式 SSE 输出 LLM 金融分析报告
"""

import json
import traceback

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(tags=["AI分析师"])


# ────────────────────────────────────────
# 请求模型
# ────────────────────────────────────────

class AnalystRequest(BaseModel):
    code: str = Field(..., description="股票代码，如 000001")
    days: int = Field(365, description="加载历史天数")


# ────────────────────────────────────────
# 流式分析（SSE）
# ────────────────────────────────────────

@router.post("/analyst/stream")
async def analyst_stream(req: AnalystRequest):
    """
    SSE 流式输出 LLM 分析报告。
    前端用 EventSource / fetch + reader 消费。
    """
    from analyst.engine import StockAnalyst

    analyst = StockAnalyst()

    async def event_generator():
        try:
            # 先发送数据采集状态
            yield _sse("event", {"type": "status", "message": f"正在采集 {req.code} 的行情数据..."})

            # 采集数据
            data = analyst.collect_data(req.code, req.days)

            # 发送基本信息
            meta = {
                "type": "meta",
                "code": data.get("code"),
                "name": data.get("name"),
            }
            # 附带技术指标摘要供前端展示卡片
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

            # 消息面摘要
            news = data.get("news", {})
            if isinstance(news, dict) and "error" not in news:
                meta["news_count"] = {
                    "stock_news": len(news.get("stock_news", [])),
                    "announcements": len(news.get("announcements", [])),
                    "market_news": len(news.get("market_news", [])),
                }
                # 发送最新 3 条新闻标题供前端展示
                meta["latest_news"] = [
                    {"title": n["title"], "date": n["date"][:10], "source": n.get("source", "")}
                    for n in news.get("stock_news", [])[:3]
                ]

            yield _sse("event", meta)

            # 发送 LLM 调用开始信号
            yield _sse("event", {"type": "status", "message": "正在调用 AI 分析模型..."})

            # 构造 prompt & 流式调用 LLM
            user_prompt = analyst.build_prompt(data)
            from analyst.llm_client import call_llm

            stream_gen = await call_llm(
                system_prompt=__import__("analyst.engine", fromlist=["SYSTEM_PROMPT"]).SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=4096,
                stream=True,
            )

            async for chunk in stream_gen:
                yield _sse("event", {"type": "token", "content": chunk})

            # 完成信号
            yield _sse("event", {"type": "done"})

        except Exception as e:
            traceback.print_exc()
            yield _sse("event", {"type": "error", "message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ────────────────────────────────────────
# 非流式分析（备用）
# ────────────────────────────────────────

@router.post("/analyst/analyze")
async def analyst_analyze(req: AnalystRequest):
    """非流式，一次性返回完整报告 JSON"""
    from analyst.engine import StockAnalyst

    try:
        analyst = StockAnalyst()
        result = await analyst.analyze(req.code, req.days)
        return {"status": "ok", "data": result}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────
# LLM 配置检查
# ────────────────────────────────────────

@router.get("/analyst/config-check")
def analyst_config_check():
    """检查 LLM 配置是否就绪"""
    from analyst.llm_client import get_llm_config

    cfg = get_llm_config()
    has_key = bool(cfg.get("api_key"))
    has_url = bool(cfg.get("base_url"))
    model = cfg.get("model", "")

    return {
        "ready": has_key and has_url,
        "has_api_key": has_key,
        "has_base_url": has_url,
        "model": model,
    }


# ────────────────────────────────────────
# Helper
# ────────────────────────────────────────

def _sse(event: str, data: dict | str) -> str:
    """格式化一条 SSE 消息"""
    payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"
