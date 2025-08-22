from sqlalchemy import Column, Integer, String, DateTime, Text, SmallInteger, func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from db import Base, engine
import json
from typing import Optional

class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    account = Column(String(255), nullable=True, default=None)
    token = Column(Text, nullable=True, default=None)
    silent_cookies = Column(Text, nullable=True, default=None)
    cookies_expires = Column(DateTime, nullable=True, default=None)
    auth = Column(Text, nullable=True, default=None)
    access_token = Column(Text, nullable=True, default=None)
    token_expires = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, nullable=True, default=None)
    updated_at = Column(DateTime, nullable=True, default=None)
    enable = Column(SmallInteger, nullable=True, default=None)  # tinyint类型
    deleted_at = Column(DateTime, nullable=True, default=None)
    count = Column(Integer, nullable=True, default=None)
    account_type = Column(String(50), nullable=True, default=None)

# CRUD操作
def create_token(db: Session, token_data: dict):
    """根据账号插入或更新 token 记录"""
    now = datetime.now()

    account = token_data.get('account')
    existing_token = None
    if account:
        existing_token = db.query(Token).filter(Token.account == account, Token.deleted_at == None).first()

    # ---------------- 若已存在 -> 执行更新 ----------------
    if existing_token:
        # 根据传入字段更新，不传入的字段保持不变
        for key, value in token_data.items():
            if value is None:
                continue  # 跳过空值，避免覆盖
            if key == 'cookies':
                # cookies 字典存入 silent_cookies
                setattr(existing_token, 'silent_cookies', json.dumps(value))
                # cookies_expires 重置为 30 天后
                existing_token.cookies_expires = now + timedelta(days=30)
            elif hasattr(existing_token, key):
                setattr(existing_token, key, value)

        # 若获得新的 token，则启用账号
        if token_data.get('token'):
            existing_token.enable = 1

        existing_token.updated_at = now
        db.commit()
        db.refresh(existing_token)
        return existing_token

    # ---------------- 不存在 -> 创建新记录 ----------------
    if "cookies" in token_data:
        # 新格式，包含 cookies 和 token
        cookies = token_data.get("cookies")
        access_token = token_data.get("access_token")
        token_val = token_data.get("token")
        auth_val = token_data.get("auth")
        account_type_val = token_data.get("account_type")

        db_token = Token(
            account=account,
            token=token_val,
            silent_cookies=json.dumps(cookies) if cookies else None,
            cookies_expires=now + timedelta(days=30),
            auth=auth_val,
            access_token=access_token,
            token_expires=None,
            created_at=now,
            updated_at=now,
            enable=1 if token_val else 0,
            count=0,
            account_type=account_type_val
        )
    else:
        # 旧格式
        db_token = Token(
            account=account,
            token=token_data.get('token'),
            silent_cookies=token_data.get('silent_cookies'),
            cookies_expires=token_data.get('cookies_expires'),
            auth=token_data.get('auth'),
            access_token=token_data.get('access_token'),
            token_expires=token_data.get('token_expires'),
            created_at=now,
            updated_at=now,
            enable=token_data.get('enable', 1),
            count=token_data.get('count', 0),
            account_type=token_data.get('account_type')
        )

    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token

def get_token(db: Session, token_id: int):
    """根据ID获取token"""
    return db.query(Token).filter(Token.id == token_id, Token.deleted_at == None).first()

def get_token_by_account(db: Session, account: str):
    """根据账号获取token"""
    return db.query(Token).filter(Token.account == account, Token.deleted_at == None).first()

def get_tokens(db: Session, skip: int = 0, limit: int = 100, sort_by: str = None, sort_desc: bool = False, account: Optional[str] = None):
    """获取所有未删除的token列表，支持账号模糊搜索"""
    query = db.query(Token).filter(Token.deleted_at == None)
    
    # 添加账号模糊搜索条件
    if account:
        query = query.filter(Token.account.like(f'%{account}%'))
    
    # Add sorting if sort_by is specified and it's a valid column
    if sort_by and hasattr(Token, sort_by):
        column = getattr(Token, sort_by)
        if sort_desc:
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    
    return query.offset(skip).limit(limit).all()

def count_tokens(db: Session, account: Optional[str] = None):
    """获取未删除的token总数，支持账号模糊搜索"""
    query = db.query(func.count(Token.id)).filter(Token.deleted_at == None)
    
    # 添加账号模糊搜索条件
    if account:
        query = query.filter(Token.account.like(f'%{account}%'))
    
    return query.scalar()

def update_token(db: Session, token_id: int, token_data: dict):
    """更新token信息"""
    db_token = get_token(db, token_id)
    if not db_token:
        return None
    
    # 更新字段
    for key, value in token_data.items():
        if hasattr(db_token, key):
            setattr(db_token, key, value)
    
    db_token.updated_at = datetime.now()
    db.commit()
    db.refresh(db_token)
    return db_token

def soft_delete_token(db: Session, token_id: int):
    """软删除token"""
    db_token = get_token(db, token_id)
    if not db_token:
        return False
    
    db_token.deleted_at = datetime.now()
    db_token.updated_at = datetime.now()
    db.commit()
    return True

def increment_count(db: Session, token_id: int):
    """增加使用次数"""
    db_token = get_token(db, token_id)
    if not db_token:
        return None
    
    if db_token.count is None:
        db_token.count = 1
    else:
        db_token.count += 1
    
    db_token.updated_at = datetime.now()
    db.commit()
    db.refresh(db_token)
    return db_token

def get_available_tokens(db: Session, skip: int = 0, limit: int = 100):
    """获取所有可用的token列表（未删除且启用的）"""
    return db.query(Token).filter(Token.deleted_at == None, Token.enable == 1).offset(skip).limit(limit).all()

# 创建表
def create_tables():
    Base.metadata.create_all(bind=engine)
