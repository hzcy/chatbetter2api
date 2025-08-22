import uuid

from fastapi import APIRouter, Depends, Body, HTTPException, BackgroundTasks, Query, Header
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import threading
import time
from datetime import datetime, timedelta
import json
import base64
import re
import uuid as uuid_lib
from concurrent.futures import ThreadPoolExecutor, as_completed
from env import REGISTER_MAX_THREADS
from utils.auth import verify_admin

from db import get_db
from models import tokens
from utils.register import register_chatbetter, activate_account, fetch_auth_info, signin_with_access_token
from utils.register import login_account
from utils.outlook_util import OutlookAccount, OutlookMailManager

# 创建路由器
router = APIRouter(
    prefix="/api/register",
    tags=["register"],
    responses={404: {"description": "Not found"}},
)

# 全局变量，用于记录邮箱注册状态
registration_status = {}

# 批量刷新状态跟踪
batch_refresh_status = {}

class BatchRefreshRequest(BaseModel):
    include_disabled: bool = False
    thread_count: int = 5

class BatchRefreshResponse(BaseModel):
    task_id: str
    count: int

# 辅助函数：检查字符串是否为UUID格式
def is_uuid(s: str) -> bool:
    """检查字符串是否为标准UUID格式"""
    try:
        uuid_obj = uuid_lib.UUID(s)
        return str(uuid_obj) == s
    except (ValueError, AttributeError, TypeError):
        return False

# 请求模型
class BulkRegisterRequest(BaseModel):
    data: str
    thread_count: int = 5

# 响应模型
class BulkRegisterResponse(BaseModel):
    task_id: str
    count: int
    parsed_data: List[Dict[str, Any]]

# Cookie处理函数
def parse_cookie_expiration(cookie_str: str) -> Optional[datetime]:
    """从cookie字符串中解析过期时间"""
    try:
        expires_match = re.search(r'expires=([^;]+)', cookie_str)
        if expires_match:
            expires_str = expires_match.group(1)
            # 解析各种可能的日期格式
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(expires_str)
            except:
                try:
                    import dateutil.parser
                    return dateutil.parser.parse(expires_str)
                except:
                    # 如果无法解析，设置默认过期时间为30天后
                    return datetime.now() + timedelta(days=30)
        return datetime.now() + timedelta(days=30)  # 默认30天
    except Exception as e:
        print(f"解析Cookie过期时间失败: {e}")
        return datetime.now() + timedelta(days=30)  # 默认30天

