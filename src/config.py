"""配置管理模块

提供统一的配置管理功能，支持从文件、环境变量和命令行参数加载配置。
使用单例模式确保配置的一致性。
"""

import os
import json
import argparse
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DownloadConfig:
    """下载相关配置"""
    zoom: int = 18
    grid_size: int = 9
    max_concurrency: int = 8
    request_timeout: float = 30.0
    request_interval_range: Tuple[float, float] = (0.1, 0.3)
    retry_wait_range: Tuple[float, float] = (6, 10)
    max_retries: int = 3
    backoff_base: float = 2.0
    
    def __post_init__(self):
        """验证配置参数"""
        if self.grid_size % 2 == 0:
            raise ValueError("grid_size必须是奇数")
        if self.zoom < 1 or self.zoom > 20:
            raise ValueError("zoom级别必须在1-20之间")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency必须大于0")


@dataclass
class PathConfig:
    """路径相关配置"""
    input_shapefile: str = ""
    tile_save_dir: str = "./tiles"
    output_dir: str = "./output"
    log_dir: str = "./logs"
    
    def __post_init__(self):
        """创建必要的目录"""
        for dir_path in [self.tile_save_dir, self.output_dir, self.log_dir]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)


@dataclass
class NetworkConfig:
    """网络相关配置"""
    headers: Dict[str, str] = field(default_factory=lambda: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                     'AppleWebKit/537.36 (KHTML, like Gecko) '
                     'Chrome/91.0.4472.124 Safari/537.36'
    })
    base_url: str = "http://mt0.google.com/vt/lyrs=s&hl=en"
    use_proxy: bool = False
    proxy_url: Optional[str] = None


