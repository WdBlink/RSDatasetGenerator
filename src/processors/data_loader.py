"""数据加载器模块

提供各种格式的地理数据加载功能。
支持Shapefile、GeoJSON等格式。
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from pyproj import Transformer

from ..utils import ValidationError, DataProcessingError, validate_shapefile


@dataclass
class GeoPoint:
    """地理点数据类"""
    longitude: float
    latitude: float
    properties: Dict[str, Any] = None
    index: int = None
    
    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'longitude': self.longitude,
            'latitude': self.latitude,
            'properties': self.properties,
            'index': self.index
        }
    
    def validate(self) -> bool:
        """验证坐标有效性"""
        return (
            -180 <= self.longitude <= 180 and
            -90 <= self.latitude <= 90
        )


@dataclass
class GeoBounds:
    """地理边界数据类"""
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    
    def contains_point(self, point: GeoPoint) -> bool:
        """检查点是否在边界内"""
        return (
            self.min_lon <= point.longitude <= self.max_lon and
            self.min_lat <= point.latitude <= self.max_lat
        )
    
    def expand(self, margin: float = 0.001) -> 'GeoBounds':
        """扩展边界"""
        return GeoBounds(
            min_lon=self.min_lon - margin,
            min_lat=self.min_lat - margin,
            max_lon=self.max_lon + margin,
            max_lat=self.max_lat + margin
        )
    
    def area(self) -> float:
        """计算边界面积（度数）"""
        return (self.max_lon - self.min_lon) * (self.max_lat - self.min_lat)


class BaseDataLoader(ABC):
    """数据加载器基类"""
    
    def __init__(self, config):
        self.config = config
        self.logger = config.logger
        self.transformer = None
    
    @abstractmethod
    def load_points(self, file_path: str) -> List[GeoPoint]:
        """加载地理点数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            地理点列表
        """
        pass
    
    @abstractmethod
    def get_bounds(self, file_path: str) -> GeoBounds:
        """获取数据边界
        
        Args:
            file_path: 文件路径
            
        Returns:
            地理边界
        """
        pass
    
    @abstractmethod
    def validate_file(self, file_path: str) -> bool:
        """验证文件格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件是否有效
        """
        pass
    
    def _setup_transformer(self, source_crs: str, target_crs: str = "EPSG:4326"):
        """设置坐标转换器
        
        Args:
            source_crs: 源坐标系
            target_crs: 目标坐标系
        """
        if source_crs != target_crs:
            try:
                self.transformer = Transformer.from_crs(
                    source_crs, target_crs, always_xy=True
                )
                self.logger.info(f"设置坐标转换: {source_crs} -> {target_crs}")
            except Exception as e:
                raise DataProcessingError(f"创建坐标转换器失败: {str(e)}")
    
    def _transform_coordinates(self, x: float, y: float) -> Tuple[float, float]:
        """转换坐标
        
        Args:
            x: X坐标（经度）
            y: Y坐标（纬度）
            
        Returns:
            转换后的坐标
        """
        if self.transformer:
            return self.transformer.transform(x, y)
        return x, y


class ShapefileLoader(BaseDataLoader):
    """Shapefile加载器"""
    
    def validate_file(self, file_path: str) -> bool:
        """验证Shapefile文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件是否有效
        """
        try:
            return validate_shapefile(file_path)
        except Exception as e:
            self.logger.error(f"验证Shapefile失败: {str(e)}")
            return False
    
    def load_points(self, file_path: str) -> List[GeoPoint]:
        """加载Shapefile中的点数据
        
        Args:
            file_path: Shapefile路径
            
        Returns:
            地理点列表
        """
        if not self.validate_file(file_path):
            raise ValidationError(f"无效的Shapefile文件: {file_path}")
        
        try:
            # 读取Shapefile
            gdf = gpd.read_file(file_path)
            
            if gdf.empty:
                raise DataProcessingError("Shapefile为空")
            
            self.logger.info(f"加载Shapefile: {file_path}, 记录数: {len(gdf)}")
            
            # 设置坐标转换
            source_crs = str(gdf.crs) if gdf.crs else "EPSG:4326"
            self._setup_transformer(source_crs)
            
            points = []
            
            for idx, row in gdf.iterrows():
                geometry = row.geometry
                
                # 处理不同的几何类型
                if isinstance(geometry, Point):
                    x, y = geometry.x, geometry.y
                elif hasattr(geometry, 'centroid'):
                    # 对于多边形等，使用质心
                    centroid = geometry.centroid
                    x, y = centroid.x, centroid.y
                    self.logger.debug(f"使用几何体质心: {geometry.geom_type}")
                else:
                    self.logger.warning(f"跳过不支持的几何类型: {type(geometry)}")
                    continue
                
                # 坐标转换
                lon, lat = self._transform_coordinates(x, y)
                
                # 创建属性字典（排除几何列）
                properties = {}
                for col in gdf.columns:
                    if col != gdf.geometry.name:
                        value = row[col]
                        # 处理pandas特殊值
                        if pd.isna(value):
                            properties[col] = None
                        else:
                            properties[col] = value
                
                # 创建地理点
                point = GeoPoint(
                    longitude=lon,
                    latitude=lat,
                    properties=properties,
                    index=idx
                )
                
                # 验证坐标
                if not point.validate():
                    self.logger.warning(
                        f"跳过无效坐标: ({lon}, {lat}) at index {idx}"
                    )
                    continue
                
                points.append(point)
            
            if not points:
                raise DataProcessingError("没有有效的地理点数据")
            
            self.logger.info(f"成功加载 {len(points)} 个有效地理点")
            return points
            
        except Exception as e:
            if isinstance(e, (ValidationError, DataProcessingError)):
                raise
            raise DataProcessingError(f"加载Shapefile失败: {str(e)}")
    
    def get_bounds(self, file_path: str) -> GeoBounds:
        """获取Shapefile数据边界
        
        Args:
            file_path: Shapefile路径
            
        Returns:
            地理边界
        """
        try:
            gdf = gpd.read_file(file_path)
            
            if gdf.empty:
                raise DataProcessingError("Shapefile为空")
            
            # 转换到WGS84
            if gdf.crs and str(gdf.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            
            # 获取边界
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            
            return GeoBounds(
                min_lon=bounds[0],
                min_lat=bounds[1],
                max_lon=bounds[2],
                max_lat=bounds[3]
            )
            
        except Exception as e:
            raise DataProcessingError(f"获取Shapefile边界失败: {str(e)}")


class GeoJSONLoader(BaseDataLoader):
    """GeoJSON加载器"""
    
    def validate_file(self, file_path: str) -> bool:
        """验证GeoJSON文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件是否有效
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            if not file_path.lower().endswith(('.geojson', '.json')):
                return False
            
            # 尝试读取文件
            gdf = gpd.read_file(file_path)
            return not gdf.empty
            
        except Exception:
            return False
    
    def load_points(self, file_path: str) -> List[GeoPoint]:
        """加载GeoJSON中的点数据
        
        Args:
            file_path: GeoJSON路径
            
        Returns:
            地理点列表
        """
        if not self.validate_file(file_path):
            raise ValidationError(f"无效的GeoJSON文件: {file_path}")
        
        try:
            # 读取GeoJSON
            gdf = gpd.read_file(file_path)
            
            if gdf.empty:
                raise DataProcessingError("GeoJSON为空")
            
            self.logger.info(f"加载GeoJSON: {file_path}, 记录数: {len(gdf)}")
            
            # 设置坐标转换
            source_crs = str(gdf.crs) if gdf.crs else "EPSG:4326"
            self._setup_transformer(source_crs)
            
            points = []
            
            for idx, row in gdf.iterrows():
                geometry = row.geometry
                
                # 处理不同的几何类型
                if isinstance(geometry, Point):
                    x, y = geometry.x, geometry.y
                elif hasattr(geometry, 'centroid'):
                    # 对于多边形等，使用质心
                    centroid = geometry.centroid
                    x, y = centroid.x, centroid.y
                    self.logger.debug(f"使用几何体质心: {geometry.geom_type}")
                else:
                    self.logger.warning(f"跳过不支持的几何类型: {type(geometry)}")
                    continue
                
                # 坐标转换
                lon, lat = self._transform_coordinates(x, y)
                
                # 创建属性字典（排除几何列）
                properties = {}
                for col in gdf.columns:
                    if col != gdf.geometry.name:
                        value = row[col]
                        # 处理pandas特殊值
                        if pd.isna(value):
                            properties[col] = None
                        else:
                            properties[col] = value
                
                # 创建地理点
                point = GeoPoint(
                    longitude=lon,
                    latitude=lat,
                    properties=properties,
                    index=idx
                )
                
                # 验证坐标
                if not point.validate():
                    self.logger.warning(
                        f"跳过无效坐标: ({lon}, {lat}) at index {idx}"
                    )
                    continue
                
                points.append(point)
            
            if not points:
                raise DataProcessingError("没有有效的地理点数据")
            
            self.logger.info(f"成功加载 {len(points)} 个有效地理点")
            return points
            
        except Exception as e:
            if isinstance(e, (ValidationError, DataProcessingError)):
                raise
            raise DataProcessingError(f"加载GeoJSON失败: {str(e)}")
    
    def get_bounds(self, file_path: str) -> GeoBounds:
        """获取GeoJSON数据边界
        
        Args:
            file_path: GeoJSON路径
            
        Returns:
            地理边界
        """
        try:
            gdf = gpd.read_file(file_path)
            
            if gdf.empty:
                raise DataProcessingError("GeoJSON为空")
            
            # 转换到WGS84
            if gdf.crs and str(gdf.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            
            # 获取边界
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            
            return GeoBounds(
                min_lon=bounds[0],
                min_lat=bounds[1],
                max_lon=bounds[2],
                max_lat=bounds[3]
            )
            
        except Exception as e:
            raise DataProcessingError(f"获取GeoJSON边界失败: {str(e)}")


class DataLoader:
    """数据加载器工厂
    
    根据文件类型自动选择合适的加载器。
    """
    
    _loaders = {
        '.shp': ShapefileLoader,
        '.geojson': GeoJSONLoader,
        '.json': GeoJSONLoader,
    }
    
    @classmethod
    def create_loader(cls, file_path: str, config) -> BaseDataLoader:
        """创建数据加载器
        
        Args:
            file_path: 文件路径
            config: 配置对象
            
        Returns:
            数据加载器实例
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        loader_class = cls._loaders.get(file_ext)
        if loader_class is None:
            raise ValidationError(f"不支持的文件格式: {file_ext}")
        
        return loader_class(config)
    
    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """获取支持的文件格式
        
        Returns:
            支持的文件格式列表
        """
        return list(cls._loaders.keys())
    
    @classmethod
    def load_points(cls, file_path: str, config) -> List[GeoPoint]:
        """加载地理点数据
        
        Args:
            file_path: 文件路径
            config: 配置对象
            
        Returns:
            地理点列表
        """
        loader = cls.create_loader(file_path, config)
        return loader.load_points(file_path)
    
    @classmethod
    def get_bounds(cls, file_path: str, config) -> GeoBounds:
        """获取数据边界
        
        Args:
            file_path: 文件路径
            config: 配置对象
            
        Returns:
            地理边界
        """
        loader = cls.create_loader(file_path, config)
        return loader.get_bounds(file_path)