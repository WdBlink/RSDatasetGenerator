"""下载器基类模块

定义下载器的抽象接口和通用功能。
"""

import os
import time
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from PIL import Image
import mercantile

from ..config import Config
from ..utils import Logger, PerformanceMonitor, DownloadError


@dataclass
class TileInfo:
    """瓦片信息"""
    x: int
    y: int
    z: int
    url: str
    file_path: str
    
    @property
    def key(self) -> Tuple[int, int, int]:
        """瓦片唯一标识"""
        return (self.x, self.y, self.z)


@dataclass
class DownloadResult:
    """下载结果"""
    tile_info: TileInfo
    success: bool
    image: Optional[Image.Image] = None
    error: Optional[str] = None
    download_time: float = 0.0
    file_size: int = 0
    from_cache: bool = False


class TileCache:
    """瓦片缓存管理器"""
    
    def __init__(self, max_size: int = 1000):
        """初始化缓存
        
        Args:
            max_size: 最大缓存数量
        """
        self.max_size = max_size
        self._cache: Dict[Tuple[int, int, int], Image.Image] = {}
        self._access_order: List[Tuple[int, int, int]] = []
    
    def get(self, key: Tuple[int, int, int]) -> Optional[Image.Image]:
        """获取缓存的瓦片
        
        Args:
            key: 瓦片标识 (x, y, z)
            
        Returns:
            缓存的图像，如果不存在返回None
        """
        if key in self._cache:
            # 更新访问顺序
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None
    
    def put(self, key: Tuple[int, int, int], image: Image.Image) -> None:
        """添加瓦片到缓存
        
        Args:
            key: 瓦片标识 (x, y, z)
            image: 瓦片图像
        """
        if key in self._cache:
            # 更新现有缓存
            self._access_order.remove(key)
        elif len(self._cache) >= self.max_size:
            # 移除最久未使用的缓存
            oldest_key = self._access_order.pop(0)
            del self._cache[oldest_key]
        
        self._cache[key] = image
        self._access_order.append(key)
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)


class BaseDownloader(ABC):
    """下载器基类
    
    定义下载器的抽象接口，所有具体下载器都应继承此类。
    """
    
    def __init__(self, config: Config):
        """初始化下载器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = Logger(f"{self.__class__.__name__}")
        self.monitor = PerformanceMonitor()
        self.cache = TileCache(max_size=1000)
        
        # 确保输出目录存在
        os.makedirs(self.config.paths.tile_save_dir, exist_ok=True)
    
    def generate_tile_url(self, x: int, y: int, z: int) -> str:
        """生成瓦片URL
        
        Args:
            x: 瓦片X坐标
            y: 瓦片Y坐标
            z: 缩放级别
            
        Returns:
            瓦片URL
        """
        return f"{self.config.network.base_url}&x={x}&y={y}&z={z}"
    
    def generate_tile_path(self, x: int, y: int, z: int) -> str:
        """生成瓦片文件路径
        
        Args:
            x: 瓦片X坐标
            y: 瓦片Y坐标
            z: 缩放级别
            
        Returns:
            瓦片文件路径
        """
        filename = f"tile_{z}_{x}_{y}.png"
        return os.path.join(self.config.paths.tile_save_dir, filename)
    
    def create_tile_info(self, x: int, y: int, z: int) -> TileInfo:
        """创建瓦片信息对象
        
        Args:
            x: 瓦片X坐标
            y: 瓦片Y坐标
            z: 缩放级别
            
        Returns:
            瓦片信息对象
        """
        return TileInfo(
            x=x,
            y=y,
            z=z,
            url=self.generate_tile_url(x, y, z),
            file_path=self.generate_tile_path(x, y, z)
        )
    
    def calculate_tiles_for_point(self, lon: float, lat: float, zoom: int, grid_size: int) -> List[TileInfo]:
        """计算点周围的瓦片
        
        Args:
            lon: 经度
            lat: 纬度
            zoom: 缩放级别
            grid_size: 网格大小
            
        Returns:
            瓦片信息列表
        """
        center_tile = mercantile.tile(lon, lat, zoom)
        half = grid_size // 2
        tiles = []
        
        for dx in range(-half, half + 1):
            for dy in range(-half, half + 1):
                x = center_tile.x + dx
                y = center_tile.y + dy
                
                # 检查瓦片坐标是否有效
                max_coord = 1 << zoom
                if 0 <= x < max_coord and 0 <= y < max_coord:
                    tiles.append(self.create_tile_info(x, y, zoom))
        
        return tiles
    
    def load_cached_tile(self, tile_info: TileInfo) -> Optional[Image.Image]:
        """从缓存或文件加载瓦片
        
        Args:
            tile_info: 瓦片信息
            
        Returns:
            瓦片图像，如果不存在返回None
        """
        # 首先检查内存缓存
        cached_image = self.cache.get(tile_info.key)
        if cached_image is not None:
            self.monitor.update_stats('cache_hits')
            return cached_image
        
        # 检查文件缓存
        if os.path.exists(tile_info.file_path):
            try:
                image = Image.open(tile_info.file_path).convert('RGB')
                self.cache.put(tile_info.key, image)
                self.monitor.update_stats('cache_hits')
                return image
            except Exception as e:
                self.logger.warning(f"加载缓存文件失败: {tile_info.file_path}, 错误: {str(e)}")
        
        self.monitor.update_stats('cache_misses')
        return None
    
    def save_tile(self, tile_info: TileInfo, image: Image.Image) -> None:
        """保存瓦片到文件和缓存
        
        Args:
            tile_info: 瓦片信息
            image: 瓦片图像
        """
        try:
            # 保存到文件
            os.makedirs(os.path.dirname(tile_info.file_path), exist_ok=True)
            image.save(tile_info.file_path, 'PNG')
            
            # 添加到缓存
            self.cache.put(tile_info.key, image)
            
            # 更新统计
            file_size = os.path.getsize(tile_info.file_path)
            self.monitor.update_stats('total_bytes', file_size)
            
        except Exception as e:
            raise DownloadError(f"保存瓦片失败: {tile_info.file_path}, 错误: {str(e)}")
    
    def add_random_delay(self) -> None:
        """添加随机延迟以避免被封禁"""
        min_interval, max_interval = self.config.download.request_interval_range
        delay = random.uniform(min_interval, max_interval)
        time.sleep(delay)
    
    def validate_tile_coordinates(self, x: int, y: int, z: int) -> bool:
        """验证瓦片坐标是否有效
        
        Args:
            x: 瓦片X坐标
            y: 瓦片Y坐标
            z: 缩放级别
            
        Returns:
            坐标是否有效
        """
        if z < 0 or z > 20:
            return False
        
        max_coord = 1 << z
        return 0 <= x < max_coord and 0 <= y < max_coord
    
    @abstractmethod
    def download_tile(self, tile_info: TileInfo) -> DownloadResult:
        """下载单个瓦片（抽象方法）
        
        Args:
            tile_info: 瓦片信息
            
        Returns:
            下载结果
        """
        pass
    
    @abstractmethod
    def download_tiles(self, tiles: List[TileInfo]) -> List[DownloadResult]:
        """批量下载瓦片（抽象方法）
        
        Args:
            tiles: 瓦片信息列表
            
        Returns:
            下载结果列表
        """
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取下载统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.monitor.get_current_stats()
        stats.update({
            'cache_size': self.cache.size(),
            'downloader_type': self.__class__.__name__
        })
        return stats
    
    def reset_statistics(self) -> None:
        """重置统计信息"""
        self.monitor.reset()
        self.cache.clear()