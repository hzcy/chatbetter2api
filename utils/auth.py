from fastapi import HTTPException, Header
from typing import Optional
import re
from env import ADMIN_PASSWORD

def extract_password_from_auth_header(authorization: str) -> str:
    """从Authorization头部提取密码
    支持格式:
    - "Bearer {password}"
    - "{password}"
    """
    if not authorization:
        return ""
    
    # 尝试解析Bearer格式
    bearer_match = re.match(r"^Bearer\s+(.+)$", authorization, re.IGNORECASE)
    if bearer_match:
        return bearer_match.group(1)
    
    # 如果不是Bearer格式，直接返回整个值
    return authorization

async def verify_admin(authorization: Optional[str] = Header(None)):
    """验证请求头中的Authorization是否匹配ADMIN_PASSWORD
    
    用法:
    ```
    @router.get("/your-endpoint")
    def your_endpoint(_: bool = Depends(verify_admin)):
        # 已通过身份验证的代码
    ```
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="未提供身份验证凭据",
            headers={"Authorization": "Bearer"},
        )
    
    password = extract_password_from_auth_header(authorization)
    if password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="无效的身份验证凭据",
            headers={"Authorization": "Bearer"},
        )
    
    return True 