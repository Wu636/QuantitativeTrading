from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.ws_manager import manager, data_feed

router = APIRouter()


@router.websocket("/ws/market")
async def websocket_market(websocket: WebSocket):
    """实时行情 WebSocket 端点"""
    await manager.connect(websocket)

    # 如果有缓存数据，先推送一次
    if data_feed.latest_snapshot:
        import json
        from datetime import datetime
        await websocket.send_text(json.dumps({
            "type": "market_snapshot",
            "data": data_feed.latest_snapshot,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }, ensure_ascii=False))

    try:
        while True:
            # 保持连接活跃，接收客户端的 ping 或指令
            msg = await websocket.receive_text()
            # 客户端可以发 "ping" 保活
            if msg == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
