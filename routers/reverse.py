from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import uuid
import asyncio
import json
import time
import aiohttp
import re
import os
import shutil
import tiktoken
from starlette.responses import PlainTextResponse

from db import get_db
from models.tokens import Token, increment_count
from utils.register import refresh_silent_cookies
from datetime import datetime, timedelta
import base64
from utils.auth import verify_admin
from env import FILE_DOMAIN
import requests
# 导入账号管理器模块
from utils.account_manager import pick_account, pick_paid_account, release_account
from utils.ws_pool import get_ws, get_msg_queue, remove_msg_queue

# 本地 ws_pool 字典已移至 utils.ws_pool 管理，这里删除旧定义
# ws_pool={} # sid-ws (已废弃)
router = APIRouter(prefix="", tags=["reverse"])

CHAT_WS_URL = "wss://app.chatbetter.com/ws/socket.io/?EIO=4&transport=websocket"

OPENAI_CHAT_COMPLETION_STREAM_DELTA = {
    "id": "chatcmpl-dummy",
    "object": "chat.completion.chunk",
    "created": int(time.time()),
    "model": "gpt-5",
    "choices": [{
        "delta": {"content": ""},
        "index": 0,
        "finish_reason": None
    }]
}

# 图片链接正则表达式
IMAGE_PATTERN = r"!\[.*?\]\(/api/v1/files/([a-f0-9\-]+)/content\)"