# 后台处理函数
def process_registrations(task_id: str, email_data: List[Dict[str, Any]], db_session, thread_count: int):
    """处理批量注册请求的后台线程函数"""
    print(f"[Register] 开始处理批量注册任务 {task_id}, 共 {len(email_data)} 个邮箱")
    registration_status[task_id] = {
        "total": len(email_data),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "status": "processing",
        "details": {}
    }
    
    # 使用线程池并发处理
    lock = threading.Lock()

    def handle_registration(item):
        email = item.get("account")
        password = item.get("password")
        refresh_token = item.get("token")
        client_id = item.get("uuid")

        if not all([email, password, refresh_token, client_id]):
            with lock:
                registration_status[task_id]["failed"] += 1
                registration_status[task_id]["details"][email] = "缺少必要参数"
            return

        try:
            print(f"[Register] 正在处理邮箱: {email}")
            with lock:
                registration_status[task_id]["details"][email] = "处理中..."

            # 1. 注册账号
            register_success, reg_err = register_chatbetter(email)
            if not register_success:
                # 注册失败后，尝试使用登录流程
                print(f"[Register] 注册失败，尝试登录流程: {email}")
                outlook_account = OutlookAccount(email, password, refresh_token, client_id)
                login_result, login_err = login_account(email, outlook_account)

                if not login_result:
                    with lock:
                        registration_status[task_id]["failed"] += 1
                        registration_status[task_id]["details"][email] = f"注册失败且登录失败: {reg_err}; {login_err}"
                    return

                # 登录成功，保存数据
                token_data = {
                    "account": email,
                    "cookies": login_result.get("cookies"),
                    "access_token": login_result.get("access_token"),
                    "token": login_result.get("token")
                }

                local_db = next(get_db())
                try:
                    tokens.create_token(local_db, token_data)
                    with lock:
                        registration_status[task_id]["success"] += 1
                        registration_status[task_id]["details"][email] = "登录成功"
                except Exception as e:
                    print(f"[Register] 保存登录数据失败: {e}")
                    with lock:
                        registration_status[task_id]["failed"] += 1
                        registration_status[task_id]["details"][email] = f"保存登录数据失败: {str(e)}"
                finally:
                    local_db.close()
                return

            # 2. 创建Outlook账号对象
            outlook_account = OutlookAccount(email, password, refresh_token, client_id)
            om_local = OutlookMailManager()

            # 3. 获取激活链接
            print(f"[Register] 获取激活链接: {email}")
            magic_link_result = om_local.get_magic_link(outlook_account)

            if magic_link_result["type"] != "True" or not magic_link_result.get("link"):
                with lock:
                    registration_status[task_id]["failed"] += 1
                    registration_status[task_id]["details"][email] = "获取激活链接失败"
                return

            activation_link = magic_link_result["link"]
            print(f"[Register] 获取到激活链接: {activation_link[:50]}...")

            # 4. 激活账号并获取Cookie和Token
            activation_result, act_err = activate_account(activation_link)

            if not activation_result:
                with lock:
                    registration_status[task_id]["failed"] += 1
                    registration_status[task_id]["details"][email] = f"激活失败: {act_err}"
                return

            # 5. 存储到数据库（使用独立会话）
            token_data = {
                "account": email,
                "cookies": activation_result.get("cookies"),
                "access_token": activation_result.get("access_token"),
                "token": activation_result.get("token")
            }

            local_db = next(get_db())
            try:
                tokens.create_token(local_db, token_data)

                with lock:
                    if activation_result.get("token"):
                        registration_status[task_id]["success"] += 1
                        registration_status[task_id]["details"][email] = "注册成功"
                    else:
                        registration_status[task_id]["failed"] += 1
                        registration_status[task_id]["details"][email] = "注册部分成功，但未获取到token"
            except Exception as e:
                print(f"[Register] 保存到数据库失败: {e}")
                with lock:
                    registration_status[task_id]["failed"] += 1
                    registration_status[task_id]["details"][email] = f"保存到数据库失败: {str(e)}"
            finally:
                local_db.close()

        except Exception as e:
            print(f"[Register] 处理邮箱 {email} 时发生错误: {str(e)}")
            with lock:
                registration_status[task_id]["failed"] += 1
                registration_status[task_id]["details"][email] = f"处理错误: {str(e)}"
        finally:
            # 只在这里增加一次processed计数
            with lock:
                registration_status[task_id]["processed"] += 1

    # 创建线程池并发执行
    # 限制线程数范围在1-20之间
    thread_count = min(20, max(1, thread_count))
    print(f"[Register] 使用 {thread_count} 个线程处理注册任务")
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = [executor.submit(handle_registration, item) for item in email_data]
        # 等待所有任务完成
        for _ in as_completed(futures):
            pass

    # 完成处理
    registration_status[task_id]["status"] = "completed"
    print(f"[Register] 批量注册任务 {task_id} 完成, 成功: {registration_status[task_id]['success']}, 失败: {registration_status[task_id]['failed']}")