class Config:
    """配置管理器（单例模式）
    
    统一管理所有配置项，支持从多种来源加载配置：
    1. 默认配置
    2. 配置文件
    3. 环境变量
    4. 命令行参数
    """
    
    _instance: Optional['Config'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'Config':
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化配置管理器"""
        if not self._initialized:
            self.download = DownloadConfig()
            self.paths = PathConfig()
            self.network = NetworkConfig()
            self._initialized = True
    
    def load_from_file(self, config_file: str) -> None:
        """从配置文件加载配置
        
        Args:
            config_file: 配置文件路径（支持JSON格式）
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式错误
        """
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 更新下载配置
        if 'download' in config_data:
            download_data = config_data['download']
            for key, value in download_data.items():
                if hasattr(self.download, key):
                    setattr(self.download, key, value)
        
        # 更新路径配置
        if 'paths' in config_data:
            paths_data = config_data['paths']
            for key, value in paths_data.items():
                if hasattr(self.paths, key):
                    setattr(self.paths, key, value)
        
        # 更新网络配置
        if 'network' in config_data:
            network_data = config_data['network']
            for key, value in network_data.items():
                if hasattr(self.network, key):
                    setattr(self.network, key, value)
    
    def load_from_env(self) -> None:
        """从环境变量加载配置"""
        # 下载配置
        if zoom := os.getenv('RS_ZOOM'):
            self.download.zoom = int(zoom)
        if grid_size := os.getenv('RS_GRID_SIZE'):
            self.download.grid_size = int(grid_size)
        if max_concurrency := os.getenv('RS_MAX_CONCURRENCY'):
            self.download.max_concurrency = int(max_concurrency)
        
        # 路径配置
        if input_shapefile := os.getenv('RS_INPUT_SHAPEFILE'):
            self.paths.input_shapefile = input_shapefile
        if tile_save_dir := os.getenv('RS_TILE_SAVE_DIR'):
            self.paths.tile_save_dir = tile_save_dir
        if output_dir := os.getenv('RS_OUTPUT_DIR'):
            self.paths.output_dir = output_dir
    
    def load_from_args(self, args: argparse.Namespace) -> None:
        """从命令行参数加载配置
        
        Args:
            args: 解析后的命令行参数
        """
        # 下载配置
        if hasattr(args, 'zoom') and args.zoom is not None:
            self.download.zoom = args.zoom
        if hasattr(args, 'grid_size') and args.grid_size is not None:
            self.download.grid_size = args.grid_size
        if hasattr(args, 'max_concurrency') and args.max_concurrency is not None:
            self.download.max_concurrency = args.max_concurrency
        if hasattr(args, 'timeout') and args.timeout is not None:
            self.download.request_timeout = args.timeout
        
        # 路径配置
        if hasattr(args, 'input') and args.input is not None:
            self.paths.input_shapefile = args.input
        if hasattr(args, 'tile_dir') and args.tile_dir is not None:
            self.paths.tile_save_dir = args.tile_dir
        if hasattr(args, 'output_dir') and args.output_dir is not None:
            self.paths.output_dir = args.output_dir
    
    def validate(self) -> None:
        """验证配置的有效性
        
        Raises:
            ValueError: 配置参数无效
        """
        if not self.paths.input_shapefile:
            raise ValueError("必须指定输入Shapefile路径")
        
        if not os.path.exists(self.paths.input_shapefile):
            raise FileNotFoundError(f"输入Shapefile不存在: {self.paths.input_shapefile}")
        
        # 验证Shapefile完整性
        base_path = os.path.splitext(self.paths.input_shapefile)[0]
        required_extensions = ['.shp', '.shx', '.dbf']
        for ext in required_extensions:
            if not os.path.exists(f"{base_path}{ext}"):
                raise FileNotFoundError(f"缺少Shapefile必要文件: {base_path}{ext}")
    
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式
        
        Returns:
            配置字典
        """
        return {
            'download': {
                'zoom': self.download.zoom,
                'grid_size': self.download.grid_size,
                'max_concurrency': self.download.max_concurrency,
                'request_timeout': self.download.request_timeout,
                'request_interval_range': self.download.request_interval_range,
                'retry_wait_range': self.download.retry_wait_range,
                'max_retries': self.download.max_retries,
                'backoff_base': self.download.backoff_base
            },
            'paths': {
                'input_shapefile': self.paths.input_shapefile,
                'tile_save_dir': self.paths.tile_save_dir,
                'output_dir': self.paths.output_dir,
                'log_dir': self.paths.log_dir
            },
            'network': {
                'headers': self.network.headers,
                'base_url': self.network.base_url,
                'use_proxy': self.network.use_proxy,
                'proxy_url': self.network.proxy_url
            }
        }
    
    def save_to_file(self, config_file: str) -> None:
        """保存配置到文件
        
        Args:
            config_file: 配置文件路径
        """
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def reset(cls) -> None:
        """重置单例实例（主要用于测试）"""
        cls._instance = None
        cls._initialized = False


def create_argument_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器
    
    Returns:
        配置好的参数解析器
    """
    parser = argparse.ArgumentParser(
        description='RSDatasetGenerator - 遥感数据集生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 必需参数
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='输入Shapefile路径'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        default='./output',
        help='输出目录路径（默认: ./output）'
    )
    
    # 下载参数
    download_group = parser.add_argument_group('下载参数')
    download_group.add_argument(
        '--zoom', '-z',
        type=int,
        default=18,
        choices=range(1, 21),
        help='瓦片缩放级别（1-20，默认: 18）'
    )
    
    download_group.add_argument(
        '--grid-size', '-g',
        type=int,
        default=9,
        choices=[3, 5, 7, 9, 11],
        help='瓦片网格尺寸（必须是奇数，默认: 9）'
    )
    
    download_group.add_argument(
        '--max-concurrency', '-c',
        type=int,
        default=8,
        help='最大并发数（默认: 8）'
    )
    
    download_group.add_argument(
        '--timeout', '-t',
        type=float,
        default=30.0,
        help='请求超时时间（秒，默认: 30.0）'
    )
    
    # 路径参数
    path_group = parser.add_argument_group('路径参数')
    path_group.add_argument(
        '--tile-dir',
        default='./tiles',
        help='瓦片存储目录（默认: ./tiles）'
    )
    
    path_group.add_argument(
        '--log-dir',
        default='./logs',
        help='日志存储目录（默认: ./logs）'
    )
    
    # 配置文件
    parser.add_argument(
        '--config', '-f',
        help='配置文件路径（JSON格式）'
    )
    
    # 其他选项
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='启用详细输出'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='RSDatasetGenerator 2.0.0'
    )
    
    return parser