# 创建文件目录
FILES_DIR = "static/files"
os.makedirs(FILES_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Async adapter for `websocket-client` (which provides blocking APIs)
# ---------------------------------------------------------------------------

class AsyncWebSocket:
    """Async wrapper around aiohttp.WebSocket connection that mimics the old interface."""
    def __init__(self, ws: aiohttp.ClientWebSocketResponse, session: aiohttp.ClientSession):
        super().__setattr__("_ws", ws)
        super().__setattr__("_session", session)

    async def send(self, data: str):
        # aiohttp 的 send_str 已是协程，无需线程池
        await self._ws.send_str(data)

    async def recv(self) -> str:
        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            return msg.data
        if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
            return None
        # 其它类型（如 PING/PONG/BINARY）目前不需要，返回空串
        return ""

    async def close(self):
        await self._ws.close()
        await self._session.close()

    # Allow `async for` usage
    def __aiter__(self):
        return self

    async def __anext__(self):
        msg = await self.recv()
        if msg is None:
            raise StopAsyncIteration
        return msg

    # Let callers set / get arbitrary attributes (e.g., sid, account)
    def __getattr__(self, item):
        return getattr(self._ws, item)

    def __setattr__(self, name, value):
        if name in {"_ws", "_session"}:
            super().__setattr__(name, value)
        else:
            super().__setattr__(name, value)

# 下载并保存图片
async def download_and_save_image(file_id: str, headers: Dict[str, str]) -> str:
    """
    下载并保存图片，返回本地文件路径
    """
    try:
        # 检查文件是否已存在
        local_path = os.path.join(FILES_DIR, f"{file_id}")
        if os.path.exists(local_path):
            # 如果文件已存在且大小大于0，直接返回链接
            if os.path.getsize(local_path) > 0:
                return f"{FILE_DOMAIN}/files/{file_id}"
            else:
                # 文件存在但大小为0，可能是之前下载失败，删除重新下载
                os.remove(local_path)
            
        # 下载文件
        async with aiohttp.ClientSession() as client:
            async with client.get(
                f"https://app.chatbetter.com/api/v1/files/{file_id}/content",
                headers=headers,
                timeout=30.0  # 30秒超时
            ) as response:
                if response.status == 200:
                    # 保存文件
                    with open(local_path, "wb") as f:
                        f.write(await response.read())
                    return f"{FILE_DOMAIN}/files/{file_id}"
                else:
                    print(f"下载图片失败: {response.status}")
                    return f"/api/v1/files/{file_id}/content"  # 返回原始链接
    except Exception as e:
        print(f"处理图片时出错: {str(e)}")
        return f"/api/v1/files/{file_id}/content"  # 出错时返回原始链接

# 替换内容中的图片链接
async def replace_image_links(content: str, headers: Dict[str, str], processed_image_ids: set = None) -> str:
    """
    替换内容中的图片链接为本地链接
    processed_image_ids: 可选参数，已处理过的图片ID集合，用于避免重复处理
    """
    if not content:
        return content
    
    # 如果没有提供已处理图片ID集合，则创建一个空集合
    if processed_image_ids is None:
        processed_image_ids = set()
        
    # 查找所有图片链接
    matches = re.finditer(IMAGE_PATTERN, content)
    new_content = content
    
    for match in matches:
        original_text = match.group(0)
        file_id = match.group(1)

        # 先确定本地链接
        if file_id in processed_image_ids:
            # 已下载的图片, 直接构造本地链接, 无需再次下载
            local_url = f"{FILE_DOMAIN}/files/{file_id}"
        else:
            # 未处理过的图片, 先下载
            local_url = await download_and_save_image(file_id, headers)
            # 标记为已处理, 避免重复下载
            processed_image_ids.add(file_id)

        # 替换链接 (无论新旧都执行, 保证内容一致)
        if local_url:
            new_link = original_text.replace(f"/api/v1/files/{file_id}/content", local_url)
            new_content = new_content.replace(original_text, new_link)
    
    return new_content

# 新增: 将 <details type="reasoning"> 块转换为 <think> 标签
def convert_reasoning_details(content: str) -> str:
    """
    将 <details type="reasoning"> 结构转换为 <think> 标签。

    规则:
    1. done="false": 用 <think> 替换开头 details 标签及其 summary，并删除末尾 </details>。
    2. done="true": 用 <think> 替换开头 details 标签及其 summary，并把末尾 </details> 改为 </think>。
    """
    if not content:
        return content

    # 处理 done="true"，保留内部内容并在末尾加 </think>
    pattern_true = re.compile(
        r'<details type="reasoning" done="true" duration="[^\"]*">\s*<summary>.*?</summary>(.*?)\n</details>',
        re.DOTALL)
    content = pattern_true.sub(lambda m: f"<think>{m.group(1)}\n</think>", content)

    # 处理 done="false"，仅替换开头，不加闭合标签
    pattern_false = re.compile(
        r'<details type="reasoning" done="false">\s*<summary>.*?</summary>(.*?)\n</details>',
        re.DOTALL)
    content = pattern_false.sub(lambda m: f"<think>{m.group(1)}", content)

    return content

@router.get("/v1/models")
async def get_models(_: bool = Depends(verify_admin)):
    """返回支持的模型列表"""
    try:
        # 读取models.json文件
        models_path = os.path.join(os.path.dirname(__file__), "models.json")
        with open(models_path, "r", encoding="utf-8") as f:
            models_data = json.load(f)
        return models_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load models: {str(e)}")

async def ensure_socket_connection(account: Token) -> Optional["AsyncWebSocket"]:
    start_time = time.time()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Cookie": f"token={account.token}; ChatBetterJwt={account.access_token}",
        "Origin": "https://app.chatbetter.com",
    }
    origin_hdr = headers.pop("Origin", None)

    try:
        timeout = aiohttp.ClientTimeout(total=60)
        session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        ws = await session.ws_connect(CHAT_WS_URL, origin=origin_hdr)
        duration = time.time() - start_time
        print(f"WebSocket connection established in {duration:.2f}s")
        return AsyncWebSocket(ws, session)
    except Exception as e:
        if 'session' in locals():
            await session.close()
        duration = time.time() - start_time
        print(f"WebSocket connection failed after {duration:.2f}s: {e}")
        return None

async def refresh_account_cookies(db: Session, account: Token) -> bool:
    cookies_dict = json.loads(account.silent_cookies or "{}")
    # 使用线程池执行阻塞的同步 HTTP 请求，避免阻塞事件循环
    loop = asyncio.get_running_loop()
    success, new_cookies, new_access_token = await loop.run_in_executor(
        None, refresh_silent_cookies, cookies_dict
    )
    if not success:
        account.enable = 0
        db.commit()
        return False
    account.silent_cookies = json.dumps(new_cookies)
    account.access_token = new_access_token
    account.cookies_expires = datetime.now() + timedelta(days=30)
    # 刷新成功后，将 token_expires 置为 15 分钟后，避免短时间内重复刷新
    account.token_expires = datetime.now() + timedelta(minutes=15)
    db.commit()
    return True