# 批量刷新处理函数
def process_refresh(task_id: str, include_disabled: bool, thread_count: int, db: Session):
    """
    后台处理批量刷新账号
    """
    from utils.register import refresh_silent_cookies, fetch_auth_info
    from db import get_db
    
    # 查询符合条件的账号ID列表（而不是整个对象）
    if include_disabled:
        account_ids = [r[0] for r in db.query(tokens.Token.id).filter(tokens.Token.deleted_at == None).all()]
    else:
        account_ids = [r[0] for r in db.query(tokens.Token.id).filter(tokens.Token.deleted_at == None, tokens.Token.enable == 1).all()]
    
    batch_refresh_status[task_id] = {
        "status": "processing",
        "total": len(account_ids),
        "processed": 0,
        "success": 0,
        "failed": 0,
    }
    
    def refresh_account(account_id):
        # 为每个线程创建独立的数据库会话
        thread_db = next(get_db())
        try:
            # 获取账号
            account = thread_db.query(tokens.Token).filter(tokens.Token.id == account_id).first()
            if not account:
                print(f"[BatchRefresh] 账号 {account_id} 不存在")
                return False
                
            # 获取cookie
            cookies_dict = json.loads(account.silent_cookies or "{}")
            if not cookies_dict:
                print(f"[BatchRefresh] 账号 {account_id} 没有cookies")
                return False
                
            # 刷新cookies
            success, new_cookies, access_token = refresh_silent_cookies(cookies_dict)
            if not success or not new_cookies or not access_token:
                print(f"[BatchRefresh] 账号 {account_id} 刷新cookies失败")
                return False
                
            # 更新数据库
            account.silent_cookies = json.dumps(new_cookies)
            account.access_token = access_token
            account.cookies_expires = datetime.now()+timedelta(days=30)
            account.updated_at = datetime.now()
            account.token_expires = datetime.now()+timedelta(minutes=15)
            account.enable = 1
            
            # 如果有token，还要更新auth和account_type
            if account.token:
                token_str = str(account.token)  # 获取token字符串
                auth_data = signin_with_access_token(str(access_token))
                if auth_data:
                    # 更新token
                    if auth_data.get('token'):
                        account.token = auth_data.get('token')
                    
                    # 更新account_type
                    if auth_data.get('account_type'):
                        account.account_type = auth_data.get('account_type')
                    
                    # 更新auth
                    account.auth = json.dumps(auth_data)
            
            # 提交更改，使用本线程的数据库会话
            thread_db.commit()
            print(f"[BatchRefresh] 账号 {account_id} 刷新成功")
            return True
            
        except Exception as e:
            # 发生异常时回滚
            thread_db.rollback()
            print(f"[BatchRefresh] 刷新账号 {account_id} 失败: {str(e)}")
            return False
        finally:
            # 关闭本线程的数据库会话
            thread_db.close()
    
    # 使用线程池处理刷新任务
    # 限制线程数范围在1-20之间
    thread_count = min(20, max(1, thread_count))
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        # 提交所有刷新任务，使用账号ID而不是整个账号对象
        future_to_account_id = {executor.submit(refresh_account, account_id): account_id for account_id in account_ids}
        
        # 处理完成的任务
        for future in as_completed(future_to_account_id):
            account_id = future_to_account_id[future]
            batch_refresh_status[task_id]["processed"] += 1
            
            try:
                success = future.result()
                if success:
                    batch_refresh_status[task_id]["success"] += 1
                else:
                    batch_refresh_status[task_id]["failed"] += 1
            except Exception as e:
                print(f"[BatchRefresh] 处理账号 {account_id} 时发生异常: {str(e)}")
                batch_refresh_status[task_id]["failed"] += 1
    
    # 任务完成
    batch_refresh_status[task_id]["status"] = "completed"
    print(f"[BatchRefresh] 批量刷新任务 {task_id} 完成, 成功: {batch_refresh_status[task_id]['success']}, 失败: {batch_refresh_status[task_id]['failed']}")


