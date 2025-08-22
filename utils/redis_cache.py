from redis import Redis
from typing import Dict, List, Optional, Any, Union
import json
import time
from env import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_ACCOUNT_CACHE_TTL

# 创建Redis客户端连接
redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True  # 自动将响应解码为字符串
)

# 缓存键前缀
KEY_PREFIX = "chatbetter2api:"
ACCOUNT_KEY = f"{KEY_PREFIX}account:"
PAID_ACCOUNT_KEY = f"{KEY_PREFIX}paid_account:"
LOCK_KEY = f"{KEY_PREFIX}account_lock:"  # 账号锁定的键前缀
LOCK_EXPIRY = 300  # 锁定过期时间（秒），防止死锁

def test_connection() -> bool:
    """测试Redis连接是否正常"""
    try:
        return redis_client.ping()
    except Exception as e:
        print(f"Redis连接测试失败: {str(e)}")
        return False

def cache_account(account_id: int, account_data: Dict[str, Any], is_paid: bool = False) -> bool:
    """
    缓存账号信息到Redis
    
    Args:
        account_id: 账号ID
        account_data: 账号数据，必须是可JSON序列化的字典
        is_paid: 是否是付费账号
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        # 序列化账号数据
        account_json = json.dumps(account_data)
        
        # 设置基本账号键
        base_key = PAID_ACCOUNT_KEY if is_paid else ACCOUNT_KEY
        key = f"{base_key}{account_id}"
        
        # 缓存账号数据，设置过期时间
        redis_client.setex(key, REDIS_ACCOUNT_CACHE_TTL, account_json)
        
        # 将账号ID加入相应的账号集合
        set_key = PAID_ACCOUNT_KEY + "set" if is_paid else ACCOUNT_KEY + "set"
        redis_client.sadd(set_key, account_id)
        
        return True
    except Exception as e:
        print(f"缓存账号失败: {str(e)}")
        return False

def lock_account(account_id: int) -> bool:
    """
    锁定账号，防止其被其他请求同时使用
    
    Args:
        account_id: 账号ID
        
    Returns:
        成功锁定返回True，已被锁定返回False
    """
    try:
        lock_key = f"{LOCK_KEY}{account_id}"
        # 使用Redis的setnx命令，只有当键不存在时才设置值（原子操作）
        locked = redis_client.setnx(lock_key, str(int(time.time())))
        if locked:
            # 设置锁的过期时间，防止死锁
            redis_client.expire(lock_key, LOCK_EXPIRY)
            return True
        return False
    except Exception as e:
        print(f"锁定账号失败: {str(e)}")
        return False

def unlock_account(account_id: int) -> bool:
    """
    解锁账号，使其可以被其他请求使用
    
    Args:
        account_id: 账号ID
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        lock_key = f"{LOCK_KEY}{account_id}"
        redis_client.delete(lock_key)
        return True
    except Exception as e:
        print(f"解锁账号失败: {str(e)}")
        return False

def is_account_locked(account_id: int) -> bool:
    """
    检查账号是否被锁定
    
    Args:
        account_id: 账号ID
        
    Returns:
        已锁定返回True，未锁定返回False
    """
    try:
        lock_key = f"{LOCK_KEY}{account_id}"
        return redis_client.exists(lock_key) == 1
    except Exception as e:
        print(f"检查账号锁定状态失败: {str(e)}")
        return True  # 如果发生错误，默认认为账号已锁定

def get_cached_account(is_paid: bool = False) -> Optional[Dict[str, Any]]:
    """
    从Redis缓存中获取一个可用的账号
    
    Args:
        is_paid: 是否获取付费账号
        
    Returns:
        返回账号数据字典，如果没有可用账号则返回None
    """
    try:
        # 确定使用哪个集合键
        set_key = PAID_ACCOUNT_KEY + "set" if is_paid else ACCOUNT_KEY + "set"
        
        # 获取集合中所有账号ID
        account_ids = redis_client.smembers(set_key)
        if not account_ids:
            return None
        
        # 查找未被锁定的账号
        for account_id in account_ids:
            # 直接读取账号数据，不再加锁
            base_key = PAID_ACCOUNT_KEY if is_paid else ACCOUNT_KEY
            key = f"{base_key}{account_id}"
            account_json = redis_client.get(key)
            if not account_json:
                # 如果键不存在，从集合中移除该ID
                redis_client.srem(set_key, account_id)
                continue
            return json.loads(account_json)
 
        # 所有账号都无效
        return None
    except Exception as e:
        print(f"获取缓存账号失败: {str(e)}")
        return None

def remove_cached_account(account_id: int, is_paid: bool = False) -> bool:
    """
    从Redis缓存中移除指定的账号
    
    Args:
        account_id: 要移除的账号ID
        is_paid: 是否是付费账号
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        # 确定基本键和集合键
        base_key = PAID_ACCOUNT_KEY if is_paid else ACCOUNT_KEY
        set_key = base_key + "set"
        key = f"{base_key}{account_id}"
        
        # 删除账号数据和从集合中移除
        redis_client.delete(key)
        redis_client.srem(set_key, account_id)
        
        return True
    except Exception as e:
        print(f"移除缓存账号失败: {str(e)}")
        return False

def refresh_account_cache(account_data_list: List[Dict[str, Any]], is_paid: bool = False) -> bool:
    """
    刷新账号缓存，批量添加账号到缓存
    
    Args:
        account_data_list: 账号数据列表
        is_paid: 是否是付费账号
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        # 清除现有缓存
        clear_account_cache(is_paid)
        
        # 批量添加新账号
        for account_data in account_data_list:
            account_id = account_data.get('id')
            if account_id:
                cache_account(account_id, account_data, is_paid)
        
        return True
    except Exception as e:
        print(f"刷新账号缓存失败: {str(e)}")
        return False

def clear_account_cache(is_paid: bool = False) -> bool:
    """
    清除指定类型的账号缓存
    
    Args:
        is_paid: 是否清除付费账号缓存
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        # 确定要清除的键模式
        base_key = PAID_ACCOUNT_KEY if is_paid else ACCOUNT_KEY
        pattern = f"{base_key}*"
        
        # 查找所有匹配的键
        keys = redis_client.keys(pattern)
        
        # 如果有键，删除它们
        if keys:
            redis_client.delete(*keys)
        
        return True
    except Exception as e:
        print(f"清除账号缓存失败: {str(e)}")
        return False

def increment_account_usage(account_id: int, is_paid: bool = False) -> bool:
    """
    增加账号的使用计数
    
    Args:
        account_id: 账号ID
        is_paid: 是否是付费账号
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        # 确定键
        base_key = PAID_ACCOUNT_KEY if is_paid else ACCOUNT_KEY
        key = f"{base_key}{account_id}"
        
        # 获取当前账号数据
        account_json = redis_client.get(key)
        if not account_json:
            return False
        
        account_data = json.loads(account_json)
        
        # 增加使用次数
        if 'count' in account_data:
            account_data['count'] += 1
        else:
            account_data['count'] = 1
        
        # 更新缓存
        redis_client.setex(key, REDIS_ACCOUNT_CACHE_TTL, json.dumps(account_data))
        
        return True
    except Exception as e:
        print(f"增加账号使用计数失败: {str(e)}")
        return False 