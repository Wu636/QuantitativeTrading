"""
FastAPI 后端 — A股量化交易系统 API

启动方式：
    cd /Users/w/PycharmProjects/QuantitativeTrading
    python -m uvicorn api.app:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import backtest, stock_picker, strategies, walk_forward, analyst

app = FastAPI(
    title="A股量化交易系统",
    description="提供选股、回测、策略对比、Walk-Forward 分析等 API",
    version="1.0.0",
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


@app.get("/")
def root():
    return {"message": "A股量化交易系统 API", "docs": "/docs"}
