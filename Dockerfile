# syntax=docker/dockerfile:1

# ---- PanSou 后端：在构建机原生架构上交叉编译 ----
FROM --platform=$BUILDPLATFORM golang:1.25-alpine AS backend
RUN apk add --no-cache git
WORKDIR /build
COPY backend/ ./backend/
ARG TARGETARCH
RUN sh backend/build.sh --arch "${TARGETARCH:-amd64}" --out /out

# ---- 运行镜像：机器人 + 后端 ----
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY src/ ./src/
COPY --from=backend /out/ /opt/pansou/

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /data \
    && chown bot:bot /data
USER bot

ARG VERSION=dev
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    PANSOU_BACKEND=builtin \
    BACKEND_BUNDLED_DIR=/opt/pansou \
    APP_VERSION=${VERSION}

VOLUME ["/data"]
# 只有需要从容器外直接调用搜索 API 时才映射这个端口
EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD ["python", "/app/src/healthcheck.py"]

ENTRYPOINT ["tini", "--"]
CMD ["python", "main.py"]