async def get_authed_socket(account: Token) -> Optional["AsyncWebSocket"]:
    """建立并认证一个websocket连接"""
    ws = await ensure_socket_connection(account)
    if ws:
        try:
            # 发送token进行认证
            await ws.recv()  # 舍弃掉第一条 0{"sid":"xxxx",...}
            t = json.dumps({"token": account.token},separators=(',', ':'))
            await ws.send(f"40{t}")
            # 等待回应
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            # 处理带前缀数字的消息格式，如"40{"sid":"xxxx"}"
            if msg.startswith("40{\"sid\""):
                msg_json = msg[2:]  # 去掉"40"前缀
                data = json.loads(msg_json)
                if isinstance(data, dict) and data.get("sid"):
                    ws.sid = data["sid"]
                    ws.account = account
                    return ws
        except Exception:
            pass # 发生任何异常，都视为失败
        
        # 如果认证失败或发生异常，关闭连接
        await ws.close()
    return None

# 检查模型是否支持图像输出
def is_image_output_model(model_name: str) -> bool:
    try:
        models_path = os.path.join(os.path.dirname(__file__), "models.json")
        with open(models_path, "r", encoding="utf-8") as f:
            models_data = json.load(f)
        
        for model in models_data.get("data", []):
            if model.get("id") == model_name or model.get("name") == model_name:
                modalities = model.get("info", {}).get("meta", {}).get("modalities", {})
                output_modalities = modalities.get("output", [])
                if "image" in output_modalities:
                    return True
        return False
    except Exception:
        # 如果发生任何错误，默认返回False
        return False

