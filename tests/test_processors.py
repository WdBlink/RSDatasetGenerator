#!/usr/bin/env python3
"""数据处理器模块测试

测试数据处理器的功能，包括：
- 数据加载
- 图像处理
- 瓦片合并
- 元数据管理
"""

import os
import sys
import unittest
import tempfile
import json
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.processors.data_loader import (
        DataLoader, ShapefileLoader, GeoJSONLoader, 
        GeoPoint, GeoBounds
    )
    from src.processors.image_processor import (
        ImageProcessor, TileMerger, PixelCoordinate, ImageMetadata
    )
    from src.processors.metadata_manager import (
        MetadataManager, DatasetMetadata, ProcessingStats
    )
    from src.processors.data_processor import DataProcessor
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行测试")
    sys.exit(1)


class TestGeoPoint(unittest.TestCase):
    """地理点测试"""
    
    def test_geo_point_creation(self):
        """测试地理点创建"""
        point = GeoPoint(
            longitude=116.3974,
            latitude=39.9093,
            properties={'name': 'Beijing', 'type': 'capital'}
        )
        
        self.assertEqual(point.longitude, 116.3974)
        self.assertEqual(point.latitude, 39.9093)
        self.assertEqual(point.properties['name'], 'Beijing')
        self.assertEqual(point.properties['type'], 'capital')
    
    def test_geo_point_validation(self):
        """测试地理点坐标验证"""
        # 有效坐标
        valid_point = GeoPoint(longitude=116.3974, latitude=39.9093)
        self.assertTrue(valid_point.is_valid())
        
        # 边界坐标
        boundary_points = [
            GeoPoint(longitude=-180.0, latitude=-90.0),
            GeoPoint(longitude=180.0, latitude=90.0),
            GeoPoint(longitude=0.0, latitude=0.0)
        ]
        
        for point in boundary_points:
            self.assertTrue(point.is_valid())
        
        # 无效坐标
        invalid_points = [
            GeoPoint(longitude=200.0, latitude=39.9093),  # 经度超出范围
            GeoPoint(longitude=116.3974, latitude=100.0),  # 纬度超出范围
            GeoPoint(longitude=-200.0, latitude=39.9093),  # 经度超出范围
            GeoPoint(longitude=116.3974, latitude=-100.0)  # 纬度超出范围
        ]
        
        for point in invalid_points:
            self.assertFalse(point.is_valid())
    
    def test_geo_point_distance(self):
        """测试地理点距离计算"""
        # 北京和上海
        beijing = GeoPoint(longitude=116.3974, latitude=39.9093)
        shanghai = GeoPoint(longitude=121.4737, latitude=31.2304)
        
        distance = beijing.distance_to(shanghai)
        
        # 北京到上海的距离大约是1000-1200公里
        self.assertGreater(distance, 1000)
        self.assertLess(distance, 1300)
        
        # 同一点的距离应该是0
        self.assertEqual(beijing.distance_to(beijing), 0.0)
    
    def test_geo_point_to_dict(self):
        """测试地理点转字典"""
        point = GeoPoint(
            longitude=116.3974,
            latitude=39.9093,
            properties={'name': 'Beijing'}
        )
        
        point_dict = point.to_dict()
        
        self.assertIsInstance(point_dict, dict)
        self.assertEqual(point_dict['longitude'], 116.3974)
        self.assertEqual(point_dict['latitude'], 39.9093)
        self.assertEqual(point_dict['properties']['name'], 'Beijing')