# API端点
@router.post("/bulk-register", response_model=BulkRegisterResponse)
def bulk_register(
    data: BulkRegisterRequest, 
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin)  # 使用身份验证依赖
):
    """批量注册账号"""
    # 这里简单处理数据，解析出账号信息
    lines = data.data.strip().split('\n')
    parsed_data = []
    
    for line in lines:
        parts = line.split('----')
        if len(parts) >= 2:
            # 解析数据
            account = parts[0]
            password = parts[1]
            token_data = None
            uuid = None
            
            if len(parts) >= 3:
                token_data = parts[2]
                
            if len(parts) >= 4:
                uuid = parts[3]
                
                # 检查是否需要调换位置 (如果第三个参数是UUID格式，则与第四个参数交换)
                if token_data and is_uuid(token_data) and uuid and not is_uuid(uuid):
                    # 调换位置
                    token_data, uuid = uuid, token_data
                
            # 将数据存入结果列表
            parsed_data.append({
                "account": account,
                "password": password,
                "token": token_data,
                "uuid": uuid
            })
    
    # 创建任务ID
    import uuid
    task_id = str(uuid.uuid4())
    
    # 启动后台线程处理注册
    thread = threading.Thread(
        target=process_registrations,
        args=(task_id, parsed_data, next(get_db()), data.thread_count),  # 为线程创建单独的数据库会话，并传递thread_count
        daemon=True
    )
    thread.start()
    
    return {
        "task_id": task_id,
        "count": len(parsed_data),
        "parsed_data": parsed_data
    }


@router.get("/status/{task_id}")
def get_registration_status(task_id: str, _: bool = Depends(verify_admin)):
    """获取注册任务状态"""
    if task_id not in registration_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return registration_status[task_id] 


@router.post("/refresh/{account_id}")
async def refresh_account(account_id: int, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """手动刷新指定账号的silent cookies"""
    from utils.register import refresh_silent_cookies, fetch_auth_info
    account = db.query(tokens.Token).filter(tokens.Token.id == account_id, tokens.Token.deleted_at == None).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    cookies_dict = json.loads(account.silent_cookies or "{}")
    success, new_cookies, access_token = refresh_silent_cookies(cookies_dict)
    if not success or not new_cookies or not access_token:
        account.enable = 0
        account.updated_at = datetime.now()
        db.commit()
        raise HTTPException(status_code=500, detail="Refresh failed and account disabled")
    account.silent_cookies = json.dumps(new_cookies)
    account.access_token = access_token
    account.cookies_expires = datetime.now()+timedelta(days=30)
    account.updated_at = datetime.now()
    account.token_expires = datetime.now()+timedelta(minutes=15)
    account.enable = 1
    
    # 使用signin_with_access_token更新token, account_type和auth
    if account.token:
        auth_data = signin_with_access_token(str(access_token))
        if auth_data:
            # 更新token
            if auth_data.get('token'):
                account.token = auth_data.get('token')
            
            # 更新account_type
            if auth_data.get('account_type'):
                account.account_type = auth_data.get('account_type')
            
            # 更新auth
            account.auth = json.dumps(auth_data)
            
            print(f"[ChatBetter] 账号 {account_id} 的token和account_type已更新")
    
    db.commit()

    return {"message": "cookies refreshed"}


@router.post("/batch-refresh", response_model=BatchRefreshResponse)
def batch_refresh(
    request: BatchRefreshRequest, 
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin)
):
    """批量刷新账号"""
    # 创建任务ID
    task_id = str(uuid.uuid4())
    
    # 确定要刷新的账号数量
    if request.include_disabled:
        count = db.query(tokens.Token).filter(tokens.Token.deleted_at == None).count()
    else:
        count = db.query(tokens.Token).filter(tokens.Token.deleted_at == None, tokens.Token.enable == 1).count()
    
    # 启动后台线程处理刷新
    thread = threading.Thread(
        target=process_refresh,
        args=(task_id, request.include_disabled, request.thread_count, next(get_db())),  # 为线程创建单独的数据库会话
        daemon=True
    )
    thread.start()
    
    return {
        "task_id": task_id,
        "count": count
    }


@router.get("/refresh-status/{task_id}")
def get_refresh_status(task_id: str, _: bool = Depends(verify_admin)):
    """获取批量刷新任务状态"""
    if task_id not in batch_refresh_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return batch_refresh_status[task_id]