@router.post("/v1/chat/completions")
async def chat_completions(request: Request, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    time1=int(time.time()*1000)
    time2: int
    time3: int
    time4: int
    body = await request.json()
    messages: List[Dict[str, Any]] = body.get("messages", [])
    model = body.get("model", "gpt-5")
    # 检测用户请求是否需要流式响应
    stream = body.get("stream", False)

    if not messages:
        raise HTTPException(status_code=400, detail="messages required")
    last_message = messages[-1]

    # 计算所有消息的token数量
    def count_message_tokens(messages: List[Dict[str, Any]]) -> int:
        """计算消息列表的token数量"""
        try:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            token_count = 0
            
            for message in messages:
                content = message.get("content", "")
                if isinstance(content, list):
                    # 处理多模态内容
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                    content = "\n".join(text_parts)
                
                # 计算当前消息的token
                if isinstance(content, str):
                    token_count += len(encoding.encode(content))
                    
                # 添加角色token (每条消息大约需要额外4个token)
                token_count += 4
            
            return token_count
        except Exception as e:
            print(f"Token计算错误: {str(e)}")
            return 0  # 出错时返回0，使用普通账号
    
    # 计算token并选择适当的账号
    token_count = count_message_tokens(messages)
    
    # 如果token数大于8192，使用付费账号，否则使用普通账号
    if token_count > 8192:
        account = await pick_paid_account(db)
    else:
        account = await pick_account(db)
    
    ws = None
    new_data = None
    attempts = 0
    try:
        while attempts < 5:
            # 构造 /api/v1/chats/new 请求
            adapt_messages = {}
            last_id = None
            current_id = None
            for msg in messages[:-1]:
                msg_id = str(uuid.uuid4())
                current_id = msg_id
                # 构造符合 ChatBetter 格式的历史消息
                # content 可能是 list 或 str
                # 如果前端传来的content是list，则需要把content中type为"text"的值作为content, 其它的忽略。type为"image_url"的要特殊处理，要在"files"插入{"type":"image","url":image_url.url}
                content = msg.get("content", "")
                # 确保有 files 字段，方便后续追加图片
                if "files" not in msg:
                    msg["files"] = []

                # 前端可能把同一条消息拆分为多段文本和图片，统一在这里合并
                if isinstance(content, list):
                    text_parts: List[str] = []
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        typ = item.get("type")
                        if typ == "image_url":
                            # 前端的图片结构为 {"type":"image_url","image_url":{"url": "..."}}
                            image_url = item.get("image_url", {}).get("url") or item.get("url")
                            if image_url:
                                msg["files"].append({"type": "image", "url": image_url})
                        elif typ == "text":
                            text_parts.append(item.get("text", ""))
                    msg["content"] = "\n".join(text_parts)

                # 检查模型是否支持图像输出
                output_type = "image-generation" if is_image_output_model(model) else "quick_answer"

                adapt_msg = {
                    "id": msg_id,
                    "parentId": last_id,
                    "childrenIds": [],  # 暂时置空，稍后设置
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "files": msg.get("files", []),
                    "timestamp": int(time.time() * 1000),
                    "outputType": output_type,
                    "models": [model]
                }
                # 更新上一条消息的 childrenIds 以指向当前消息
                if last_id is not None and last_id in adapt_messages:
                    adapt_messages[last_id]["childrenIds"] = [msg_id]
                adapt_messages[msg_id] = adapt_msg
                last_id = msg_id
            
            if len(messages) == 1:
                # 如果只有一条message，则插入两个message，防止系统修改自己的prompt
                output_type = "image-generation" if is_image_output_model(model) else "quick_answer"
                user_msg_id = str(uuid.uuid4())
                asst_msg_id = str(uuid.uuid4())

                user_msg = {
                    "id": user_msg_id,
                    "parentId": None,
                    "childrenIds": [asst_msg_id],
                    "role": "user",
                    "content": " ",
                    "files": [],
                    "timestamp": int(time.time() * 1000),
                    "outputType": output_type,
                    "models": [model]
                }
                adapt_messages[user_msg_id] = user_msg

                asst_msg = {
                    "id": asst_msg_id,
                    "parentId": user_msg_id,
                    "childrenIds": [],
                    "role": "assistant",
                    "content": " ",
                    "files": [],
                    "timestamp": int(time.time() * 1000),
                    "outputType": output_type,
                    "models": [model]
                }
                adapt_messages[asst_msg_id] = asst_msg
                
                last_id = asst_msg_id
                current_id = asst_msg_id
            
            new_payload = {
                "chat": {
                    "id": "",
                    "title": "新对话",
                    "models": [model],
                    "params": {},
                    "history": {
                        "currentId": current_id,
                        "messages": adapt_messages
                    },
                    "messages": [],
                    "tags": [],
                    "timestamp": int(time.time()*1000)
                }
            }
            headers = {
                "Authorization": f"Bearer {account.token}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                "Cookie": f"token={account.token}; ChatBetterJwt={account.access_token}",
                "Content-Type": "application/json"
            }

            time2=int(time.time()*1000)

            async with aiohttp.ClientSession() as client:
                new_chat_task = client.post(
                    "https://app.chatbetter.com/api/v1/chats/new", 
                    json=new_payload, 
                    headers=headers,
                    timeout=60.0  # 60秒超时
                )
                ws_task = get_authed_socket(account)
                
                results = await asyncio.gather(new_chat_task, ws_task, return_exceptions=True)
                new_resp_or_exc, ws_or_exc = results

            ws_success = not isinstance(ws_or_exc, Exception) and ws_or_exc is not None
            chat_success = not isinstance(new_resp_or_exc, Exception) and hasattr(new_resp_or_exc, "status") and new_resp_or_exc.status in [200, 201]

            # 如果成功，提前解析 response.json()，避免 session 关闭导致连接关闭错误
            if chat_success and not isinstance(new_resp_or_exc, Exception):
                try:
                    new_data_temp = await new_resp_or_exc.json()
                except Exception:
                    new_data_temp = None
            else:
                new_data_temp = None

            time3=int(time.time()*1000)

            if ws_success and chat_success and new_data_temp is not None:
                ws = ws_or_exc
                new_data = new_data_temp
                break # 成功，跳出循环

            # 如果失败，关闭可能已建立的ws连接
            if ws_success:
                await ws_or_exc.close()
            
            # 尝试刷新cookies，如果失败则更换账号
            if not await refresh_account_cookies(db, account):
                # 在更换账号前释放当前账号
                release_account(account.id)
                if token_count > 8192:
                    account = await pick_paid_account(db)
                else:
                    account = await pick_account(db)
            
            attempts += 1
        
        if not ws or not new_data:
            release_account(account.id)
            raise HTTPException(status_code=503, detail="Unable to establish connection and create chat after several retries")

        account = ws.account
        sid = ws.sid
        chat_id = new_data["id"]
        # Get the dedicated message queue associated with this chat
        queue = get_msg_queue(chat_id)
        current_id = new_data["chat"]["history"]["currentId"]

        # 处理最后一条消息（即当前用户提问）的 content 与 files
        last_content = last_message.get("content", "")
        if "files" not in last_message:
            last_message["files"] = []
        if isinstance(last_content, list):
            text_parts: List[str] = []
            for item in last_content:
                if not isinstance(item, dict):
                    continue
                typ = item.get("type")
                if typ == "image_url":
                    image_url = item.get("image_url", {}).get("url") or item.get("url")
                    if image_url:
                        last_message["files"].append({"type": "image", "url": image_url})
                elif typ == "text":
                    text_parts.append(item.get("text", ""))
            last_message["content"] = "\n".join(text_parts)

        # 检查模型是否支持图像输出
        output_type = "image-generation" if is_image_output_model(model) else "quick_answer"

        # 构造patch数据
        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())
        patch_payload = {
            "generate_tags": False,
            "generate_title": False,
            "currentId": uuid1,
            "messages": [
                {
                    "id": uuid2,
                    "parentId": current_id,
                    "childrenIds": [uuid1],
                    "role": "user",
                    "content": last_message["content"],
                    "files": last_message.get("files", []),
                    "timestamp": int(time.time()),
                    "models": [model],
                    "outputType": output_type
                },
                {
                    "parentId": uuid2,
                    "id": uuid1,
                    "childrenIds": [],
                    "role": "assistant",
                    "content": "",
                    "model": model,
                    "modelName": model,
                    "modelIdx": 0,
                    "timestamp": int(time.time())
                }
            ],
            "session_id": sid,
            "stream": True,
            "tool_servers": [],
            "features": {
                "image_generation": is_image_output_model(model),
                "code_interpreter": False,
                "web_search": False
            },
            "params": {},
            "variables": {}
        }

        time4=int(time.time()*1000)
        print(f"-------------\n"
              f"进入到ws之前 {time2-time1}\n"
              f"ws花费 {time3-time2}\n"
              f"进入到ws之后 {time3-time1}\n"
              f"ws到patch之前 {time4-time2}\n"
              f"进入到patch之前 {time4-time1}")

        # 发送patch
        async with aiohttp.ClientSession() as client:
            patch_resp = await client.patch(
                f"https://app.chatbetter.com/api/v1/chats/{chat_id}",
                json=patch_payload, 
                headers=headers,
                timeout=60.0  # 增加超时时间到60秒
            )
        if patch_resp.status != 200 and patch_resp.status != 201:
            await ws.close()
            raise HTTPException(status_code=502, detail="Patch chat failed")

        # 准备StreamingResponse
        from fastapi.responses import StreamingResponse, JSONResponse

        async def stream_generator():
            # 记录已经发送给客户端的完整内容，用于计算增量
            last_sent_content = ""  # 已发送的完整内容
            processed_image_ids = set()  # 已处理过的图片ID集合
            try:
                start_chunk = {
                    "id": "chatcmpl-dummy",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "delta": {
                                "content": "",
                                "role": "assistant"
                            },
                            "logprobs": None,
                            "finish_reason": None,
                            "index": 0
                        }
                    ],
                    "usage": None
                }
                yield f"data: {json.dumps(start_chunk,separators=(',', ':'))}\n\n"

                # 监听ws消息并流式返回
                async for raw_msg in ws:
                    print(raw_msg.encode("utf-8"))
                    # 处理带前缀数字的消息格式，如"42[\"chat-events\",{...}]"
                    if raw_msg == "2":
                        await ws.send("3")
                    if raw_msg.startswith("42") and "chat-events" in raw_msg:
                        # 提取json部分
                        try:
                            # 去掉"42"前缀
                            msg_json = raw_msg[2:]
                            parts = json.loads(msg_json)
                            if isinstance(parts, list) and len(parts) == 2:
                                data = parts[1].get("data", {})
                                if data.get("type") == "chat:completion":
                                    chunk = data.get("data", {})
                                    full_content = chunk.get("content", "")

                                    error=chunk.get("error")
                                    if error:
                                        print(f"{account.account}----{error}")
                                        raise HTTPException(status_code=502, detail="服务端出错")
                                    if not full_content:
                                        continue # 跳过空content

                                    finish = chunk.get("done")

                                    # 检查内容中是否包含图片链接，如果有则处理
                                    if "![" in full_content and "/api/v1/files/" in full_content:
                                        full_content = await replace_image_links(full_content, headers, processed_image_ids)
                                    # 替换 reasoning 详情块为 <think> 标记
                                    full_content = convert_reasoning_details(full_content)

                                    # 仅将增量部分发送给客户端，避免重复
                                    # 使用公共前缀算法，兼容内容长度的增减，避免遗漏字符
                                    common_prefix_len = 0
                                    for a, b in zip(last_sent_content, full_content):
                                        if a == b:
                                            common_prefix_len += 1
                                        else:
                                            break
                                    delta_content = full_content[common_prefix_len:]
                                    last_sent_content = full_content
                                    if finish:
                                        # 发送结束 chunk
                                        end_chunk = {
                                            "id": "chatcmpl-dummy",
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": model,
                                            "choices": [{
                                                "delta": {},
                                                "logprobs": None,
                                                "finish_reason": "stop",
                                                "index": 0,
                                            }],
                                            "usage": None
                                        }
                                        yield f"data: {json.dumps(end_chunk,separators=(',', ':'))}\n\n"
                                        yield "data: [DONE]\n\n"
                                        break
                                    if delta_content:
                                        openai_chunk = {
                                            "id": "chatcmpl-dummy",
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": model,
                                            "choices": [{
                                                "delta": {"content": delta_content},
                                                "logprobs": None,
                                                "finish_reason": None,
                                                "index": 0
                                            }],
                                            "usage": None
                                        }
                                        yield f"data: {json.dumps(openai_chunk)}\n\n"

                                    usage = chunk.get("usage",{})
                                    if usage:
                                        usage_chunk = {
                                            "id": "chatcmpl-dummy",
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": model,
                                            "choices": [{
                                                "delta": {},
                                                "index": 0
                                            }],
                                            "usage": usage
                                        }
                                        yield f"data: {json.dumps(usage_chunk,separators=(',', ':'))}\n\n"

                        except Exception:
                            continue
            finally:
                # 确保无论如何都释放账号锁定
                release_account(account.id)
                # 确保关闭WebSocket连接
                if ws:
                    try:
                        await ws.close()
                    except:
                        pass

        # 非流式响应收集器
        async def collect_full_response():
            full_content = ""
            final_usage = {}
            processed_image_ids = set()  # 已处理过的图片ID集合
            try:
                # 监听ws消息并收集完整响应
                async for raw_msg in ws:
                    # 处理带前缀数字的消息格式，如"42[\"chat-events\",{...}]"
                    if raw_msg == "2":
                        await ws.send("3")
                    if raw_msg.startswith("42") and "chat-events" in raw_msg:
                        # 提取json部分
                        try:
                            # 去掉"42"前缀
                            msg_json = raw_msg[2:]
                            parts = json.loads(msg_json)
                            if isinstance(parts, list) and len(parts) == 2:
                                data = parts[1].get("data", {})
                                if data.get("type") == "chat:completion":
                                    chunk = data.get("data", {})
                                    full_content = chunk.get("content", "")

                                    error = chunk.get("error")
                                    if error:
                                        print(f"{account.account}----{error}")
                                        raise HTTPException(status_code=502, detail="服务端出错")
                                    if not full_content:
                                        continue # 跳过空content
                                    usage = chunk.get("usage", {})
                                    if usage:
                                        final_usage = usage
                                    if chunk.get("done"):
                                        break
                        except Exception:
                            continue
            finally:
                # 确保关闭WebSocket连接
                if ws:
                    try:
                        await ws.close()
                    except:
                        pass
        
            # 处理图片链接
            if "![" in full_content and "/api/v1/files/" in full_content:
                full_content = await replace_image_links(full_content, headers, processed_image_ids)
            # 替换 reasoning 详情块为 <think> 标记
            full_content = convert_reasoning_details(full_content)
            
            # 构造非流式响应格式
            complete_response = {
                "id": f"chatcmpl-{str(uuid.uuid4())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": full_content
                        },
                        "finish_reason": "stop"
                    }
                ]
            }
            
            # 如果有usage数据，添加到响应中
            if final_usage:
                complete_response["usage"] = final_usage
                
            return complete_response

        # 根据请求类型返回流式或非流式响应
        if stream:
            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            try:
                # 非流式请求，等待收集完整响应后返回
                full_response = await collect_full_response()
                return JSONResponse(content=full_response)
            finally:
                # 释放账号锁定
                release_account(account.id)
                # 关闭WebSocket连接
                if ws:
                    try:
                        await ws.close()
                    except:
                        pass
    except Exception as e:
        # 发生异常时也要确保释放账号
        if account:
            release_account(account.id)
        # 关闭WebSocket连接
        if ws:
            try:
                await ws.close()
            except:
                pass
        raise