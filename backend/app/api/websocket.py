"""WebSocket 实时推送：把服务层事件广播给订阅该任务的面板连接"""
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import task_service

logger = logging.getLogger(__name__)
router = APIRouter()

# task_id -> [queue, ...]：工作流线程向队列投递事件，WS 协程消费
_subscribers: dict[int, list] = {}
_loop: asyncio.AbstractEventLoop | None = None


def broadcast(task_id: int, event: dict) -> None:
    """由工作流线程调用（线程安全：通过 loop.call_soon_threadsafe 投递）"""
    if _loop is None:
        return
    for q in list(_subscribers.get(task_id, [])):
        async def _put(q=q):
            await q.put(event)
        _loop.call_soon_threadsafe(asyncio.ensure_future, _put())


task_service.register_broadcaster(broadcast)


@router.websocket("/ws/{task_id}")
async def ws_task(websocket: WebSocket, task_id: int):
    global _loop
    _loop = asyncio.get_running_loop()
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(task_id, []).append(queue)
    logger.info("WS 订阅: task=%s", task_id)
    try:
        # 先发一条连接成功
        await websocket.send_json({"type": "connected", "task_id": task_id})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25.0)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info("WS 断开: task=%s", task_id)
    finally:
        try:
            _subscribers.get(task_id, []).remove(queue)
        except ValueError:
            pass
