# RSDatasetGenerator Makefile
# 遥感数据集生成器的构建和开发工具

.PHONY: help install install-dev test lint format clean build docker run docs deploy

# 默认目标
help:
	@echo "RSDatasetGenerator - 遥感数据集生成器"
	@echo ""
	@echo "可用命令:"
	@echo "  install      - 安装生产依赖"
	@echo "  install-dev  - 安装开发依赖"
	@echo "  test         - 运行测试"
	@echo "  test-cov     - 运行测试并生成覆盖率报告"
	@echo "  lint         - 代码检查"
	@echo "  format       - 代码格式化"
	@echo "  type-check   - 类型检查"
	@echo "  security     - 安全检查"
	@echo "  clean        - 清理临时文件"
	@echo "  build        - 构建包"
	@echo "  docker       - 构建Docker镜像"
	@echo "  docker-run   - 运行Docker容器"
	@echo "  docs         - 生成文档"
	@echo "  docs-serve   - 启动文档服务器"
	@echo "  run          - 运行应用"
	@echo "  run-example  - 运行示例"
	@echo "  deploy       - 部署到生产环境"
	@echo "  version      - 显示版本信息"

# 安装依赖
install:
	@echo "安装生产依赖..."
	pip install -r requirements.txt
	pip install -e .

install-dev:
	@echo "安装开发依赖..."
	pip install -r requirements.txt
	pip install -e ".[dev]"
	pre-commit install

# 测试
test:
	@echo "运行测试..."
	pytest tests/ -v

test-cov:
	@echo "运行测试并生成覆盖率报告..."
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-integration:
	@echo "运行集成测试..."
	pytest tests/integration/ -v

test-performance:
	@echo "运行性能测试..."
	pytest tests/performance/ -v

# 代码质量
lint:
	@echo "运行代码检查..."
	flake8 src/ tests/
	pylint src/

format:
	@echo "格式化代码..."
	black src/ tests/
	isort src/ tests/

type-check:
	@echo "运行类型检查..."
	mypy src/

security:
	@echo "运行安全检查..."
	bandit -r src/
	safety check

# 清理
clean:
	@echo "清理临时文件..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .tox/
	rm -rf output/
	rm -rf cache/
	rm -rf temp/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# 构建
build: clean
	@echo "构建包..."
	python -m build

wheel:
	@echo "构建wheel包..."
	python setup.py bdist_wheel

sdist:
	@echo "构建源码包..."
	python setup.py sdist

# Docker
docker:
	@echo "构建Docker镜像..."
	docker build -t rs-dataset-generator:latest .

docker-dev:
	@echo "构建开发Docker镜像..."
	docker build -f Dockerfile.dev -t rs-dataset-generator:dev .

docker-run:
	@echo "运行Docker容器..."
	docker run -it --rm \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/output:/app/output \
		rs-dataset-generator:latest

docker-compose-up:
	@echo "启动Docker Compose服务..."
	docker-compose up -d

docker-compose-down:
	@echo "停止Docker Compose服务..."
	docker-compose down

# 文档
docs:
	@echo "生成文档..."
	cd docs && make html

docs-serve:
	@echo "启动文档服务器..."
	cd docs/_build/html && python -m http.server 8000

docs-clean:
	@echo "清理文档..."
	cd docs && make clean

# 运行
run:
	@echo "运行应用..."
	python -m src.rs_dataset_generator --help

run-example:
	@echo "运行示例..."
	python -m src.rs_dataset_generator \
		data/example.geojson \
		output/ \
		--zoom-level 18 \
		--grid-size 5

run-dev:
	@echo "运行开发模式..."
	python -m src.rs_dataset_generator \
		--config config.yaml \
		--debug \
		data/example.geojson \
		output/

# 发布
upload-test:
	@echo "上传到测试PyPI..."
	twine upload --repository testpypi dist/*

upload:
	@echo "上传到PyPI..."
	twine upload dist/*

# 部署
deploy-staging:
	@echo "部署到测试环境..."
	# 添加部署到测试环境的命令

deploy-prod:
	@echo "部署到生产环境..."
	# 添加部署到生产环境的命令

deploy: build docker
	@echo "部署应用..."
	# 添加部署命令

# 版本管理
version:
	@echo "当前版本信息:"
	@python -c "import src.rs_dataset_generator; print(f'版本: {src.rs_dataset_generator.__version__}')"
	@git describe --tags --always

bump-patch:
	@echo "升级补丁版本..."
	bump2version patch

bump-minor:
	@echo "升级次版本..."
	bump2version minor

bump-major:
	@echo "升级主版本..."
	bump2version major

# 开发工具
setup-dev:
	@echo "设置开发环境..."
	python -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && make install-dev

activate:
	@echo "激活虚拟环境:"
	@echo "source venv/bin/activate"

check-deps:
	@echo "检查依赖更新..."
	pip list --outdated

update-deps:
	@echo "更新依赖..."
	pip install --upgrade -r requirements.txt

# 数据管理
download-sample:
	@echo "下载示例数据..."
	mkdir -p data
	curl -o data/example.geojson https://raw.githubusercontent.com/example/sample-data/main/example.geojson

clean-data:
	@echo "清理数据文件..."
	rm -rf data/temp/*
	rm -rf cache/*

# 监控和分析
profile:
	@echo "性能分析..."
	python -m cProfile -o profile.stats -m src.rs_dataset_generator data/example.geojson output/
	python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"

memory-profile:
	@echo "内存分析..."
	mprof run python -m src.rs_dataset_generator data/example.geojson output/
	mprof plot

# 持续集成
ci: lint type-check security test-cov
	@echo "持续集成检查完成"

# 预提交检查
pre-commit:
	@echo "运行预提交检查..."
	pre-commit run --all-files

# 全面检查
check-all: clean install-dev lint type-check security test-cov docs
	@echo "全面检查完成"

# 发布准备
release-prep: check-all build
	@echo "发布准备完成"

# 快速开始
quickstart: setup-dev download-sample run-example
	@echo "快速开始完成"

# 帮助信息
info:
	@echo "项目信息:"
	@echo "  名称: RSDatasetGenerator"
	@echo "  描述: 遥感数据集生成器"
	@echo "  版本: $(shell python -c 'import src.rs_dataset_generator; print(src.rs_dataset_generator.__version__)')"
	@echo "  Python: $(shell python --version)"
	@echo "  平台: $(shell uname -s)"
	@echo "  架构: $(shell uname -m)"