# RSDatasetGenerator 本地部署指南

本文档提供了使用 Conda 或 Poetry 在本地部署 RSDatasetGenerator 项目的详细说明。

## 系统要求

- Python 3.8 或更高版本
- Windows 10/11, macOS 10.15+, 或 Linux
- 至少 4GB 可用内存
- 至少 2GB 可用磁盘空间

## 方法一：使用 Conda 部署（推荐）

### 1. 安装 Anaconda 或 Miniconda

如果您还没有安装 Conda，请从以下链接下载并安装：
- [Anaconda](https://www.anaconda.com/products/distribution)（完整版）
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html)（轻量版，推荐）

### 2. 创建 Conda 环境

```bash
# 克隆项目（如果还没有）
git clone <repository-url>
cd RSDatasetGenerator

# 使用环境配置文件创建环境
conda env create -f environment.yml

# 激活环境
conda activate rs-dataset-generator
```

### 3. 安装项目

```bash
# 以开发模式安装项目
pip install -e .

# 或者安装包含所有可选依赖
pip install -e ".[all]"
```

### 4. 验证安装

```bash
# 检查命令行工具
rs-dataset-generator --help

# 或使用简短命令
rsdg --help

# 运行测试
pytest tests/
```

## 方法二：使用 Poetry 部署

### 1. 安装 Poetry

```bash
# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -

# 或使用 pip 安装
pip install poetry
```

### 2. 配置 Poetry（可选）

```bash
# 配置虚拟环境在项目目录中创建
poetry config virtualenvs.in-project true

# 配置使用清华镜像源（中国用户推荐）
poetry config repositories.tsinghua https://pypi.tuna.tsinghua.edu.cn/simple/
poetry config pypi-token.tsinghua <your-token>
```

### 3. 安装依赖

```bash
# 克隆项目（如果还没有）
git clone <repository-url>
cd RSDatasetGenerator

# 安装项目依赖
poetry install

# 安装包含开发依赖
poetry install --with dev

# 安装所有可选依赖
poetry install --extras "all"
```

### 4. 激活虚拟环境

```bash
# 激活 Poetry 虚拟环境
poetry shell

# 或者直接运行命令
poetry run rs-dataset-generator --help
```

### 5. 验证安装

```bash
# 在 Poetry 环境中运行
poetry run rs-dataset-generator --help
poetry run pytest tests/
```

## 方法三：使用 pip 直接安装

### 1. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 2. 安装项目

```bash
# 克隆项目
git clone <repository-url>
cd RSDatasetGenerator

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt

# 安装项目
pip install -e .
```

## 配置项目

### 1. 复制配置文件

```bash
# 复制默认配置文件
cp config.yaml config.local.yaml
```

### 2. 编辑配置文件

根据您的需求编辑 `config.local.yaml` 文件：

```yaml
# 下载配置
download:
  zoom_level: 18          # 瓦片缩放级别
  max_concurrency: 10     # 最大并发数
  request_timeout: 30     # 请求超时时间

# 路径配置
paths:
  output_dir: "output"    # 输出目录
  cache_dir: "cache"      # 缓存目录
  log_dir: "logs"         # 日志目录
```

### 3. 创建必要目录

```bash
# 创建数据目录
mkdir -p data output cache logs temp
```

## 使用示例

### 基本使用

```bash
# 从 GeoJSON 文件生成数据集
rs-dataset-generator data/points.geojson output/ --zoom-level 18

# 使用自定义配置文件
rs-dataset-generator data/points.geojson output/ --config config.local.yaml

# 启用详细日志
rs-dataset-generator data/points.geojson output/ --verbose
```

### Python API 使用

```python
from src.rs_dataset_generator import RSDatasetGenerator
from src.config import load_config

# 加载配置
config = load_config('config.yaml')

# 创建生成器实例
generator = RSDatasetGenerator(config)

# 生成数据集
result = generator.generate_dataset(
    input_file='data/points.geojson',
    output_dir='output/',
    zoom_level=18
)

print(f"生成了 {result.total_images} 张图像")
```

## 开发环境设置

### 1. 安装开发依赖

```bash
# Conda 环境
conda activate rs-dataset-generator
pip install -e ".[dev]"

# Poetry 环境
poetry install --with dev
```

### 2. 设置 Pre-commit 钩子

```bash
# 安装 pre-commit 钩子
pre-commit install

# 手动运行所有钩子
pre-commit run --all-files
```

### 3. 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_core.py

# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 4. 代码格式化

```bash
# 格式化代码
black src/ tests/

# 排序导入
isort src/ tests/

# 类型检查
mypy src/

# 代码质量检查
flake8 src/ tests/
```

## 故障排除

### 常见问题

1. **GDAL 安装问题**
   ```bash
   # 在 conda 环境中重新安装 GDAL
   conda install -c conda-forge gdal
   ```

2. **网络连接问题**
   - 检查防火墙设置
   - 配置代理（如果需要）
   - 使用国内镜像源

3. **权限问题**
   ```bash
   # 确保输出目录有写权限
   chmod 755 output/
   ```

4. **内存不足**
   - 减少并发数量
   - 增加系统虚拟内存
   - 使用较小的网格大小

### 获取帮助

- 查看详细帮助：`rs-dataset-generator --help`
- 查看版本信息：`rs-dataset-generator --version`
- 提交问题：[GitHub Issues](https://github.com/your-username/RSDatasetGenerator/issues)
- 查看文档：[在线文档](https://rsdatasetgenerator.readthedocs.io/)

## 性能优化建议

1. **使用 SSD 存储**：将缓存和输出目录放在 SSD 上
2. **调整并发数**：根据网络带宽和系统性能调整 `max_concurrency`
3. **启用缓存**：设置 `enable_cache: true` 避免重复下载
4. **批处理**：一次处理多个点而不是单独处理
5. **监控资源**：使用 `--monitor` 选项监控系统资源使用情况

## 更新项目

### Conda 环境更新

```bash
# 更新环境
conda env update -f environment.yml

# 重新安装项目
pip install -e .
```

### Poetry 环境更新

```bash
# 更新依赖
poetry update

# 重新安装项目
poetry install
```