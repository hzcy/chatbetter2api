import requests
import random
import string
import re
import json
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

from utils.outlook_util import OutlookAccount, OutlookMailManager

# API设置
HEADERS = {
    "Origin": "https://app.chatbetter.com",
    "Referer": "https://app.chatbetter.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

# ----------------- 登录相关配置 -----------------
PRELOGIN_URL = "https://auth.chatbetter.com/frontegg/identity/resources/auth/v1/passwordless/magiclink/prelogin"
POSTLOGIN_URL = "https://auth.chatbetter.com/frontegg/identity/resources/auth/v1/passwordless/magiclink/postlogin"


# ----------------- 辅助函数 -----------------

def extract_login_token(login_link: str) -> Optional[str]:
    """从登录链接中提取token参数"""
    try:
        token_match = re.search(r"token=([^&]+)", login_link)
        return token_match.group(1) if token_match else None
    except Exception as e:
        print(f"[ChatBetter] 提取登录token异常: {str(e)}")
        return None


def send_prelogin_email(email: str) -> bool:
    """向指定邮箱发送登录magic link邮件"""
    payload = {
        "email": email,
        "invitationToken": "",
        "username": ""
    }
    try:
        resp = requests.post(PRELOGIN_URL, json=payload, headers=HEADERS)
        if resp.status_code in (200, 201):
            print(f"[ChatBetter] 已发送login magic link到 {email}")
            return True
        print(f"[ChatBetter] 发送prelogin失败, 状态码: {resp.status_code}, 响应: {resp.text}")
        return False
    except Exception as e:
        print(f"[ChatBetter] 发送prelogin请求异常: {str(e)}")
        return False


def fetch_auth_info(token:str, chat_better_jwt: str) -> Optional[dict]:
    try:
        # 准备请求头
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': HEADERS['User-Agent'],
            'Cookie': f'token={token}; ChatBetterJwt={chat_better_jwt}',
            'Authorization': f'Bearer {token}'
        }
        
        # 发送请求
        response = requests.get(
            "https://app.chatbetter.com/api/v1/auths/",
            headers=headers
        )
        
        # 检查响应状态
        if response.status_code not in (200, 201):
            error_msg = f"API请求失败, 状态码: {response.status_code}, 响应: {response.text}"
            print(f"[ChatBetter] {error_msg}")
            return None
            
        # 解析响应数据
        try:
            auth_data = response.json()
            token = auth_data.get('token')
            account_type = auth_data.get('account_type')
            
            if not token:
                error_msg = "API响应中没有token"
                print(f"[ChatBetter] {error_msg}")
                return auth_data
                
            print(f"[ChatBetter] 获取到token: {token[:20]}... 账号类型: {account_type}")
            return auth_data
            
        except Exception as e:
            error_msg = f"解析API响应失败: {str(e)}"
            print(f"[ChatBetter] {error_msg}")
            return None
            
    except Exception as e:
        error_msg = f"API请求异常: {str(e)}"
        print(f"[ChatBetter] {error_msg}")
        return None


# ----------------- 新增: 通过 accessToken 调用 /api/v1/auths/signin -----------------


def signin_with_access_token(access_token: str) -> Optional[dict]:
    """使用 accessToken 调用 /api/v1/auths/signin 获取认证信息

    Args:
        access_token: 登录流程中获取到的 ChatBetterJwt (即 accessToken)

    Returns:
        解析后的响应 JSON, 如果失败则返回 None
    """
    # 准备请求头, 只需要在 Cookie 中携带 ChatBetterJwt
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': HEADERS['User-Agent'],
        'Cookie': f'ChatBetterJwt={access_token}'
    }

    try:
        response = requests.post(
            "https://app.chatbetter.com/api/v1/auths/signin",
            json={"email":"","password":""},
            headers=headers
        )

        # 状态码校验
        if response.status_code not in (200, 201):
            print(f"[ChatBetter] signin 失败, 状态码: {response.status_code}, 响应: {response.text}")
            return None

        # 解析 JSON
        try:
            auth_data = response.json()
        except Exception as e:
            print(f"[ChatBetter] 解析 signin 响应失败: {str(e)}")
            return None

        token = auth_data.get('token')
        account_type = auth_data.get('account_type')

        if token:
            pass
        else:
            print("[ChatBetter] signin 响应中未包含 token")

        return auth_data

    except Exception as e:
        print(f"[ChatBetter] signin 请求异常: {str(e)}")
        return None


