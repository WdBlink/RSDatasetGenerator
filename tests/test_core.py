#!/usr/bin/env python3
"""核心功能测试

测试RSDatasetGenerator的核心功能，包括：
- 配置管理
- 工具函数
- 数据加载
- 下载器工厂
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.config import ConfigManager
    from src.utils import Logger, PerformanceMonitor, validate_shapefile, ensure_directory
    from src.processors.data_loader import DataLoader, GeoPoint
    from src.downloaders.factory import DownloaderFactory, DownloaderType
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行测试")
    sys.exit(1)


class TestConfigManager(unittest.TestCase):
    """配置管理器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.yaml')
        
        # 创建测试配置文件
        test_config = {
            'download': {
                'zoom_level': 18,
                'grid_size': 5
            },
            'network': {
                'max_retries': 3,
                'request_timeout': 30
            }
        }
        
        import yaml
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f)
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        config_manager = ConfigManager()
        config = config_manager.load_config(self.config_file)
        
        self.assertIsInstance(config, dict)
        self.assertIn('download', config)
        self.assertEqual(config['download']['zoom_level'], 18)
    
    def test_load_config_with_overrides(self):
        """测试配置覆盖"""
        config_manager = ConfigManager()
        overrides = {'download': {'zoom_level': 20}}
        
        config = config_manager.load_config(self.config_file, overrides)
        
        self.assertEqual(config['download']['zoom_level'], 20)
        self.assertEqual(config['download']['grid_size'], 5)  # 未覆盖的值保持不变
    
    def test_validate_config(self):
        """测试配置验证"""
        config_manager = ConfigManager()
        
        # 有效配置
        valid_config = {
            'zoom_level': 18,
            'grid_size': 5,
            'max_retries': 3
        }
        
        self.assertTrue(config_manager.validate_config(valid_config))
        
        # 无效配置
        invalid_config = {
            'zoom_level': 25,  # 超出范围
            'grid_size': -1,   # 负数
        }
        
        self.assertFalse(config_manager.validate_config(invalid_config))


