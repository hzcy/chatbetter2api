from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from models import tokens
from routers import token, register, reverse
import os
import threading
import time
from utils.check_cookies import run_scheduler as run_cookies_scheduler, check_and_refresh_accounts
from utils.check_models import run_scheduler as run_models_scheduler, refresh_models
from utils.redis_cache import test_connection as test_redis_connection
from utils.account_manager import refresh_accounts_cache
from db import get_db
from env import PROXY_URL
import subprocess, shutil

# 创建FastAPI应用
app = FastAPI(
    title="ChatBetter2API",
    description="ChatBetter2API后端接口",
    version="0.1.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由器
app.include_router(token.router)
app.include_router(register.router)  # 添加注册路由器
app.include_router(reverse.router)  # 注册reverse路由器

# 后台线程
cookie_checker_thread = None
model_checker_thread = None
redis_refresher_thread = None

# 创建表和启动后台任务
@app.on_event("startup")
async def startup_event():
    # 设置全局代理（如果有配置）
    if PROXY_URL:
        os.environ["http_proxy"] = PROXY_URL
        os.environ["https_proxy"] = PROXY_URL
        print(f"已启用全局代理: {PROXY_URL}")

    # 创建数据库表
    tokens.create_tables()
    
    # 初始化Redis缓存
    try:
        if test_redis_connection():
            print("Redis连接成功，正在初始化缓存...")
            db = next(get_db())
            refresh_accounts_cache(db)
            db.close()
            print("Redis缓存初始化完成")
        else:
            print("Redis连接失败，将使用数据库作为备用")
    except Exception as e:
        print(f"Redis初始化失败: {str(e)}")
    
    # 启动cookie检查器线程
    global cookie_checker_thread, model_checker_thread, redis_refresher_thread
    
    def run_cookie_checker():
        # 在应用启动30秒后执行首次检查，确保应用完全初始化
        time.sleep(30)
        # 立即执行一次检查
        check_and_refresh_accounts()
        # 然后启动定时任务
        run_cookies_scheduler()
    
    # 创建并启动守护线程
    cookie_checker_thread = threading.Thread(target=run_cookie_checker, daemon=True)
    cookie_checker_thread.start()
    print("Cookie检查程序已在后台启动")

    # 启动模型刷新线程
    def run_model_checker():
        # 在应用启动60秒后执行首次刷新，确保应用和cookie都已初始化
        time.sleep(60)
        # 立即执行一次模型刷新
        refresh_models()
        # 然后启动定时任务
        run_models_scheduler()
    
    # 创建并启动模型刷新守护线程
    model_checker_thread = threading.Thread(target=run_model_checker, daemon=True)
    model_checker_thread.start()
    print("模型刷新程序已在后台启动")
    
    # 启动Redis缓存刷新线程
    def run_redis_refresher():
        # 应用启动后延迟15秒开始刷新，避免和其他任务冲突
        time.sleep(15)
        while True:
            try:
                # 每隔60秒刷新一次Redis缓存
                db = next(get_db())
                try:
                    refresh_accounts_cache(db)
                finally:
                    # 确保在任何情况下都关闭数据库连接
                    db.close()
            except Exception as e:
                print(f"Redis缓存刷新失败: {str(e)}")
            finally:
                # 每隔60秒刷新一次
                time.sleep(60)
    
    # 创建并启动Redis缓存刷新守护线程
    redis_refresher_thread = threading.Thread(target=run_redis_refresher, daemon=True)
    redis_refresher_thread.start()
    print("Redis缓存刷新程序已在后台启动")

# 首页
@app.get("/")
async def root():
    return {"message": "欢迎使用ChatBetter2API"}

# 静态文件目录
# 新的前端打包输出目录（Vite构建）
project_root = os.path.dirname(os.path.abspath(__file__))
frontend_src_path = os.path.join(project_root, "admin_frontend")
frontend_dist_path = os.path.join(frontend_src_path, "dist")


if not os.path.exists(frontend_dist_path):
    print("[Frontend] 未检测到前端构建产物，仅提供API")

# 创建静态文件目录
static_dir = os.path.join(project_root, "static")
files_dir = os.path.join(static_dir, "files")
os.makedirs(files_dir, exist_ok=True)

# 挂载静态文件目录，用于提供下载的图片
app.mount("/files", StaticFiles(directory=files_dir), name="files")

# 前端静态资源路径 (assets, js, css等)
if os.path.exists(frontend_dist_path):
    # 只为静态资源文件夹挂载静态服务，不包括根路径
    app.mount("/admin/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="admin_assets")
else:
    print("[Frontend] 警告: 未找到前端构建产物，管理后台不可用")

# 管理后台根路径
@app.get("/admin")
async def admin_root():
    return FileResponse(os.path.join(frontend_dist_path, "index.html"))

# 所有/admin/*路径的SPA前端路由请求
@app.get("/admin/{path:path}")
async def admin_spa_routes(path: str):
    # 如果请求的路径看起来像静态资源，尝试直接提供文件
    if path.startswith("assets/"):
        file_path = os.path.join(frontend_dist_path, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
    # 否则返回index.html让前端路由处理
    return FileResponse(os.path.join(frontend_dist_path, "index.html"))

# 启动服务器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8055)