class TestGeoBounds(unittest.TestCase):
    """地理边界测试"""
    
    def test_geo_bounds_creation(self):
        """测试地理边界创建"""
        bounds = GeoBounds(
            min_lon=116.0,
            max_lon=117.0,
            min_lat=39.0,
            max_lat=40.0
        )
        
        self.assertEqual(bounds.min_lon, 116.0)
        self.assertEqual(bounds.max_lon, 117.0)
        self.assertEqual(bounds.min_lat, 39.0)
        self.assertEqual(bounds.max_lat, 40.0)
    
    def test_geo_bounds_validation(self):
        """测试地理边界验证"""
        # 有效边界
        valid_bounds = GeoBounds(
            min_lon=116.0, max_lon=117.0,
            min_lat=39.0, max_lat=40.0
        )
        self.assertTrue(valid_bounds.is_valid())
        
        # 无效边界（最小值大于最大值）
        invalid_bounds = GeoBounds(
            min_lon=117.0, max_lon=116.0,  # min > max
            min_lat=39.0, max_lat=40.0
        )
        self.assertFalse(invalid_bounds.is_valid())
    
    def test_geo_bounds_contains_point(self):
        """测试地理边界包含点检查"""
        bounds = GeoBounds(
            min_lon=116.0, max_lon=117.0,
            min_lat=39.0, max_lat=40.0
        )
        
        # 边界内的点
        inside_point = GeoPoint(longitude=116.5, latitude=39.5)
        self.assertTrue(bounds.contains_point(inside_point))
        
        # 边界外的点
        outside_point = GeoPoint(longitude=118.0, latitude=39.5)
        self.assertFalse(bounds.contains_point(outside_point))
        
        # 边界上的点
        boundary_point = GeoPoint(longitude=116.0, latitude=39.0)
        self.assertTrue(bounds.contains_point(boundary_point))
    
    def test_geo_bounds_center(self):
        """测试地理边界中心点计算"""
        bounds = GeoBounds(
            min_lon=116.0, max_lon=118.0,
            min_lat=39.0, max_lat=41.0
        )
        
        center = bounds.center()
        
        self.assertEqual(center.longitude, 117.0)
        self.assertEqual(center.latitude, 40.0)
    
    def test_geo_bounds_area(self):
        """测试地理边界面积计算"""
        bounds = GeoBounds(
            min_lon=116.0, max_lon=117.0,
            min_lat=39.0, max_lat=40.0
        )
        
        area = bounds.area()
        
        # 面积应该是正数
        self.assertGreater(area, 0)
        
        # 1度x1度的区域面积应该在合理范围内
        self.assertLess(area, 20000)  # 平方公里


