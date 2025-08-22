FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . /app/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 返回到应用根目录
WORKDIR /app

# 创建静态文件目录
RUN mkdir -p static/files

# 暴露端口
EXPOSE 8055

# 设置环境变量（可在运行容器时覆盖）
ENV MYSQL_USER=root
ENV MYSQL_PASSWORD=123456
ENV MYSQL_HOST=mysql
ENV MYSQL_PORT=3306
ENV MYSQL_DB=chatbetter2api
ENV FILE_DOMAIN=http://127.0.0.1:8055

# 启动命令：先执行数据库迁移，再启动应用
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8055"] 