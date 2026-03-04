"""
FastAPI 后端 — A股量化交易系统 API

启动方式：
    cd /Users/w/PycharmProjects/QuantitativeTrading
    python -m uvicorn api.app:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import backtest, stock_picker, strategies, walk_forward, analyst, market, timing_picker, watchlist
from api.routes import ws_routes
from api.ws_manager import data_feed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：启动后台行情轮询
    data_feed.start()
    yield
    # 关闭时：停止后台任务
    data_feed.stop()


app = FastAPI(
    title="A股量化交易系统",
    description="提供选股、回测、策略对比、Walk-Forward 分析等 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — 允许前端 dev server 访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(backtest.router, prefix="/api")
app.include_router(stock_picker.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(walk_forward.router, prefix="/api")
app.include_router(analyst.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(timing_picker.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")

# WebSocket 路由（无 /api 前缀）
app.include_router(ws_routes.router)


@app.get("/")
def root():
    return {"message": "A股量化交易系统 API", "docs": "/docs"}

