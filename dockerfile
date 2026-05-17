FROM python:3.10-slim

LABEL author="ffing.cn" \
      desc="数据库管理工具：python3.10-flask项目镜像"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5001 5002

VOLUME [ "/app/conf", "/app/log", "/app/ssl","/app/img"]

ENTRYPOINT ["python", "app.py"]