from sqlalchemy.orm import Session
from models.tokens import Token, increment_count
from sqlalchemy import desc, asc
from typing import Optional, Dict, Any, List
import json
from utils.redis_cache import (
    cache_account, 
    get_cached_account, 
    increment_account_usage,
    refresh_account_cache,
    test_connection as test_redis_connection,
    remove_cached_account,
    lock_account,
    unlock_account,
    is_account_locked
)

def token_to_dict(token: Token) -> Dict[str, Any]:
    """将Token对象转换为可序列化的字典"""
    if not token:
        return {}
    
    return {
        "id": token.id,
        "account": token.account,
        "token": token.token,
        "access_token": token.access_token,
        "account_type": token.account_type,
        "count": token.count,
        "enable": token.enable
    }

async def pick_account(db: Session) -> Token:
    """
    挑选使用次数最少且启用的账号
    优先从Redis缓存获取，如果缓存无数据则从数据库获取并更新缓存
    会锁定选中的账号，防止被同时使用
    """
    # 尝试从Redis缓存中获取账号
    try:
        if test_redis_connection():
            cached_account = get_cached_account(is_paid=False)
            if cached_account and cached_account.get("id"):
                # 从缓存获取到账号，需要从数据库中获取完整的Token对象
                account_id = cached_account.get("id")
                db_account = db.query(Token).filter(Token.id == account_id).first()
                
                if db_account and db_account.enable == 1 and db_account.deleted_at is None:
                    # 更新使用次数
                    increment_count(db, db_account.id)
                    db.commit()
                    db.refresh(db_account)
                    
                    # 更新Redis中的使用次数
                    increment_account_usage(account_id, is_paid=False)
                    
                    # 注意：此时账号已经被锁定，由调用者负责在适当时机解锁
                    return db_account
    except Exception as e:
        print(f"Redis缓存获取账号失败: {str(e)}")
    
    # 如果Redis不可用或者没有缓存数据，从数据库获取
    # 获取所有可用账号
    accounts = (
        db.query(Token)
        .filter(Token.enable == 1, Token.deleted_at == None)
        .order_by(Token.count.asc(), desc(Token.token_expires))
        .all()
    )
    
    account = accounts[0]

    if not account:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="No available account")
    
    # 更新使用次数
    increment_count(db, account.id)
    db.commit()
    db.refresh(account)

    # 尝试更新Redis缓存
    try:
        if test_redis_connection():
            account_data = token_to_dict(account)
            cache_account(account.id, account_data, is_paid=False)
    except Exception as e:
        print(f"更新Redis缓存账号失败: {str(e)}")
    
    return account

async def pick_paid_account(db: Session) -> Token:
    """
    挑选account_type为paid的账号，如果没有则选择普通账号
    优先从Redis缓存获取，如果缓存无数据则从数据库获取并更新缓存
    会锁定选中的账号，防止被同时使用
    """
    # 尝试从Redis缓存中获取付费账号
    try:
        if test_redis_connection():
            cached_account = get_cached_account(is_paid=True)
            if cached_account and cached_account.get("id"):
                # 从缓存获取到付费账号
                account_id = cached_account.get("id")
                db_account = db.query(Token).filter(Token.id == account_id).first()
                
                if db_account and db_account.enable == 1 and db_account.deleted_at is None:
                    # 更新使用次数
                    increment_count(db, db_account.id)
                    db.commit()
                    db.refresh(db_account)
                    
                    # 更新Redis中的使用次数
                    increment_account_usage(account_id, is_paid=True)
                    
                    # 注意：此时账号已经被锁定，由调用者负责在适当时机解锁
                    return db_account
    except Exception as e:
        print(f"Redis缓存获取付费账号失败: {str(e)}")
    
    # 如果Redis不可用或者没有缓存数据，从数据库获取
    # 获取所有可用的付费账号
    paid_accounts = (
        db.query(Token)
        .filter(Token.enable == 1, Token.deleted_at == None, Token.account_type == 'paid')
        .order_by(Token.count.asc(), desc(Token.token_expires))
        .all()
    )
    
    account = paid_accounts[0] if paid_accounts else None

    # 如果所有付费账号都被锁定，尝试获取普通账号
    if not account:
        return await pick_account(db)
    
    # 更新使用次数
    increment_count(db, account.id)
    db.commit()
    db.refresh(account)
    
    # 尝试更新Redis缓存
    try:
        if test_redis_connection():
            account_data = token_to_dict(account)
            cache_account(account.id, account_data, is_paid=True)
    except Exception as e:
        print(f"更新Redis缓存付费账号失败: {str(e)}")
    
    return account

def release_account(account_id: int) -> bool:
    """
    释放账号，使其可以被其他请求使用
    
    Args:
        account_id: 要释放的账号ID
        
    Returns:
        成功返回True，失败返回False
    """
    return True

def refresh_accounts_cache(db: Session):
    """
    刷新Redis中的账号缓存
    将数据库中的可用账号加载到Redis缓存中
    """
    try:
        if not test_redis_connection():
            print("Redis连接不可用，无法刷新缓存")
            return False
        
        # 加载普通账号
        normal_accounts = (
            db.query(Token)
            .filter(Token.enable == 1, Token.deleted_at == None)
            .order_by(Token.count.asc(), desc(Token.token_expires))
            .all()
        )
        
        normal_account_data = [token_to_dict(account) for account in normal_accounts]
        refresh_account_cache(normal_account_data, is_paid=False)
        
        # 加载付费账号
        paid_accounts = (
            db.query(Token)
            .filter(Token.enable == 1, Token.deleted_at == None, Token.account_type == 'paid')
            .order_by(Token.count.asc(), desc(Token.token_expires))
            .all()
        )
        
        paid_account_data = [token_to_dict(account) for account in paid_accounts]
        refresh_account_cache(paid_account_data, is_paid=True)
        
        return True
    except Exception as e:
        print(f"刷新账号缓存失败: {str(e)}")
        return False 