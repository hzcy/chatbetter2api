import os

# 数据库连接配置
# 优先使用 DATABASE_DSN，否则使用单独的 MySQL 环境变量
DATABASE_DSN = os.environ.get('DATABASE_DSN')

if DATABASE_DSN:
    # 将 tcp 格式转换为 mysql+pymysql 格式
    if DATABASE_DSN.startswith('mysql://'):
        DATABASE_URL = DATABASE_DSN.replace('mysql://', 'mysql+pymysql://', 1)
    elif '@tcp(' in DATABASE_DSN:
        # 解析 DSN 格式: user:password@tcp(host:port)/database
        import re
        match = re.match(r'([^:]+):([^@]+)@tcp\(([^:]+):(\d+)\)/(.+)', DATABASE_DSN)
        if match:
            user, password, host, port, database = match.groups()
            DATABASE_URL = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        else:
            raise ValueError(f"无法解析 DATABASE_DSN 格式: {DATABASE_DSN}")
    else:
        DATABASE_URL = DATABASE_DSN
else:
    # MySQL连接信息，从环境变量获取，如果没有则使用默认值
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'Shijie11')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'chatbetter2api')

    # 合并成一个环境变量
    DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

# Redis连接信息
# 支持 Redis URL 格式（如 Upstash）或传统配置方式
REDIS_URL = os.environ.get('REDIS_URL')

if REDIS_URL:
    # 使用 Redis URL 连接
    import redis
    redis_client_config = redis.from_url(REDIS_URL, decode_responses=True)
    # 从 URL 解析基本信息用于兼容性
    REDIS_HOST = 'upstash-redis'  # 标识使用 URL 连接
    REDIS_PORT = 6379
    REDIS_DB = 0
    REDIS_PASSWORD = None
else:
    # 传统方式配置
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
    redis_client_config = None

REDIS_ACCOUNT_CACHE_TTL = int(os.environ.get('REDIS_ACCOUNT_CACHE_TTL', 30))  # 账号缓存过期时间（秒）

# 代理配置（可选），如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080
PROXY_URL = os.environ.get('PROXY_URL')

# 管理员密码，从环境变量获取，如果没有则使用默认值
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '123456')

# 批量注册线程池最大线程数
REGISTER_MAX_THREADS = int(os.environ.get('REGISTER_MAX_THREADS', '10'))

FILE_DOMAIN = os.environ.get('FILE_DOMAIN', 'https://127.0.0.1:8055')
