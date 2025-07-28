"""图像处理模块

提供瓦片合并、图像处理和坐标转换功能。
"""

import math
import os
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from .data_loader import GeoPoint
from ..downloaders.base import TileInfo, DownloadResult
from ..utils import DataProcessingError


@dataclass
class PixelCoordinate:
    """像素坐标"""
    x: float
    y: float
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {'x': self.x, 'y': self.y}


@dataclass
class ImageMetadata:
    """图像元数据"""
    width: int
    height: int
    zoom_level: int
    tile_size: int
    grid_size: int
    center_point: GeoPoint
    bounds: Dict[str, float]
    pixel_coordinates: List[Dict[str, any]]
    
    def to_dict(self) -> Dict[str, any]:
        """转换为字典"""
        return {
            'width': self.width,
            'height': self.height,
            'zoom_level': self.zoom_level,
            'tile_size': self.tile_size,
            'grid_size': self.grid_size,
            'center_point': self.center_point.to_dict(),
            'bounds': self.bounds,
            'pixel_coordinates': self.pixel_coordinates
        }


class TileMerger:
    """瓦片合并器
    
    负责将下载的瓦片合并成完整图像。
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = config.logger
        self.tile_size = 256  # Google Maps瓦片标准尺寸
    
    def merge_tiles(self, 
                   download_results: List[DownloadResult], 
                   grid_size: int,
                   center_tile: TileInfo) -> Image.Image:
        """合并瓦片为完整图像
        
        Args:
            download_results: 下载结果列表
            grid_size: 网格大小
            center_tile: 中心瓦片信息
            
        Returns:
            合并后的图像
        """
        # 计算输出图像尺寸
        output_width = grid_size * self.tile_size
        output_height = grid_size * self.tile_size
        
        # 创建输出图像
        merged_image = Image.new('RGB', (output_width, output_height), (0, 0, 0))
        
        # 创建瓦片位置映射
        tile_map = {}
        for result in download_results:
            if result.success and result.image:
                tile_info = result.tile_info
                tile_map[(tile_info.x, tile_info.y)] = result.image
        
        # 计算网格起始位置
        half_grid = grid_size // 2
        start_x = center_tile.x - half_grid
        start_y = center_tile.y - half_grid
        
        # 合并瓦片
        successful_tiles = 0
        missing_tiles = []
        
        for grid_y in range(grid_size):
            for grid_x in range(grid_size):
                tile_x = start_x + grid_x
                tile_y = start_y + grid_y
                
                # 计算在输出图像中的位置
                pixel_x = grid_x * self.tile_size
                pixel_y = grid_y * self.tile_size
                
                # 获取瓦片图像
                tile_image = tile_map.get((tile_x, tile_y))
                
                if tile_image:
                    # 确保瓦片尺寸正确
                    if tile_image.size != (self.tile_size, self.tile_size):
                        tile_image = tile_image.resize(
                            (self.tile_size, self.tile_size), 
                            Image.Resampling.LANCZOS
                        )
                    
                    # 粘贴瓦片
                    merged_image.paste(tile_image, (pixel_x, pixel_y))
                    successful_tiles += 1
                else:
                    # 记录缺失的瓦片
                    missing_tiles.append((tile_x, tile_y))
                    
                    # 用灰色填充缺失的瓦片
                    self._fill_missing_tile(merged_image, pixel_x, pixel_y)
        
        # 记录合并统计
        total_tiles = grid_size * grid_size
        self.logger.info(
            f"瓦片合并完成: {successful_tiles}/{total_tiles} 成功, "
            f"{len(missing_tiles)} 缺失"
        )
        
        if missing_tiles:
            self.logger.warning(f"缺失瓦片坐标: {missing_tiles[:10]}{'...' if len(missing_tiles) > 10 else ''}")
        
        return merged_image
    
    def _fill_missing_tile(self, image: Image.Image, x: int, y: int):
        """填充缺失的瓦片
        
        Args:
            image: 目标图像
            x: X坐标
            y: Y坐标
        """
        # 创建灰色瓦片
        gray_tile = Image.new('RGB', (self.tile_size, self.tile_size), (128, 128, 128))
        
        # 添加"缺失"文字标记
        try:
            draw = ImageDraw.Draw(gray_tile)
            # 尝试使用默认字体
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            text = "MISSING"
            if font:
                # 计算文字位置（居中）
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = (self.tile_size - text_width) // 2
                text_y = (self.tile_size - text_height) // 2
                
                draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
            else:
                # 如果没有字体，画一个X
                draw.line([(0, 0), (self.tile_size, self.tile_size)], fill=(255, 255, 255), width=2)
                draw.line([(0, self.tile_size), (self.tile_size, 0)], fill=(255, 255, 255), width=2)
        
        except Exception as e:
            self.logger.debug(f"添加缺失瓦片标记失败: {str(e)}")
        
        # 粘贴到目标图像
        image.paste(gray_tile, (x, y))


class ImageProcessor:
    """图像处理器
    
    提供图像处理和坐标转换功能。
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = config.logger
        self.tile_merger = TileMerger(config)
    
    def process_point_image(self, 
                          point: GeoPoint, 
                          download_results: List[DownloadResult],
                          zoom_level: int,
                          grid_size: int) -> Tuple[Image.Image, ImageMetadata]:
        """处理单个点的图像
        
        Args:
            point: 地理点
            download_results: 下载结果列表
            zoom_level: 缩放级别
            grid_size: 网格大小
            
        Returns:
            处理后的图像和元数据
        """
        # 计算中心瓦片坐标
        center_tile_x, center_tile_y = self._geo_to_tile(point.longitude, point.latitude, zoom_level)
        center_tile = TileInfo(center_tile_x, center_tile_y, zoom_level, "", "")
        
        # 合并瓦片
        merged_image = self.tile_merger.merge_tiles(download_results, grid_size, center_tile)
        
        # 计算点在图像中的像素坐标
        pixel_coord = self._geo_to_pixel(point, center_tile, grid_size)
        
        # 创建元数据
        metadata = self._create_image_metadata(
            merged_image, point, center_tile, grid_size, zoom_level, pixel_coord
        )
        
        return merged_image, metadata
    
    def _geo_to_tile(self, lon: float, lat: float, zoom: int) -> Tuple[int, int]:
        """地理坐标转瓦片坐标
        
        Args:
            lon: 经度
            lat: 纬度
            zoom: 缩放级别
            
        Returns:
            瓦片坐标 (x, y)
        """
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return x, y
    
    def _tile_to_geo(self, x: int, y: int, zoom: int) -> Tuple[float, float]:
        """瓦片坐标转地理坐标
        
        Args:
            x: 瓦片X坐标
            y: 瓦片Y坐标
            zoom: 缩放级别
            
        Returns:
            地理坐标 (lon, lat)
        """
        n = 2.0 ** zoom
        lon = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat = math.degrees(lat_rad)
        return lon, lat
    
    def _geo_to_pixel(self, point: GeoPoint, center_tile: TileInfo, grid_size: int) -> PixelCoordinate:
        """地理坐标转像素坐标
        
        Args:
            point: 地理点
            center_tile: 中心瓦片
            grid_size: 网格大小
            
        Returns:
            像素坐标
        """
        # 计算点的瓦片坐标（浮点数）
        point_tile_x, point_tile_y = self._geo_to_tile_float(
            point.longitude, point.latitude, center_tile.z
        )
        
        # 计算网格起始瓦片坐标
        half_grid = grid_size // 2
        start_tile_x = center_tile.x - half_grid
        start_tile_y = center_tile.y - half_grid
        
        # 计算在网格中的相对位置
        relative_tile_x = point_tile_x - start_tile_x
        relative_tile_y = point_tile_y - start_tile_y
        
        # 转换为像素坐标
        pixel_x = relative_tile_x * 256
        pixel_y = relative_tile_y * 256
        
        return PixelCoordinate(pixel_x, pixel_y)
    
    def _geo_to_tile_float(self, lon: float, lat: float, zoom: int) -> Tuple[float, float]:
        """地理坐标转浮点瓦片坐标
        
        Args:
            lon: 经度
            lat: 纬度
            zoom: 缩放级别
            
        Returns:
            浮点瓦片坐标 (x, y)
        """
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        x = (lon + 180.0) / 360.0 * n
        y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
        return x, y
    
    def _create_image_metadata(self, 
                             image: Image.Image,
                             center_point: GeoPoint,
                             center_tile: TileInfo,
                             grid_size: int,
                             zoom_level: int,
                             pixel_coord: PixelCoordinate) -> ImageMetadata:
        """创建图像元数据
        
        Args:
            image: 图像
            center_point: 中心点
            center_tile: 中心瓦片
            grid_size: 网格大小
            zoom_level: 缩放级别
            pixel_coord: 像素坐标
            
        Returns:
            图像元数据
        """
        # 计算图像边界
        half_grid = grid_size // 2
        
        # 左上角瓦片坐标
        top_left_tile_x = center_tile.x - half_grid
        top_left_tile_y = center_tile.y - half_grid
        
        # 右下角瓦片坐标
        bottom_right_tile_x = center_tile.x + half_grid
        bottom_right_tile_y = center_tile.y + half_grid
        
        # 转换为地理坐标
        min_lon, max_lat = self._tile_to_geo(top_left_tile_x, top_left_tile_y, zoom_level)
        max_lon, min_lat = self._tile_to_geo(bottom_right_tile_x, bottom_right_tile_y, zoom_level)
        
        bounds = {
            'min_lon': min_lon,
            'min_lat': min_lat,
            'max_lon': max_lon,
            'max_lat': max_lat
        }
        
        # 创建像素坐标信息
        pixel_coordinates = [{
            'point_index': center_point.index,
            'longitude': center_point.longitude,
            'latitude': center_point.latitude,
            'pixel_x': pixel_coord.x,
            'pixel_y': pixel_coord.y,
            'properties': center_point.properties
        }]
        
        return ImageMetadata(
            width=image.width,
            height=image.height,
            zoom_level=zoom_level,
            tile_size=256,
            grid_size=grid_size,
            center_point=center_point,
            bounds=bounds,
            pixel_coordinates=pixel_coordinates
        )
    
    def add_point_markers(self, image: Image.Image, metadata: ImageMetadata, 
                         marker_size: int = 5, marker_color: Tuple[int, int, int] = (255, 0, 0)) -> Image.Image:
        """在图像上添加点标记
        
        Args:
            image: 原始图像
            metadata: 图像元数据
            marker_size: 标记大小
            marker_color: 标记颜色
            
        Returns:
            添加标记后的图像
        """
        # 创建图像副本
        marked_image = image.copy()
        draw = ImageDraw.Draw(marked_image)
        
        # 添加点标记
        for coord_info in metadata.pixel_coordinates:
            x = coord_info['pixel_x']
            y = coord_info['pixel_y']
            
            # 绘制圆形标记
            left = x - marker_size
            top = y - marker_size
            right = x + marker_size
            bottom = y + marker_size
            
            draw.ellipse([left, top, right, bottom], fill=marker_color, outline=(255, 255, 255), width=1)
        
        return marked_image
    
    def resize_image(self, image: Image.Image, target_size: Tuple[int, int], 
                    resample: Image.Resampling = Image.Resampling.LANCZOS) -> Image.Image:
        """调整图像尺寸
        
        Args:
            image: 原始图像
            target_size: 目标尺寸 (width, height)
            resample: 重采样方法
            
        Returns:
            调整尺寸后的图像
        """
        return image.resize(target_size, resample)
    
    def crop_image(self, image: Image.Image, crop_box: Tuple[int, int, int, int]) -> Image.Image:
        """裁剪图像
        
        Args:
            image: 原始图像
            crop_box: 裁剪框 (left, top, right, bottom)
            
        Returns:
            裁剪后的图像
        """
        return image.crop(crop_box)
    
    def enhance_image(self, image: Image.Image, brightness: float = 1.0, 
                     contrast: float = 1.0, saturation: float = 1.0) -> Image.Image:
        """增强图像
        
        Args:
            image: 原始图像
            brightness: 亮度调整因子
            contrast: 对比度调整因子
            saturation: 饱和度调整因子
            
        Returns:
            增强后的图像
        """
        from PIL import ImageEnhance
        
        enhanced_image = image.copy()
        
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(enhanced_image)
            enhanced_image = enhancer.enhance(brightness)
        
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(enhanced_image)
            enhanced_image = enhancer.enhance(contrast)
        
        if saturation != 1.0:
            enhancer = ImageEnhance.Color(enhanced_image)
            enhanced_image = enhancer.enhance(saturation)
        
        return enhanced_image