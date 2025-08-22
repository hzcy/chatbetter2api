from typing import Dict, Any, Callable
import asyncio
import json

# This module maintains two global pools:
# 1. ws_pool:   account(str) -> {"sid": str, "ws": AsyncWebSocket}
# 2. msg_pool:  chat_id(str) -> asyncio.Queue that stores completion chunks coming from the websocket stream

ws_pool: Dict[str, Dict[str, Any]] = {}
msg_pool: Dict[str, asyncio.Queue] = {}

_pool_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_or_create_queue(chat_id: str) -> asyncio.Queue:
    if chat_id not in msg_pool:
        msg_pool[chat_id] = asyncio.Queue()
    return msg_pool[chat_id]

async def _ws_listener(account_key: str):
    """Background task that listens on a websocket and dispatches messages to msg_pool.
    It shuts itself down when the websocket closes or raises an exception.
    """
    ws_entry = ws_pool.get(account_key)
    if not ws_entry:
        return  # Nothing to listen on
    ws = ws_entry["ws"]

    try:
        async for raw_msg in ws:
            # Keep-alive ping-pong
            if raw_msg == "2":
                await ws.send("3")
                continue

            if raw_msg.startswith("42") and "chat-events" in raw_msg:
                try:
                    msg_json = raw_msg[2:]  # strip "42"
                    parts = json.loads(msg_json)
                    if not (isinstance(parts, list) and len(parts) == 2):
                        continue
                    payload = parts[1]
                    chat_id = payload.get("chat_id")
                    data = payload.get("data", {})
                    if not chat_id:
                        continue

                    # Only interested in chat:completion chunks
                    if data.get("type") != "chat:completion":
                        continue

                    chunk = data.get("data", {})
                    queue = _get_or_create_queue(chat_id)
                    await queue.put(chunk)
                except Exception:
                    continue  # Ignore malformed messages
    except Exception as e:
        # Propagate exception to consumers via queue (optional)
        pass
    finally:
        # Clean up pools on websocket closure
        async with _pool_lock:
            ws_pool.pop(account_key, None)
        # Close all pending queues (alert consumers)
        for chat_id, queue in list(msg_pool.items()):
            if queue.empty():
                continue
            await queue.put({"error": "ws_closed"})

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_ws(account: Any, ws_factory: Callable[[Any], "AsyncWebSocket"]):
    """Return an authenticated websocket for the given account. If the account already
    has a live websocket, reuse it; otherwise, create one with *ws_factory*.
    This function is concurrency-safe.
    """
    account_key = getattr(account, "account", str(getattr(account, "id", "")))

    # Double-checked locking pattern to avoid creating multiple websockets.
    if account_key in ws_pool and not ws_pool[account_key]["ws"].closed:
        return ws_pool[account_key]["ws"]

    async with _pool_lock:
        # Re-check inside lock
        if account_key in ws_pool and not ws_pool[account_key]["ws"].closed:
            return ws_pool[account_key]["ws"]

        # Create new websocket via provided factory
        ws = await ws_factory(account)
        if ws is None:
            raise RuntimeError("Failed to create websocket for account")

        ws_pool[account_key] = {"sid": ws.sid, "ws": ws}
        # Launch background listener
        asyncio.create_task(_ws_listener(account_key))
        return ws

def get_msg_queue(chat_id: str) -> asyncio.Queue:
    """Return (and create if necessary) the message queue for *chat_id*."""
    return _get_or_create_queue(chat_id)

def remove_msg_queue(chat_id: str):
    """Remove queue for chat_id when no longer needed."""
    msg_pool.pop(chat_id, None) 