# ChatBetter2API

ChatBetter2API 是一个用于代理 ChatBetter 服务的 API 接口。

## 使用 Redis 缓存优化账号选择

为了解决高并发请求下数据库连接数过大的问题，项目引入了 Redis 缓存层来优化账号选择逻辑。

### Redis 缓存的主要优势

- **减少数据库查询**：在高并发请求时，不再需要每次都从数据库查询账号
- **降低数据库连接压力**：避免大量并发请求同时查询数据库导致连接池溢出
- **提高响应速度**：从 Redis 获取账号信息速度更快
- **分散数据库访问压力**：通过周期性批量刷新缓存替代实时查询

### Redis 缓存架构

Redis 缓存系统主要包含以下几个部分：

1. **Redis 连接层**：负责处理与 Redis 服务器的连接和基本操作
2. **账号缓存**：维护可用账号列表和详细信息
3. **定期刷新机制**：每隔一段时间从数据库更新缓存

### 环境变量配置

在 `env.py` 文件中添加了以下 Redis 相关配置：

```python
# Redis 连接信息
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_ACCOUNT_CACHE_TTL = int(os.environ.get('REDIS_ACCOUNT_CACHE_TTL', 30))  # 账号缓存过期时间（秒）
```

### Docker 环境配置

在 `docker-compose.yml` 文件中，已添加 Redis 服务：

```yaml
# Redis服务
redis:
  image: redis:7.0
  container_name: chatbetter2api-redis
  restart: always
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes
```

并在应用服务中添加了相关环境变量：

```yaml
environment:
  # 其他环境变量...
  - REDIS_HOST=redis
  - REDIS_PORT=6379
```

### 故障恢复机制

- 如果 Redis 服务不可用，系统会自动回退到直接查询数据库
- 每个操作都包含异常处理，确保即使缓存失败也不会影响正常功能
- 系统启动时会自动检测 Redis 是否可用，如不可用则使用数据库作为备用

### 缓存策略

- **过期时间**：账号缓存默认过期时间为 30 秒，可通过环境变量修改
- **周期刷新**：后台任务每 60 秒刷新一次缓存内容
- **自动更新**：账号状态变更时（启用/禁用）会同步更新缓存

### 调试信息

系统会在控制台输出关于 Redis 缓存的调试信息：

- Redis 连接状态
- 缓存初始化结果
- 缓存刷新成功或失败通知

## 部署说明

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

可以在 `.env` 文件中配置必要的环境变量，或直接在 `docker-compose.yml` 中设置。

### 3. 使用 Docker 部署

```bash
docker-compose up -d
```

这将启动 MySQL、Redis 和应用服务。

### 4. 直接运行

```bash
uvicorn main:app --host 0.0.0.0 --port 8055
```

## API 端点

- `/v1/chat/completions` - 聊天完成API
- 其他API端点...

## 技术栈

- FastAPI
- SQLAlchemy
- Redis
- MySQL
- Docker 