def login_account(email: str, outlook_account: OutlookAccount) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    使用magic link登录已存在的ChatBetter账号

    Args:
        email: 邮箱地址
        outlook_account: OutlookAccount对象

    Returns:
        (结果字典, 错误信息)
    """
    # 1. 发送prelogin邮件
    if not send_prelogin_email(email):
        return None, "prelogin发送失败"

    # 2. 等待并获取登录magic link
    manager = OutlookMailManager()
    magic_link_result = manager.get_login_link(outlook_account)
    if magic_link_result.get("type") != "True" or not magic_link_result.get("link"):
        return None, "获取登录链接失败"

    login_link = magic_link_result["link"]
    print(f"[ChatBetter] 获取到登录链接: {login_link[:50]}...")

    # 3. 解析token
    token = extract_login_token(login_link)
    if not token:
        return None, "无法从登录链接中提取token"

    # 4. 调用postlogin
    payload = {
        "token": token,
        "invitationToken": ""
    }
    try:
        resp = requests.post(POSTLOGIN_URL, json=payload, headers=HEADERS)
        if resp.status_code not in (200, 201):
            return None, f"postlogin失败, 状态码: {resp.status_code}, 响应: {resp.text}"

        # 提取cookies
        cookie_dict = {c.name: c.value for c in resp.cookies}
        fe_device_cookie = next((name for name in cookie_dict if name.startswith('fe_device')), None)
        fe_refresh_cookie = next((name for name in cookie_dict if name.startswith('fe_refresh')), None)
        if not fe_device_cookie or not fe_refresh_cookie:
            return None, "登录失败, 未获取到所需cookies"

        # accessToken 在响应体
        try:
            resp_json = resp.json()
            access_token = resp_json.get('accessToken')
        except Exception as e:
            access_token = None
            print(f"[ChatBetter] 解析postlogin响应失败: {str(e)}")

        if not access_token:
            return None, "登录失败, 未获取到accessToken"

        print(f"[ChatBetter] 登录成功, 获取accessToken: {access_token[:20]}...")

        # 5. 通过 /api/v1/auths/signin 获取认证信息 (推荐)
        auth_data = signin_with_access_token(access_token)

        # 如果 signin 失败, 再尝试旧的 /auths/ 接口作为回退
        if not auth_data:
            auth_data = fetch_auth_info(token, access_token)


        if not auth_data:
            # 严重错误，无数据返回
            return {
                "cookies": cookie_dict,
                "access_token": access_token,
                "token": None
            }, "errr"
            
        # 即使有错误但还是获取到了auth_data，我们仍然继续使用
        token = auth_data.get('token') if auth_data else None
        account_type = auth_data.get('account_type') if auth_data else None
        auth = json.dumps(auth_data) if auth_data else None

        if not token:
            return {
                "cookies": cookie_dict,
                "access_token": access_token,
                "token": None
            }, "未获取到token"

        print(f"[ChatBetter] Login flow 获取到token: {token[:20]}...")

        return {
            "cookies": cookie_dict,
            "access_token": access_token,
            "token": token,
            "auth": auth,
            "account_type": account_type
        }, None
    except Exception as e:
        return None, f"postlogin请求异常: {str(e)}"


def generate_random_name(length=8):
    """生成随机字母字符串作为用户名"""
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))


def register_chatbetter(email: str) -> Tuple[bool, Optional[str]]:
    """
    注册ChatBetter账号
    
    Args:
        email: Outlook邮箱账号
        
    Returns:
        注册是否成功
    """
    # 生成随机8位字母作为用户名和公司名
    random_name = generate_random_name(8)
    
    # 构建请求体
    payload = {
        "name": random_name,
        "companyName": random_name,
        "email": email
    }
    
    # 请求头
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    
    try:
        # 发送注册请求
        response = requests.post(
            "https://auth.chatbetter.com/frontegg/identity/resources/users/v1/signUp",
            json=payload,
            headers=headers
        )
        
        # 检查响应
        if response.status_code == 200 or response.status_code == 201:
            print(f"[ChatBetter] 账号 {email} 注册请求成功")
            return True, None
        else:
            msg = f"注册失败，状态码: {response.status_code}, 响应: {response.text}"
            print(f"[ChatBetter] {msg}")
            return False, msg
            
    except Exception as e:
        msg = f"注册请求异常: {str(e)}"
        print(f"[ChatBetter] {msg}")
        return False, msg


def extract_activation_params(activation_link: str) -> Tuple[Optional[str], Optional[str]]:
    """
    从激活链接中提取userId和token
    
    Args:
        activation_link: 激活链接
        
    Returns:
        (userId, token)元组，若提取失败则为(None, None)
    """
    try:
        # 使用正则表达式提取参数
        user_id_match = re.search(r'userId=([^&]+)', activation_link)
        token_match = re.search(r'token=([^&]+)', activation_link)
        
        user_id = user_id_match.group(1) if user_id_match else None
        token = token_match.group(1) if token_match else None
        
        return user_id, token
    except Exception as e:
        print(f"[ChatBetter] 提取激活参数异常: {str(e)}")
        return None, None


def activate_account(activation_link: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    激活ChatBetter账号并获取Cookie
    
    Args:
        activation_link: 激活链接
        
    Returns:
        包含cookies和token信息的字典，激活失败则返回None
    """
    # 提取userId和token
    user_id, token = extract_activation_params(activation_link)
    
    if not user_id or not token:
        msg="无法从链接中提取激活参数"
        print(f"[ChatBetter] {msg}")
        return None, msg
    
    # 构建请求体
    payload = {
        "userId": user_id,
        "token": token
    }
    
    # 请求头
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    
    try:
        # 发送激活请求
        response = requests.post(
            "https://auth.chatbetter.com/frontegg/identity/resources/users/v1/activate",
            json=payload,
            headers=headers
        )
        
        # 检查响应
        if response.status_code != 200 and response.status_code != 201:
            msg=f"激活失败，状态码: {response.status_code}, 响应: {response.text}"
            print(f"[ChatBetter] {msg}")
            return None, msg
            
        # 获取cookie
        cookies = response.cookies
        cookie_dict = {cookie.name: cookie.value for cookie in cookies}
        
        # 检查是否包含fe_device和fe_refresh开头的cookie
        fe_device_cookie = next((name for name in cookie_dict if name.startswith('fe_device')), None)
        fe_refresh_cookie = next((name for name in cookie_dict if name.startswith('fe_refresh')), None)
        
        if not fe_device_cookie or not fe_refresh_cookie:
            msg="账号激活失败，未获取到预期的Cookie"
            print(f"[ChatBetter] {msg}")
            return None, msg
            
        # 从响应体中获取accessToken
        response_data = response.json()
        access_token = response_data.get('accessToken')
        
        if not access_token:
            msg="账号激活失败，未获取到accessToken"
            print(f"[ChatBetter] {msg}")
            return None, msg
            
        print(f"[ChatBetter] 获取到accessToken: {access_token[:20]}...")
        
        # 调用API获取认证信息
        auth_data = signin_with_access_token(access_token)
        
        if not auth_data:
            # 严重错误，无数据返回
            return {
                "cookies": cookie_dict,
                "access_token": access_token,
                "token": None
            }, "errrrrr"
        
        # 即使有错误但还是获取到了auth_data，我们仍然继续使用
        token = auth_data.get('token') if auth_data else None
        account_type = auth_data.get('account_type') if auth_data else None
        auth = json.dumps(auth_data) if auth_data else None
        
        if not token:
            print("[ChatBetter] 未从API响应中获取到token")
            return {
                "cookies": cookie_dict,
                "access_token": access_token,
                "token": None
            }, "未获取到token"
            
        print(f"[ChatBetter] 获取到token: {token[:20]}...")
        
        # 返回完整的结果
        return {
            "cookies": cookie_dict,
            "access_token": access_token,
            "token": token,
            "auth": auth,
            "account_type": account_type
        }, None
            
    except Exception as e:
        msg=f"激活请求异常: {str(e)}"
        print(f"[ChatBetter] {msg}")
        return None, msg


