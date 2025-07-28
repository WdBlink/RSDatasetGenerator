# 遥感数据集生成器 (Remote Sensing Dataset Generator)

[![CI/CD](https://github.com/your-username/RSDatasetGenerator/workflows/CI/badge.svg)](https://github.com/your-username/RSDatasetGenerator/actions)
[![Docker](https://img.shields.io/docker/v/your-username/rsdatasetgenerator?label=docker)](https://hub.docker.com/r/your-username/rsdatasetgenerator)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

一个基于Python的专业工具，用于根据矢量文件（如Shapefile、GeoJSON）中的地理点信息，自动下载对应区域的Google地图遥感图像，并生成包含像素坐标映射的完整数据集。

## 🚀 快速开始

### 使用Docker（推荐）

```bash
# 克隆项目
git clone https://github.com/your-username/RSDatasetGenerator.git
cd RSDatasetGenerator

# 使用Docker Compose启动
docker-compose up -d

# 或者使用Makefile
make docker-up
```

### 本地安装

```bash
# 安装依赖
make install

# 或者手动安装
pip install -r requirements.txt
pip install -e .
```

## 主要功能

✅ **矢量文件支持**: 读取Shapefile格式的矢量数据  
✅ **Google地图集成**: 从Google卫星影像服务下载高质量遥感图像  
✅ **瓦片拼接**: 自动下载并拼接多个瓦片形成完整区域图像  
✅ **元数据保存**: 保存坐标信息、瓦片信息等元数据  
✅ **高性能下载**: 支持异步并发下载，提升效率  
✅ **智能重试**: 内置重试机制和请求间隔控制  

## 📁 项目结构

```
RSDatasetGenerator/
├── src/                    # 源代码目录
│   └── rsdatasetgenerator/ # 主包
├── tests/                  # 测试文件
├── docs/                   # 文档
├── scripts/                # 脚本文件
├── data/                   # 数据目录
├── shp-temp/              # 示例Shapefile数据
│   ├── NingXia.*          # 宁夏地区矢量数据
│   ├── temp_comm.*        # 社区点位数据
│   └── temp_gansu.*       # 甘肃地区矢量数据
├── .github/               # GitHub Actions配置
│   └── workflows/
│       └── ci.yml         # CI/CD流水线
├── config.yaml            # 主配置文件
├── docker-compose.yml     # Docker Compose配置
├── Dockerfile             # Docker镜像构建
├── Makefile              # 开发工具命令
├── pyproject.toml        # 项目配置
├── setup.py              # 安装配置
├── setup.cfg             # 工具配置
├── requirements.txt      # 依赖列表
├── .pre-commit-config.yaml # 预提交钩子
├── .gitignore            # Git忽略文件
├── LICENSE               # 许可证
├── CHANGELOG.md          # 更新日志
└── README.md             # 项目说明
```

## 🛠️ 环境要求

### Python版本
- Python 3.8+

### 系统要求
- 内存：建议4GB+
- 存储：根据数据量需求
- 网络：稳定的互联网连接

### 依赖包
核心依赖已在 `requirements.txt` 中定义：
```bash
# 安装所有依赖
pip install -r requirements.txt

# 或安装开发依赖
pip install -r requirements-dev.txt
```

主要依赖包括：
- `geopandas`: 地理数据处理
- `Pillow`: 图像处理
- `requests/aiohttp`: HTTP请求
- `shapely`: 几何计算
- `mercantile`: 瓦片计算
- `psutil`: 系统监控

## 📖 使用方法

### 配置文件

项目使用 `config.yaml` 进行配置管理：

```yaml
# 基本配置示例
download:
  zoom_level: 18
  grid_size: 5
  max_concurrent: 8
  
paths:
  output_dir: "./output"
  cache_dir: "./cache"
  
network:
  timeout: 30
  max_retries: 3
```

### 命令行使用

```bash
# 基本使用
rsdg --input data.shp --output ./results

# 指定配置文件
rsdg --config custom_config.yaml --input data.shp

# 使用Docker
docker run -v $(pwd)/data:/data rsdatasetgenerator \
  --input /data/shapefile.shp --output /data/output
```

### Python API

```python
from rsdatasetgenerator import RSDatasetGenerator

# 创建生成器实例
generator = RSDatasetGenerator(config_path="config.yaml")

# 处理数据
results = generator.process_shapefile(
    input_path="data.shp",
    output_dir="./output"
)
```

### 开发模式

```bash
# 安装开发依赖
make install-dev

# 运行测试
make test

# 代码格式化
make format

# 类型检查
make type-check

# 查看所有可用命令
make help
```

### 🐳 Docker部署

#### 开发环境
```bash
# 启动开发环境（包含热重载）
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# 或使用Makefile
make docker-dev
```

#### 生产环境
```bash
# 启动生产环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 或使用Makefile
make docker-prod
```

#### 监控和日志
```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f rsdg

# 访问监控面板
# Grafana: http://localhost:3000
# Prometheus: http://localhost:9090
```

### ⚙️ 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input` | 输入Shapefile路径 | 必需 |
| `--output` | 结果输出目录 | 必需 |
| `--config` | 配置文件路径 | config.yaml |
| `--zoom` | 瓦片缩放级别 | 18 |
| `--grid` | 瓦片网格尺寸 | 5 |
| `--threads` | 最大并发线程数 | 8 |
| `--timeout` | 请求超时时间（秒） | 30.0 |
| `--retries` | 最大重试次数 | 3 |
| `--verbose` | 详细输出模式 | False |

## 输入数据要求

### Shapefile格式要求
- 必须包含完整的Shapefile文件集（.shp, .shx, .dbf等）
- 几何类型：点要素（Point）
- 必需字段：`osm_id`（用作唯一标识符）
- 坐标系统：建议使用WGS84（EPSG:4326）

### 示例数据结构
```
osm_id    | geometry
----------|------------------
12345     | POINT(106.5 35.2)
12346     | POINT(106.6 35.3)
```

## 输出数据说明

### 图像文件
- 格式：PNG
- 命名：`{osm_id}_{zoom}_{tile_x}_{tile_y}.png`
- 尺寸：256 × grid_size 像素

### 元数据文件
- 格式：JSON
- 命名：`{osm_id}_{zoom}_{tile_x}_{tile_y}.json`
- 内容：坐标信息、瓦片信息、像素坐标等

### 元数据示例
```json
{
  "image": "12345_18_123456_78910.png",
  "tile_center": {
    "z": 18,
    "x": 123456,
    "y": 78910
  },
  "points": [
    {
      "id": "12345",
      "pixel_x": 640,
      "pixel_y": 640
    }
  ]
}
```

## ⚡ 技术特性

### 🗺️ 瓦片系统
- 使用Web Mercator投影（EPSG:3857）
- 支持1-20级缩放
- 标准256×256像素瓦片
- 多种瓦片源支持（Google、OpenStreetMap等）

### 🚀 性能优化
- 异步并发下载
- 智能缓存机制
- 内存使用监控
- 网络请求优化
- 连接池管理
- 断点续传支持

### 🛡️ 错误处理
- 自动重试机制
- 指数退避策略
- 详细错误日志
- 进度监控报告
- 健康检查

### 🔧 开发工具
- 完整的CI/CD流水线
- 自动化测试（单元测试、集成测试）
- 代码质量检查（Black、Flake8、MyPy）
- 预提交钩子
- 自动化文档生成
- 性能分析工具

### 📊 监控和日志
- Prometheus指标收集
- Grafana可视化面板
- 结构化日志输出
- 性能指标追踪
- 错误率监控

## ⚠️ 注意事项

1. **使用限制**: 请遵守Google地图服务条款，避免过于频繁的请求
2. **网络环境**: 确保网络连接稳定，建议使用VPN以获得更好的访问速度
3. **存储空间**: 高分辨率图像占用空间较大，请确保有足够的存储空间
4. **坐标系统**: 输入数据建议使用WGS84坐标系统
5. **资源限制**: 在Docker环境中注意内存和CPU限制配置
6. **安全性**: 生产环境请修改默认密码和API密钥

## 🔧 开发指南

### 环境设置
```bash
# 克隆项目
git clone https://github.com/your-username/RSDatasetGenerator.git
cd RSDatasetGenerator

# 设置开发环境
make setup-dev

# 安装预提交钩子
pre-commit install
```

### 代码规范
- 使用Black进行代码格式化
- 使用MyPy进行类型检查
- 使用Pytest进行测试
- 遵循PEP 8编码规范

### 测试
```bash
# 运行所有测试
make test

# 运行特定测试
pytest tests/test_specific.py

# 生成覆盖率报告
make coverage
```

### 构建和发布
```bash
# 构建包
make build

# 发布到PyPI（需要配置凭据）
make publish

# 构建Docker镜像
make docker-build
```

## 常见问题

### Q: 下载速度很慢怎么办？
A: 可以调整并发线程数（--threads）和请求间隔参数，但不要设置过高以避免被封禁。

### Q: 部分瓦片下载失败？
A: 这是正常现象，程序会自动重试。如果持续失败，可能是网络问题或该区域无影像数据。

### Q: 如何选择合适的缩放级别？
A: 缩放级别越高，图像分辨率越高，但下载时间和存储空间需求也越大。建议根据实际需求选择：
- 级别15-16：适合大区域概览
- 级别17-18：适合详细分析
- 级别19-20：适合精细研究

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 贡献

欢迎提交Issue和Pull Request来改进项目。