class TestDataLoader(unittest.TestCase):
    """数据加载器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_geojson_loader(self):
        """测试创建GeoJSON加载器"""
        geojson_file = os.path.join(self.temp_dir, 'test.geojson')
        
        # 创建测试GeoJSON文件
        test_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [116.3974, 39.9093]
                    },
                    "properties": {"name": "Beijing"}
                }
            ]
        }
        
        with open(geojson_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        loader = DataLoader.create_loader(geojson_file)
        
        self.assertIsInstance(loader, GeoJSONLoader)
        self.assertEqual(loader.file_path, geojson_file)
    
    def test_create_shapefile_loader(self):
        """测试创建Shapefile加载器"""
        shapefile = os.path.join(self.temp_dir, 'test.shp')
        
        # 创建空的shapefile（仅用于测试文件类型识别）
        with open(shapefile, 'w') as f:
            f.write('')
        
        loader = DataLoader.create_loader(shapefile)
        
        self.assertIsInstance(loader, ShapefileLoader)
        self.assertEqual(loader.file_path, shapefile)
    
    def test_unsupported_file_type(self):
        """测试不支持的文件类型"""
        txt_file = os.path.join(self.temp_dir, 'test.txt')
        
        with open(txt_file, 'w') as f:
            f.write('test content')
        
        with self.assertRaises(ValueError) as context:
            DataLoader.create_loader(txt_file)
        
        self.assertIn('不支持的文件类型', str(context.exception))
    
    @patch('geopandas.read_file')
    def test_geojson_loader_load_points(self, mock_read_file):
        """测试GeoJSON加载器加载点数据"""
        # 模拟GeoDataFrame
        mock_row1 = Mock()
        mock_row1.geometry.x = 116.3974
        mock_row1.geometry.y = 39.9093
        mock_row1.to_dict.return_value = {'name': 'Beijing'}
        
        mock_row2 = Mock()
        mock_row2.geometry.x = 121.4737
        mock_row2.geometry.y = 31.2304
        mock_row2.to_dict.return_value = {'name': 'Shanghai'}
        
        mock_gdf = Mock()
        mock_gdf.iterrows.return_value = [(0, mock_row1), (1, mock_row2)]
        mock_read_file.return_value = mock_gdf
        
        geojson_file = os.path.join(self.temp_dir, 'test.geojson')
        with open(geojson_file, 'w') as f:
            f.write('{}')
        
        loader = GeoJSONLoader(geojson_file)
        points = loader.load_points()
        
        self.assertEqual(len(points), 2)
        
        # 检查第一个点
        self.assertIsInstance(points[0], GeoPoint)
        self.assertEqual(points[0].longitude, 116.3974)
        self.assertEqual(points[0].latitude, 39.9093)
        self.assertEqual(points[0].properties['name'], 'Beijing')
        
        # 检查第二个点
        self.assertEqual(points[1].longitude, 121.4737)
        self.assertEqual(points[1].latitude, 31.2304)
        self.assertEqual(points[1].properties['name'], 'Shanghai')
    
    @patch('geopandas.read_file')
    def test_loader_get_bounds(self, mock_read_file):
        """测试加载器获取边界"""
        # 模拟GeoDataFrame的bounds属性
        mock_gdf = Mock()
        mock_gdf.total_bounds = [116.0, 39.0, 118.0, 41.0]  # [minx, miny, maxx, maxy]
        mock_read_file.return_value = mock_gdf
        
        geojson_file = os.path.join(self.temp_dir, 'test.geojson')
        with open(geojson_file, 'w') as f:
            f.write('{}')
        
        loader = GeoJSONLoader(geojson_file)
        bounds = loader.get_bounds()
        
        self.assertIsInstance(bounds, GeoBounds)
        self.assertEqual(bounds.min_lon, 116.0)
        self.assertEqual(bounds.min_lat, 39.0)
        self.assertEqual(bounds.max_lon, 118.0)
        self.assertEqual(bounds.max_lat, 41.0)


class TestPixelCoordinate(unittest.TestCase):
    """像素坐标测试"""
    
    def test_pixel_coordinate_creation(self):
        """测试像素坐标创建"""
        coord = PixelCoordinate(x=100, y=200)
        
        self.assertEqual(coord.x, 100)
        self.assertEqual(coord.y, 200)
    
    def test_pixel_coordinate_validation(self):
        """测试像素坐标验证"""
        # 有效坐标
        valid_coord = PixelCoordinate(x=100, y=200)
        self.assertTrue(valid_coord.is_valid())
        
        # 边界坐标
        boundary_coord = PixelCoordinate(x=0, y=0)
        self.assertTrue(boundary_coord.is_valid())
        
        # 无效坐标（负数）
        invalid_coord = PixelCoordinate(x=-1, y=200)
        self.assertFalse(invalid_coord.is_valid())
    
    def test_pixel_coordinate_distance(self):
        """测试像素坐标距离计算"""
        coord1 = PixelCoordinate(x=0, y=0)
        coord2 = PixelCoordinate(x=3, y=4)
        
        distance = coord1.distance_to(coord2)
        
        # 3-4-5直角三角形
        self.assertEqual(distance, 5.0)
    
    def test_pixel_coordinate_to_dict(self):
        """测试像素坐标转字典"""
        coord = PixelCoordinate(x=100, y=200)
        coord_dict = coord.to_dict()
        
        self.assertIsInstance(coord_dict, dict)
        self.assertEqual(coord_dict['x'], 100)
        self.assertEqual(coord_dict['y'], 200)


class TestImageMetadata(unittest.TestCase):
    """图像元数据测试"""
    
    def test_image_metadata_creation(self):
        """测试图像元数据创建"""
        metadata = ImageMetadata(
            width=1024,
            height=1024,
            zoom_level=18,
            center_lon=116.3974,
            center_lat=39.9093,
            bounds=GeoBounds(116.0, 117.0, 39.0, 40.0),
            tile_size=256,
            grid_size=4
        )
        
        self.assertEqual(metadata.width, 1024)
        self.assertEqual(metadata.height, 1024)
        self.assertEqual(metadata.zoom_level, 18)
        self.assertEqual(metadata.center_lon, 116.3974)
        self.assertEqual(metadata.center_lat, 39.9093)
        self.assertEqual(metadata.tile_size, 256)
        self.assertEqual(metadata.grid_size, 4)
    
    def test_image_metadata_to_dict(self):
        """测试图像元数据转字典"""
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        metadata = ImageMetadata(
            width=1024,
            height=1024,
            zoom_level=18,
            center_lon=116.3974,
            center_lat=39.9093,
            bounds=bounds,
            tile_size=256,
            grid_size=4
        )
        
        metadata_dict = metadata.to_dict()
        
        self.assertIsInstance(metadata_dict, dict)
        self.assertEqual(metadata_dict['width'], 1024)
        self.assertEqual(metadata_dict['height'], 1024)
        self.assertEqual(metadata_dict['zoom_level'], 18)
        self.assertIn('bounds', metadata_dict)


class TestTileMerger(unittest.TestCase):
    """瓦片合并器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.merger = TileMerger()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_tile(self, color=(255, 0, 0), size=(256, 256)):
        """创建测试瓦片图像"""
        image = Image.new('RGB', size, color)
        return image
    
    def test_merge_tiles_complete_grid(self):
        """测试合并完整的瓦片网格"""
        # 创建2x2的瓦片网格
        tile_paths = {}
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        
        for i, color in enumerate(colors):
            x, y = i % 2, i // 2
            tile_path = os.path.join(self.temp_dir, f'tile_{x}_{y}.png')
            tile_image = self.create_test_tile(color)
            tile_image.save(tile_path)
            tile_paths[(x, y)] = tile_path
        
        merged_image = self.merger.merge_tiles(tile_paths, grid_size=2)
        
        self.assertIsInstance(merged_image, Image.Image)
        self.assertEqual(merged_image.size, (512, 512))  # 2x2 * 256
    
    def test_merge_tiles_missing_tiles(self):
        """测试合并缺失瓦片的网格"""
        # 创建不完整的2x2网格（只有3个瓦片）
        tile_paths = {}
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        positions = [(0, 0), (1, 0), (0, 1)]  # 缺少(1, 1)
        
        for i, (color, pos) in enumerate(zip(colors, positions)):
            x, y = pos
            tile_path = os.path.join(self.temp_dir, f'tile_{x}_{y}.png')
            tile_image = self.create_test_tile(color)
            tile_image.save(tile_path)
            tile_paths[(x, y)] = tile_path
        
        merged_image = self.merger.merge_tiles(tile_paths, grid_size=2)
        
        self.assertIsInstance(merged_image, Image.Image)
        self.assertEqual(merged_image.size, (512, 512))
        
        # 检查缺失的瓦片位置是否用默认颜色填充
        # 右下角应该是默认的灰色
        pixel = merged_image.getpixel((384, 384))  # 右下角瓦片的中心
        self.assertEqual(pixel, (128, 128, 128))  # 默认灰色
    
    def test_merge_tiles_custom_tile_size(self):
        """测试自定义瓦片大小的合并"""
        tile_size = 128
        tile_paths = {}
        
        # 创建1x1的网格
        tile_path = os.path.join(self.temp_dir, 'tile_0_0.png')
        tile_image = self.create_test_tile(size=(tile_size, tile_size))
        tile_image.save(tile_path)
        tile_paths[(0, 0)] = tile_path
        
        merged_image = self.merger.merge_tiles(
            tile_paths, 
            grid_size=1, 
            tile_size=tile_size
        )
        
        self.assertEqual(merged_image.size, (tile_size, tile_size))
    
    def test_merge_tiles_empty_grid(self):
        """测试合并空网格"""
        tile_paths = {}  # 空的瓦片路径字典
        
        merged_image = self.merger.merge_tiles(tile_paths, grid_size=2)
        
        self.assertIsInstance(merged_image, Image.Image)
        self.assertEqual(merged_image.size, (512, 512))
        
        # 整个图像应该是默认颜色
        pixel = merged_image.getpixel((256, 256))  # 中心像素
        self.assertEqual(pixel, (128, 128, 128))


