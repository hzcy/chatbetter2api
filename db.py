from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from env import DATABASE_URL

# 创建数据库引擎，增加连接池配置
engine = create_engine(
    DATABASE_URL,
    pool_size=50,  # 增加连接池大小
    max_overflow=100,  # 增加最大溢出连接数
    pool_timeout=60,  # 增加连接获取超时时间
    pool_recycle=1800,  # 每小时回收一次连接
    pool_pre_ping=True  # 每次连接前ping一下，确保连接有效
)

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
