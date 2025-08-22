import json
import logging
import threading
import time
import schedule
import os
import traceback
import requests
import re
from sqlalchemy import desc
from datetime import datetime
from models.tokens import Token
from db import get_db
from sqlalchemy.orm import Session

# 配置日志
logging.basicConfig(
    filename="models_checker.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("models_checker")

# 模型缓存文件
MODELS_FILE = "routers/models.json"

# 标志位，用于控制run_scheduler函数中的循环
_running = False

def refresh_models():
    """
    从账号中刷新模型列表并保存到本地
    """
    logger.info("开始执行模型刷新任务...")
    
    db = None
    try:
        db = next(get_db())
        
        # 获取一个启用的账号，优先选择最近token_expires更新的
        account = (
            db.query(Token)
            .filter(Token.enable == 1, Token.deleted_at == None)
            .order_by(desc(Token.token_expires))
            .first()
        )
        
        if not account:
            logger.error("没有可用账号，无法获取模型信息")
            return
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {account.token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cookie": f"token={account.token}; ChatBetterJwt={account.access_token}",
            "Content-Type": "application/json"
        }
        
        # 获取模型信息
        try:
            response = requests.get("https://app.chatbetter.com/api/v1/models", headers=headers)
            if response.status_code == 200:
                models_data = response.json()
                
                # 保存到本地文件
                with open(MODELS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(models_data, f, indent=2, ensure_ascii=False)
                
                logger.info("模型信息已成功刷新")
                return
            else:
                logger.error(f"获取模型信息失败: HTTP {response.status_code}")
        except Exception as e:
            logger.exception(f"请求模型API失败: {str(e)}")
    except Exception as e:
        logger.exception(f"模型刷新过程中发生错误: {str(e)}")
    finally:
        # 确保数据库连接被关闭
        if db:
            db.close()
    
    logger.info("模型刷新任务执行完毕")

def run_scheduler():
    """
    运行定时任务：每6小时刷新一次模型列表
    """
    global _running
    if _running:
        return
    
    _running = True
    
    # 设置每6小时执行一次
    schedule.every(6).hours.do(refresh_models)
    
    # 运行循环
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次是否有待执行的任务 