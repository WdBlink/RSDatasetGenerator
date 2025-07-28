#!/usr/bin/env python3
"""RSDatasetGenerator安装脚本

这个脚本用于安装RSDatasetGenerator包，使其可以作为Python包进行分发和安装。
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages

# 确保Python版本
if sys.version_info < (3, 8):
    raise RuntimeError("RSDatasetGenerator需要Python 3.8或更高版本")

# 获取项目根目录
HERE = Path(__file__).parent.absolute()

# 读取README文件
readme_file = HERE / "README.md"
if readme_file.exists():
    with open(readme_file, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "遥感数据集生成器 - 从矢量文件生成遥感图像数据集"

# 读取requirements文件
requirements_file = HERE / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file, "r", encoding="utf-8") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
else:
    # 基本依赖
    requirements = [
        "geopandas>=0.14.0",
        "shapely>=2.0.0",
        "fiona>=1.9.0",
        "pyproj>=3.6.0",
        "requests>=2.31.0",
        "aiohttp>=3.9.0",
        "aiofiles>=23.2.0",
        "Pillow>=10.0.0",
        "numpy>=1.24.0",
        "pyyaml>=6.0.1",
        "tqdm>=4.66.0",
        "psutil>=5.9.0",
        "click>=8.1.0",
        "colorama>=0.4.6",
        "tabulate>=0.9.0"
    ]

# 开发依赖
dev_requirements = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.7.0",
    "flake8>=6.0.0",
    "mypy>=1.5.0",
    "isort>=5.12.0",
    "pre-commit>=3.3.0"
]

# 文档依赖
docs_requirements = [
    "sphinx>=7.1.0",
    "sphinx-rtd-theme>=1.3.0",
    "myst-parser>=2.0.0"
]

# 性能测试依赖
benchmark_requirements = [
    "memory-profiler>=0.61.0",
    "line-profiler>=4.1.0",
    "py-spy>=0.3.14"
]

# 版本信息
version_file = HERE / "src" / "__init__.py"
version = "1.0.0"  # 默认版本

if version_file.exists():
    with open(version_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                version = line.split("=")[1].strip().strip('"').strip("'")
                break

# 包信息
setup(
    name="rs-dataset-generator",
    version=version,
    author="RSDatasetGenerator Team",
    author_email="contact@rsdatasetgenerator.com",
    description="从矢量文件生成遥感图像数据集的工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/RSDatasetGenerator",
    project_urls={
        "Bug Reports": "https://github.com/your-username/RSDatasetGenerator/issues",
        "Source": "https://github.com/your-username/RSDatasetGenerator",
        "Documentation": "https://rsdatasetgenerator.readthedocs.io/",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
    ],
    keywords="gis, remote sensing, satellite imagery, dataset generation, geospatial",
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
        "docs": docs_requirements,
        "benchmark": benchmark_requirements,
        "all": dev_requirements + docs_requirements + benchmark_requirements,
    },
    entry_points={
        "console_scripts": [
            "rs-dataset-generator=src.cli:main",
            "rsdg=src.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "src": [
            "config/*.yaml",
            "config/*.yml",
            "templates/*.json",
            "templates/*.yaml",
        ],
    },
    zip_safe=False,
    platforms=["any"],
    license="MIT",
    # 测试配置
    test_suite="tests",
    tests_require=[
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.1.0",
    ],
    # 项目元数据
    project_urls={
        "Homepage": "https://github.com/your-username/RSDatasetGenerator",
        "Documentation": "https://rsdatasetgenerator.readthedocs.io/",
        "Repository": "https://github.com/your-username/RSDatasetGenerator.git",
        "Bug Tracker": "https://github.com/your-username/RSDatasetGenerator/issues",
        "Changelog": "https://github.com/your-username/RSDatasetGenerator/blob/main/CHANGELOG.md",
    },
)

# 安装后的验证
if __name__ == "__main__":
    print("RSDatasetGenerator安装配置完成")
    print(f"版本: {version}")
    print(f"Python要求: >=3.8")
    print(f"依赖包数量: {len(requirements)}")
    
    # 检查关键依赖
    critical_deps = ["geopandas", "requests", "Pillow", "numpy"]
    missing_deps = []
    
    for dep in critical_deps:
        if not any(dep.lower() in req.lower() for req in requirements):
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"警告: 缺少关键依赖: {', '.join(missing_deps)}")
    else:
        print("所有关键依赖都已包含")
    
    print("\n安装命令:")
    print("  基本安装: pip install .")
    print("  开发安装: pip install -e .[dev]")
    print("  完整安装: pip install -e .[all]")
    print("\n使用命令:")
    print("  rs-dataset-generator --help")
    print("  rsdg --help")