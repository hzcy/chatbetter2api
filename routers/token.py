import json
import os

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Header
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
from db import get_db
from models import tokens
from utils.auth import verify_admin
from utils.register import refresh_silent_cookies

# 创建路由器
router = APIRouter(
    prefix="/api/tokens",
    tags=["tokens"],
    responses={404: {"description": "Token not found"}},
)

# Pydantic模型用于请求和响应
class TokenBase(BaseModel):
    account: Optional[str] = None
    token: Optional[str] = None
    silent_cookies: Optional[str] = None
    cookies_expires: Optional[datetime] = None
    auth: Optional[str] = None
    access_token: Optional[str] = None
    token_expires: Optional[datetime] = None
    enable: Optional[int] = 1
    count: Optional[int] = 0
    account_type: Optional[str] = None

class TokenCreate(TokenBase):
    pass

class TokenUpdate(TokenBase):
    pass

class Token(TokenBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class PaginatedTokens(BaseModel):
    total: int
    items: List[Token]

class LoginResponse(BaseModel):
    status: str = "success"
    
class BulkRegisterRequest(BaseModel):
    data: str

# API端点
@router.post("/login", response_model=LoginResponse)
async def login(authorization: Optional[str] = Header(None)):
    """管理员登录
    验证请求头中的Authorization是否匹配ADMIN_PASSWORD
    """
    # 直接使用verify_admin进行验证，但需要手动调用它
    await verify_admin(authorization)
    
    # 如果没有抛出异常，则验证通过
    return {"status": "success"}

@router.post("/", response_model=Token)
def create_token_api(token_data: TokenCreate, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """创建新的token"""
    return tokens.create_token(db=db, token_data=token_data.dict())

# 获取并保存最新模型列表（放在动态参数路由之前，避免路径冲突）
@router.get("/refresh-models")
async def refresh_models(db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """
    使用最新更新的启用账号刷新模型数据
    """
    try:
        # 查询最新更新且启用的账号
        account = db.query(tokens.Token).filter(
            tokens.Token.enable == 1,
            tokens.Token.deleted_at == None
        ).order_by(tokens.Token.updated_at.desc()).first()

        if not account:
            raise HTTPException(status_code=404, detail="No available account found")

        # 组装请求头
        headers = {
            "Authorization": f"Bearer {account.token}",
            "Cookie": f"token={account.token}; ChatBetterJwt={account.access_token}"
        }

        # 请求 ChatBetter 接口获取模型列表
        response = requests.get("https://app.chatbetter.com/api/models", headers=headers)
        response.raise_for_status()

        models_data = response.json()

        # 将结果写入本地文件 routers/models.json
        models_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "routers",
            "models.json",
        )
        with open(models_file_path, "w", encoding="utf-8") as f:
            json.dump(models_data, f, ensure_ascii=False, indent=2)

        return {"status": "success", "message": "Models refreshed successfully"}

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing models: {str(e)}")

@router.get("/{token_id}", response_model=Token)
def read_token(token_id: int, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """通过ID获取token"""
    db_token = tokens.get_token(db, token_id=token_id)
    if db_token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token

@router.get("/account/{account}", response_model=Token)
def read_token_by_account(account: str, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """通过账号获取token"""
    db_token = tokens.get_token_by_account(db, account=account)
    if db_token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token

@router.get("/", response_model=PaginatedTokens)
def read_tokens(
    skip: int = 0, 
    limit: int = 10, 
    sort_by: Optional[str] = None,
    sort_desc: bool = False,
    account: Optional[str] = None,
    db: Session = Depends(get_db), 
    _: bool = Depends(verify_admin)
):
    """获取token列表（带分页）"""
    items = tokens.get_tokens(db, skip=skip, limit=limit, sort_by=sort_by, sort_desc=sort_desc)
    total = tokens.count_tokens(db)  # 需要在tokens模块中添加此函数
    return {"total": total, "items": items}

@router.put("/{token_id}", response_model=Token)
def update_token_api(token_id: int, token_data: TokenUpdate, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """更新token信息"""
    db_token = tokens.update_token(db, token_id=token_id, token_data=token_data.dict(exclude_unset=True))
    if db_token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token

@router.delete("/{token_id}", response_model=bool)
def delete_token(token_id: int, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """软删除token"""
    result = tokens.soft_delete_token(db, token_id=token_id)
    if not result:
        raise HTTPException(status_code=404, detail="Token not found")
    return result

@router.put("/{token_id}/increment", response_model=Token)
def increment_token_count(token_id: int, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """增加token使用次数"""
    db_token = tokens.increment_count(db, token_id=token_id)
    if db_token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token

@router.get("/available/", response_model=List[Token])
def read_available_tokens(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """获取可用的token列表"""
    return tokens.get_available_tokens(db, skip=skip, limit=limit)

@router.get("/{token_id}/upgrade")
def upgrade_token(token_id: int, db: Session = Depends(get_db), _: bool = Depends(verify_admin)):
    """刷新账号的silent cookies并返回Stripe升级链接"""
    # 获取账号
    account = (
        db.query(tokens.Token)
        .filter(tokens.Token.id == token_id, tokens.Token.deleted_at == None)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Token not found")

    # 尝试刷新 silent cookies 以获得新的 access_token
    try:
        cookies_dict = json.loads(account.silent_cookies or "{}")
    except Exception:
        cookies_dict = {}

    if cookies_dict:
        success, new_cookies, new_access_token = refresh_silent_cookies(cookies_dict)
        if success and new_cookies and new_access_token:
            account.silent_cookies = json.dumps(new_cookies)
            account.access_token = new_access_token
            account.cookies_expires = datetime.now() + timedelta(days=30)
            account.updated_at = datetime.now()
            db.commit()

    # 如果缺少 token 或 access_token，无法继续
    if not account.token or not account.access_token:
        raise HTTPException(status_code=400, detail="Missing token or access_token")

    headers = {
        "Cookie": f"token={account.token}; ChatBetterJwt={account.access_token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        # 跟随重定向获取最终链接
        resp = requests.get("https://app.chatbetter.com/stripe/checkout", headers=headers, allow_redirects=True)
        final_url = resp.url
        return {"url": final_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to obtain upgrade URL: {str(e)}")