class TestLogger(unittest.TestCase):
    """日志器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test.log')
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_logger_creation(self):
        """测试日志器创建"""
        logger = Logger(
            name='TestLogger',
            level='INFO',
            console_output=True,
            file_output=True,
            log_file=self.log_file
        )
        
        self.assertIsNotNone(logger.logger)
        self.assertEqual(logger.logger.name, 'TestLogger')
    
    def test_logger_file_output(self):
        """测试日志文件输出"""
        logger = Logger(
            name='TestLogger',
            level='INFO',
            console_output=False,
            file_output=True,
            log_file=self.log_file
        )
        
        logger.info("测试消息")
        
        # 检查日志文件是否创建
        self.assertTrue(os.path.exists(self.log_file))
        
        # 检查日志内容
        with open(self.log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("测试消息", content)
    
    def test_execution_timer(self):
        """测试执行时间记录"""
        logger = Logger(name='TestLogger')
        
        with logger.execution_timer("测试操作"):
            import time
            time.sleep(0.1)  # 模拟耗时操作
        
        # 这里主要测试不会抛出异常
        self.assertTrue(True)


class TestPerformanceMonitor(unittest.TestCase):
    """性能监控器测试"""
    
    def test_monitor_creation(self):
        """测试监控器创建"""
        monitor = PerformanceMonitor()
        self.assertIsNotNone(monitor)
        self.assertFalse(monitor.is_monitoring)
    
    def test_monitor_start_stop(self):
        """测试监控启动和停止"""
        monitor = PerformanceMonitor()
        
        monitor.start_monitoring()
        self.assertTrue(monitor.is_monitoring)
        
        import time
        time.sleep(0.1)  # 让监控运行一段时间
        
        monitor.stop_monitoring()
        self.assertFalse(monitor.is_monitoring)
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        monitor = PerformanceMonitor()
        
        monitor.start_monitoring()
        import time
        time.sleep(0.1)
        monitor.stop_monitoring()
        
        stats = monitor.get_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('avg_cpu_percent', stats)
        self.assertIn('avg_memory_mb', stats)
        self.assertIn('peak_memory_mb', stats)


class TestUtilityFunctions(unittest.TestCase):
    """工具函数测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_ensure_directory(self):
        """测试目录创建"""
        test_dir = os.path.join(self.temp_dir, 'test_subdir')
        
        # 目录不存在时创建
        ensure_directory(test_dir)
        self.assertTrue(os.path.exists(test_dir))
        self.assertTrue(os.path.isdir(test_dir))
        
        # 目录已存在时不报错
        ensure_directory(test_dir)
        self.assertTrue(os.path.exists(test_dir))
    
    def test_validate_shapefile_missing(self):
        """测试验证不存在的Shapefile"""
        non_existent_file = os.path.join(self.temp_dir, 'missing.shp')
        
        result = validate_shapefile(non_existent_file)
        self.assertFalse(result)
    
    @patch('geopandas.read_file')
    def test_validate_shapefile_valid(self, mock_read_file):
        """测试验证有效的Shapefile"""
        # 模拟成功读取
        mock_gdf = Mock()
        mock_gdf.empty = False
        mock_read_file.return_value = mock_gdf
        
        test_file = os.path.join(self.temp_dir, 'test.shp')
        
        # 创建空文件
        with open(test_file, 'w') as f:
            f.write('')
        
        result = validate_shapefile(test_file)
        self.assertTrue(result)
    
    @patch('geopandas.read_file')
    def test_validate_shapefile_invalid(self, mock_read_file):
        """测试验证无效的Shapefile"""
        # 模拟读取失败
        mock_read_file.side_effect = Exception("读取失败")
        
        test_file = os.path.join(self.temp_dir, 'test.shp')
        
        # 创建空文件
        with open(test_file, 'w') as f:
            f.write('')
        
        result = validate_shapefile(test_file)
        self.assertFalse(result)


