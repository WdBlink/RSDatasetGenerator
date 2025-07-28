# RSDatasetGenerator Docker镜像
# 基于Python 3.8的轻量级Alpine Linux镜像

# 多阶段构建 - 构建阶段
FROM python:3.8-alpine as builder

# 设置工作目录
WORKDIR /app

# 安装构建依赖
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    geos-dev \
    proj-dev \
    gdal-dev \
    sqlite-dev \
    postgresql-dev \
    libffi-dev \
    openssl-dev \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    tk-dev \
    tcl-dev \
    harfbuzz-dev \
    fribidi-dev \
    libimagequant-dev \
    libxcb-dev \
    libpng-dev

# 升级pip并安装wheel
RUN pip install --upgrade pip wheel

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 多阶段构建 - 运行阶段
FROM python:3.8-alpine as runtime

# 设置标签
LABEL maintainer="RSDatasetGenerator Team <contact@rsdatasetgenerator.com>"
LABEL version="1.0.0"
LABEL description="遥感数据集生成器 - 从矢量文件生成遥感图像数据集"
LABEL org.opencontainers.image.source="https://github.com/your-username/RSDatasetGenerator"
LABEL org.opencontainers.image.documentation="https://rsdatasetgenerator.readthedocs.io/"
LABEL org.opencontainers.image.licenses="MIT"

# 安装运行时依赖
RUN apk add --no-cache \
    geos \
    proj \
    gdal \
    sqlite \
    postgresql-client \
    jpeg \
    zlib \
    freetype \
    lcms2 \
    openjpeg \
    tiff \
    tk \
    tcl \
    harfbuzz \
    fribidi \
    libimagequant \
    libxcb \
    libpng \
    bash \
    curl \
    ca-certificates

# 创建非root用户
RUN addgroup -g 1000 rsdg && \
    adduser -D -s /bin/bash -u 1000 -G rsdg rsdg

# 设置工作目录
WORKDIR /app

# 从构建阶段复制Python包
COPY --from=builder /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY --chown=rsdg:rsdg . .

# 安装应用
RUN pip install --no-deps -e .

# 创建必要的目录
RUN mkdir -p /app/data /app/output /app/cache /app/logs && \
    chown -R rsdg:rsdg /app

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV GDAL_DATA=/usr/share/gdal
ENV PROJ_LIB=/usr/share/proj

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import src.rs_dataset_generator; print('OK')" || exit 1

# 切换到非root用户
USER rsdg

# 暴露端口（如果有Web界面）
# EXPOSE 8000

# 设置卷
VOLUME ["/app/data", "/app/output", "/app/cache"]

# 默认命令
CMD ["rs-dataset-generator", "--help"]

# 构建参数
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# 添加构建信息标签
LABEL org.opencontainers.image.created=$BUILD_DATE
LABEL org.opencontainers.image.revision=$VCS_REF
LABEL org.opencontainers.image.version=$VERSION

# 使用示例:
# docker build -t rs-dataset-generator .
# docker run -v $(pwd)/data:/app/data -v $(pwd)/output:/app/output rs-dataset-generator

# 开发模式运行:
# docker run -it --rm -v $(pwd):/app rs-dataset-generator bash

# 生产模式运行:
# docker run -d --name rsdg \
#   -v /path/to/data:/app/data \
#   -v /path/to/output:/app/output \
#   -v /path/to/cache:/app/cache \
#   rs-dataset-generator \
#   rs-dataset-generator /app/data/input.geojson /app/output --zoom-level 18