def refresh_silent_cookies(cookies: dict) -> Tuple[bool, Optional[dict], Optional[str]]:
    """
    刷新silent cookies
    
    Args:
        cookies: 当前的cookies字典
        
    Returns:
        (成功标志, 新cookies字典, access_token)，如果刷新失败则返回(False, None, None)
    """
    if not cookies:
        print("[ChatBetter] cookies为空，无法刷新")
        return False, None, None
    
    try:
        # 准备请求
        payload = {
            "tenantId": None
        }
        
        # 发送请求
        response = requests.post(
            "https://auth.chatbetter.com/frontegg/oauth/authorize/silent",
            json=payload,
            headers=HEADERS,
            cookies=cookies
        )
        
        # 检查响应状态
        if response.status_code not in (200, 201):
            print(f"[ChatBetter] 刷新失败，状态码: {response.status_code}")
            return False, None, None
        
        # 从响应体中获取access_token
        try:
            response_data = response.json()
            access_token = response_data.get('access_token')
            if not access_token:
                print("[ChatBetter] 响应中没有access_token")
                return False, None, None
        except Exception as e:
            print(f"[ChatBetter] 解析响应体失败: {str(e)}")
            return False, None, None
        
        # 直接使用response.cookies获取字典
        cookie_dict = {cookie.name: cookie.value for cookie in response.cookies}
        
        # 检查必需cookie
        if not any(name.startswith('fe_device') for name in cookie_dict) or not any(name.startswith('fe_refresh') for name in cookie_dict):
            print("[ChatBetter] 刷新失败，未找到所需的cookies")
            return False, None, None
        
        #print(f"[ChatBetter] cookies刷新成功，获取到access_token: {access_token[:20]}...")
        return True, cookie_dict, access_token
    
    except Exception as e:
        print(f"[ChatBetter] 刷新cookies时发生异常: {str(e)}")
        return False, None, None