class TestDataLoader(unittest.TestCase):
    """数据加载器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_loader_geojson(self):
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
                    "properties": {"name": "test"}
                }
            ]
        }
        
        with open(geojson_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        loader = DataLoader.create_loader(geojson_file)
        self.assertIsNotNone(loader)
        self.assertEqual(loader.__class__.__name__, 'GeoJSONLoader')
    
    def test_create_loader_shapefile(self):
        """测试创建Shapefile加载器"""
        shapefile = os.path.join(self.temp_dir, 'test.shp')
        
        # 创建空的shapefile（仅用于测试文件类型识别）
        with open(shapefile, 'w') as f:
            f.write('')
        
        loader = DataLoader.create_loader(shapefile)
        self.assertIsNotNone(loader)
        self.assertEqual(loader.__class__.__name__, 'ShapefileLoader')
    
    def test_create_loader_unsupported(self):
        """测试不支持的文件类型"""
        txt_file = os.path.join(self.temp_dir, 'test.txt')
        
        with open(txt_file, 'w') as f:
            f.write('test')
        
        with self.assertRaises(ValueError):
            DataLoader.create_loader(txt_file)
    
    @patch('geopandas.read_file')
    def test_load_points_from_geojson(self, mock_read_file):
        """测试从GeoJSON加载点数据"""
        # 模拟GeoDataFrame
        mock_gdf = Mock()
        mock_gdf.iterrows.return_value = [
            (0, Mock(geometry=Mock(x=116.3974, y=39.9093), to_dict=lambda: {'name': 'test1'})),
            (1, Mock(geometry=Mock(x=121.4737, y=31.2304), to_dict=lambda: {'name': 'test2'}))
        ]
        mock_read_file.return_value = mock_gdf
        
        geojson_file = os.path.join(self.temp_dir, 'test.geojson')
        with open(geojson_file, 'w') as f:
            f.write('{}')
        
        loader = DataLoader.create_loader(geojson_file)
        points = loader.load_points()
        
        self.assertEqual(len(points), 2)
        self.assertIsInstance(points[0], GeoPoint)
        self.assertEqual(points[0].longitude, 116.3974)
        self.assertEqual(points[0].latitude, 39.9093)


class TestDownloaderFactory(unittest.TestCase):
    """下载器工厂测试"""
    
    def test_create_sync_downloader(self):
        """测试创建同步下载器"""
        downloader = DownloaderFactory.create_downloader(
            downloader_type=DownloaderType.SYNC,
            max_retries=3,
            request_timeout=30
        )
        
        self.assertIsNotNone(downloader)
        self.assertEqual(downloader.__class__.__name__, 'SyncDownloader')
    
    def test_create_async_downloader(self):
        """测试创建异步下载器"""
        downloader = DownloaderFactory.create_downloader(
            downloader_type=DownloaderType.ASYNC,
            max_concurrency=10,
            max_retries=3,
            request_timeout=30
        )
        
        self.assertIsNotNone(downloader)
        self.assertEqual(downloader.__class__.__name__, 'AsyncDownloader')
    
    def test_create_auto_downloader(self):
        """测试自动选择下载器"""
        downloader = DownloaderFactory.create_downloader(
            downloader_type=DownloaderType.AUTO,
            max_concurrency=5
        )
        
        self.assertIsNotNone(downloader)
        # 自动选择应该根据并发数选择合适的下载器
    
    def test_get_available_downloaders(self):
        """测试获取可用下载器列表"""
        downloaders = DownloaderFactory.get_available_downloaders()
        
        self.assertIsInstance(downloaders, list)
        self.assertIn('sync', downloaders)
        self.assertIn('async', downloaders)
    
    def test_validate_config(self):
        """测试配置验证"""
        # 有效配置
        valid_config = {
            'downloader_type': 'async',
            'max_concurrency': 10,
            'max_retries': 3,
            'request_timeout': 30
        }
        
        self.assertTrue(DownloaderFactory.validate_config(valid_config))
        
        # 无效配置
        invalid_config = {
            'downloader_type': 'invalid_type',
            'max_concurrency': -1
        }
        
        self.assertFalse(DownloaderFactory.validate_config(invalid_config))


class TestGeoPoint(unittest.TestCase):
    """地理点测试"""
    
    def test_geo_point_creation(self):
        """测试地理点创建"""
        point = GeoPoint(
            longitude=116.3974,
            latitude=39.9093,
            properties={'name': 'Beijing'}
        )
        
        self.assertEqual(point.longitude, 116.3974)
        self.assertEqual(point.latitude, 39.9093)
        self.assertEqual(point.properties['name'], 'Beijing')
    
    def test_geo_point_validation(self):
        """测试地理点坐标验证"""
        # 有效坐标
        valid_point = GeoPoint(longitude=116.3974, latitude=39.9093)
        self.assertTrue(valid_point.is_valid())
        
        # 无效经度
        invalid_lon = GeoPoint(longitude=200.0, latitude=39.9093)
        self.assertFalse(invalid_lon.is_valid())
        
        # 无效纬度
        invalid_lat = GeoPoint(longitude=116.3974, latitude=100.0)
        self.assertFalse(invalid_lat.is_valid())
    
    def test_geo_point_distance(self):
        """测试地理点距离计算"""
        point1 = GeoPoint(longitude=116.3974, latitude=39.9093)  # 北京
        point2 = GeoPoint(longitude=121.4737, latitude=31.2304)  # 上海
        
        distance = point1.distance_to(point2)
        
        # 北京到上海的距离大约是1000公里
        self.assertGreater(distance, 1000)
        self.assertLess(distance, 1500)


if __name__ == '__main__':
    # 设置测试环境
    os.environ['TESTING'] = '1'
    
    # 运行测试
    unittest.main(verbosity=2)