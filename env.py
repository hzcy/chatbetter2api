import os

# MySQL连接信息，从环境变量获取，如果没有则使用默认值
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'Shijie11')
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DB = os.environ.get('MYSQL_DB', 'chatbetter2api')

# 合并成一个环境变量
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

# Redis连接信息
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_ACCOUNT_CACHE_TTL = int(os.environ.get('REDIS_ACCOUNT_CACHE_TTL', 30))  # 账号缓存过期时间（秒）

# 代理配置（可选），如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080
PROXY_URL = os.environ.get('PROXY_URL')

# 管理员密码，从环境变量获取，如果没有则使用默认值
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '123456')

# 批量注册线程池最大线程数
REGISTER_MAX_THREADS = int(os.environ.get('REGISTER_MAX_THREADS', '10'))

FILE_DOMAIN = os.environ.get('FILE_DOMAIN', 'https://127.0.0.1:8055')