class TestImageProcessor(unittest.TestCase):
    """图像处理器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.processor = ImageProcessor()
    
    def test_geo_to_pixel_conversion(self):
        """测试地理坐标到像素坐标转换"""
        # 创建测试元数据
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        metadata = ImageMetadata(
            width=1024,
            height=1024,
            zoom_level=18,
            center_lon=116.5,
            center_lat=39.5,
            bounds=bounds,
            tile_size=256,
            grid_size=4
        )
        
        # 测试中心点转换
        pixel_coord = self.processor.geo_to_pixel(
            lon=116.5, lat=39.5, metadata=metadata
        )
        
        self.assertIsInstance(pixel_coord, PixelCoordinate)
        # 中心点应该在图像中心附近
        self.assertAlmostEqual(pixel_coord.x, 512, delta=50)
        self.assertAlmostEqual(pixel_coord.y, 512, delta=50)
    
    def test_pixel_to_geo_conversion(self):
        """测试像素坐标到地理坐标转换"""
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        metadata = ImageMetadata(
            width=1024,
            height=1024,
            zoom_level=18,
            center_lon=116.5,
            center_lat=39.5,
            bounds=bounds,
            tile_size=256,
            grid_size=4
        )
        
        # 测试图像中心像素转换
        geo_point = self.processor.pixel_to_geo(
            x=512, y=512, metadata=metadata
        )
        
        self.assertIsInstance(geo_point, GeoPoint)
        # 应该接近边界的中心
        self.assertAlmostEqual(geo_point.longitude, 116.5, delta=0.1)
        self.assertAlmostEqual(geo_point.latitude, 39.5, delta=0.1)
    
    def test_create_image_metadata(self):
        """测试创建图像元数据"""
        center_point = GeoPoint(longitude=116.5, latitude=39.5)
        
        metadata = self.processor.create_image_metadata(
            center_point=center_point,
            zoom_level=18,
            grid_size=4,
            tile_size=256
        )
        
        self.assertIsInstance(metadata, ImageMetadata)
        self.assertEqual(metadata.zoom_level, 18)
        self.assertEqual(metadata.grid_size, 4)
        self.assertEqual(metadata.tile_size, 256)
        self.assertEqual(metadata.width, 1024)  # 4 * 256
        self.assertEqual(metadata.height, 1024)
        self.assertEqual(metadata.center_lon, 116.5)
        self.assertEqual(metadata.center_lat, 39.5)
    
    def test_add_point_markers(self):
        """测试添加点标记"""
        # 创建测试图像
        image = Image.new('RGB', (1024, 1024), (255, 255, 255))
        
        # 创建测试点
        points = [
            GeoPoint(longitude=116.3, latitude=39.3),
            GeoPoint(longitude=116.7, latitude=39.7)
        ]
        
        # 创建测试元数据
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        metadata = ImageMetadata(
            width=1024,
            height=1024,
            zoom_level=18,
            center_lon=116.5,
            center_lat=39.5,
            bounds=bounds,
            tile_size=256,
            grid_size=4
        )
        
        marked_image = self.processor.add_point_markers(
            image=image,
            points=points,
            metadata=metadata,
            marker_color=(255, 0, 0),
            marker_size=10
        )
        
        self.assertIsInstance(marked_image, Image.Image)
        self.assertEqual(marked_image.size, image.size)
        
        # 图像应该被修改（不再是纯白色）
        self.assertNotEqual(list(marked_image.getdata()), list(image.getdata()))
    
    def test_resize_image(self):
        """测试图像尺寸调整"""
        # 创建测试图像
        original_image = Image.new('RGB', (1024, 1024), (255, 0, 0))
        
        # 调整尺寸
        resized_image = self.processor.resize_image(
            image=original_image,
            target_size=(512, 512)
        )
        
        self.assertIsInstance(resized_image, Image.Image)
        self.assertEqual(resized_image.size, (512, 512))
    
    def test_crop_image(self):
        """测试图像裁剪"""
        # 创建测试图像
        original_image = Image.new('RGB', (1024, 1024), (255, 0, 0))
        
        # 裁剪图像
        cropped_image = self.processor.crop_image(
            image=original_image,
            bbox=(100, 100, 600, 600)  # (left, top, right, bottom)
        )
        
        self.assertIsInstance(cropped_image, Image.Image)
        self.assertEqual(cropped_image.size, (500, 500))  # 600-100 = 500


class TestProcessingStats(unittest.TestCase):
    """处理统计测试"""
    
    def test_processing_stats_creation(self):
        """测试处理统计创建"""
        stats = ProcessingStats(
            total_points=100,
            processed_points=95,
            failed_points=5,
            total_tiles=400,
            downloaded_tiles=380,
            cached_tiles=20,
            processing_time=120.5,
            download_time=90.2,
            merge_time=30.3
        )
        
        self.assertEqual(stats.total_points, 100)
        self.assertEqual(stats.processed_points, 95)
        self.assertEqual(stats.failed_points, 5)
        self.assertEqual(stats.total_tiles, 400)
        self.assertEqual(stats.downloaded_tiles, 380)
        self.assertEqual(stats.cached_tiles, 20)
        self.assertEqual(stats.processing_time, 120.5)
        self.assertEqual(stats.download_time, 90.2)
        self.assertEqual(stats.merge_time, 30.3)
    
    def test_processing_stats_success_rate(self):
        """测试处理成功率计算"""
        stats = ProcessingStats(
            total_points=100,
            processed_points=95,
            failed_points=5
        )
        
        success_rate = stats.success_rate()
        self.assertEqual(success_rate, 0.95)
    
    def test_processing_stats_download_rate(self):
        """测试下载成功率计算"""
        stats = ProcessingStats(
            total_tiles=400,
            downloaded_tiles=380,
            cached_tiles=20
        )
        
        download_rate = stats.download_success_rate()
        self.assertEqual(download_rate, 1.0)  # (380 + 20) / 400 = 1.0
    
    def test_processing_stats_to_dict(self):
        """测试处理统计转字典"""
        stats = ProcessingStats(
            total_points=100,
            processed_points=95,
            processing_time=120.5
        )
        
        stats_dict = stats.to_dict()
        
        self.assertIsInstance(stats_dict, dict)
        self.assertEqual(stats_dict['total_points'], 100)
        self.assertEqual(stats_dict['processed_points'], 95)
        self.assertEqual(stats_dict['processing_time'], 120.5)
        self.assertIn('success_rate', stats_dict)


class TestDatasetMetadata(unittest.TestCase):
    """数据集元数据测试"""
    
    def test_dataset_metadata_creation(self):
        """测试数据集元数据创建"""
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        stats = ProcessingStats(total_points=100, processed_points=95)
        
        metadata = DatasetMetadata(
            name="测试数据集",
            description="这是一个测试数据集",
            source_file="test.geojson",
            output_directory="/tmp/output",
            bounds=bounds,
            zoom_level=18,
            grid_size=5,
            tile_size=256,
            total_images=95,
            processing_stats=stats,
            created_at="2024-01-01T00:00:00Z"
        )
        
        self.assertEqual(metadata.name, "测试数据集")
        self.assertEqual(metadata.description, "这是一个测试数据集")
        self.assertEqual(metadata.source_file, "test.geojson")
        self.assertEqual(metadata.output_directory, "/tmp/output")
        self.assertEqual(metadata.zoom_level, 18)
        self.assertEqual(metadata.grid_size, 5)
        self.assertEqual(metadata.tile_size, 256)
        self.assertEqual(metadata.total_images, 95)
    
    def test_dataset_metadata_to_dict(self):
        """测试数据集元数据转字典"""
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        stats = ProcessingStats(total_points=100, processed_points=95)
        
        metadata = DatasetMetadata(
            name="测试数据集",
            bounds=bounds,
            zoom_level=18,
            processing_stats=stats
        )
        
        metadata_dict = metadata.to_dict()
        
        self.assertIsInstance(metadata_dict, dict)
        self.assertEqual(metadata_dict['name'], "测试数据集")
        self.assertEqual(metadata_dict['zoom_level'], 18)
        self.assertIn('bounds', metadata_dict)
        self.assertIn('processing_stats', metadata_dict)


class TestMetadataManager(unittest.TestCase):
    """元数据管理器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = MetadataManager()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_image_metadata_json(self):
        """测试保存图像元数据为JSON"""
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        metadata = ImageMetadata(
            width=1024,
            height=1024,
            zoom_level=18,
            center_lon=116.5,
            center_lat=39.5,
            bounds=bounds,
            tile_size=256,
            grid_size=4
        )
        
        output_path = os.path.join(self.temp_dir, 'metadata.json')
        
        self.manager.save_image_metadata(
            metadata=metadata,
            output_path=output_path,
            format='json'
        )
        
        self.assertTrue(os.path.exists(output_path))
        
        # 验证JSON内容
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data['width'], 1024)
            self.assertEqual(data['zoom_level'], 18)
    
    def test_save_dataset_summary(self):
        """测试保存数据集摘要"""
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        stats = ProcessingStats(total_points=100, processed_points=95)
        
        metadata = DatasetMetadata(
            name="测试数据集",
            bounds=bounds,
            zoom_level=18,
            processing_stats=stats
        )
        
        output_path = os.path.join(self.temp_dir, 'summary.json')
        
        self.manager.save_dataset_summary(
            metadata=metadata,
            output_path=output_path,
            format='json'
        )
        
        self.assertTrue(os.path.exists(output_path))
        
        # 验证内容
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data['name'], "测试数据集")
            self.assertEqual(data['zoom_level'], 18)
    
    def test_create_coordinate_mapping(self):
        """测试创建坐标映射"""
        points = [
            GeoPoint(longitude=116.3, latitude=39.3, properties={'id': 1}),
            GeoPoint(longitude=116.7, latitude=39.7, properties={'id': 2})
        ]
        
        bounds = GeoBounds(116.0, 117.0, 39.0, 40.0)
        metadata = ImageMetadata(
            width=1024,
            height=1024,
            zoom_level=18,
            center_lon=116.5,
            center_lat=39.5,
            bounds=bounds,
            tile_size=256,
            grid_size=4
        )
        
        mapping = self.manager.create_coordinate_mapping(
            points=points,
            metadata=metadata
        )
        
        self.assertIsInstance(mapping, list)
        self.assertEqual(len(mapping), 2)
        
        # 检查映射结构
        for item in mapping:
            self.assertIn('geo_coordinates', item)
            self.assertIn('pixel_coordinates', item)
            self.assertIn('properties', item)
    
    def test_export_to_csv(self):
        """测试导出到CSV"""
        data = [
            {'name': 'Point1', 'lon': 116.3, 'lat': 39.3, 'x': 100, 'y': 200},
            {'name': 'Point2', 'lon': 116.7, 'lat': 39.7, 'x': 300, 'y': 400}
        ]
        
        output_path = os.path.join(self.temp_dir, 'data.csv')
        
        self.manager.export_to_csv(
            data=data,
            output_path=output_path,
            fieldnames=['name', 'lon', 'lat', 'x', 'y']
        )
        
        self.assertTrue(os.path.exists(output_path))
        
        # 验证CSV内容
        import csv
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['name'], 'Point1')
            self.assertEqual(float(rows[0]['lon']), 116.3)


if __name__ == '__main__':
    # 设置测试环境
    os.environ['TESTING'] = '1'
    
    # 运行测试
    unittest.main(verbosity=2)