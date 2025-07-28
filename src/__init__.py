"""RSDatasetGenerator - 遥感数据集生成器

一个基于矢量文件的遥感图像数据下载工具，能够根据提供的Shapefile矢量文件，
自动从Google地图服务下载对应区域的高分辨率卫星影像数据。
"""

__version__ = "2.0.0"
__author__ = "RSDatasetGenerator Team"
__email__ = "contact@rsdatasetgenerator.com"

from .config import Config
from .core import RSDatasetGenerator
from .downloaders import DownloaderFactory
from .processors import DataProcessor
from .utils import Logger

__all__ = [
    "Config",
    "RSDatasetGenerator", 
    "DownloaderFactory",
    "DataProcessor",
    "Logger"
]