from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from analyst.market_analyzer import MarketAnalyzer, MarketAnalyzerLLM

router = APIRouter(
    prefix="/market",
    tags=["市场状态分析"],
)

@router.get("/status")
def get_market_status():
    """获取纯量化市场状态分析，毫秒级响应"""
    analyzer = MarketAnalyzer()
    result = analyzer.analyze()
    return result

@router.get("/status/llm")
async def get_market_status_llm():
    """获取 LLM 增强市场状态分析，SSE 流式输出"""
    analyzer = MarketAnalyzerLLM()
    
    async def event_generator():
        # analyzer.analyze_stream() 首先 yield 返回纯量化指标字典（转成了JSON文本），
        # 后面紧接着 yield LLM 的 Markdown 文本块。
        # 为了兼容前端 SSE 解析，我们把所有内容都发过去。
        async for chunk in analyzer.analyze_stream():
            yield f"data: {chunk}\n\n"
        
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
