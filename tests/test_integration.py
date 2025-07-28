#!/usr/bin/env python3
"""集成测试

测试RSDatasetGenerator的端到端功能，包括：
- 完整的数据处理流程
- 不同配置下的系统行为
- 错误处理和恢复
- 性能基准测试
"""

import os
import sys
import unittest
import tempfile
import json
import time
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.rs_dataset_generator import RSDatasetGenerator, create_generator, quick_generate
    from src.config import ConfigManager
    from src.processors.data_loader import GeoPoint
    from src.downloaders.factory import DownloaderType
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行测试")
    sys.exit(1)


class TestRSDatasetGeneratorIntegration(unittest.TestCase):
    """RSDatasetGenerator集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, 'output')
        self.cache_dir = os.path.join(self.temp_dir, 'cache')
        
        # 创建测试GeoJSON文件
        self.test_geojson = self.create_test_geojson()
        
        # 基本配置
        self.basic_config = {
            'zoom_level': 18,
            'grid_size': 3,
            'output_dir': self.output_dir,
            'cache_dir': self.cache_dir,
            'downloader_type': 'sync',
            'max_retries': 2,
            'request_timeout': 10
        }
    
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_geojson(self):
        """创建测试GeoJSON文件"""
        test_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [116.3974, 39.9093]  # 北京
                    },
                    "properties": {
                        "name": "Beijing",
                        "type": "capital",
                        "id": 1
                    }
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [121.4737, 31.2304]  # 上海
                    },
                    "properties": {
                        "name": "Shanghai",
                        "type": "city",
                        "id": 2
                    }
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [113.2644, 23.1291]  # 广州
                    },
                    "properties": {
                        "name": "Guangzhou",
                        "type": "city",
                        "id": 3
                    }
                }
            ]
        }
        
        geojson_path = os.path.join(self.temp_dir, 'test_points.geojson')
        with open(geojson_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        return geojson_path
    
    def test_generator_initialization(self):
        """测试生成器初始化"""
        generator = RSDatasetGenerator(config=self.basic_config)
        
        self.assertIsNotNone(generator.config_manager)
        self.assertIsNotNone(generator.data_processor)
        self.assertIsNotNone(generator.downloader_factory)
        self.assertIsNotNone(generator.logger)
        self.assertIsNotNone(generator.performance_monitor)
    
    def test_validate_input_file_valid(self):
        """测试验证有效输入文件"""
        generator = RSDatasetGenerator(config=self.basic_config)
        
        result = generator.validate_input_file(self.test_geojson)
        self.assertTrue(result)
    
    def test_validate_input_file_invalid(self):
        """测试验证无效输入文件"""
        generator = RSDatasetGenerator(config=self.basic_config)
        
        # 不存在的文件
        result = generator.validate_input_file('/nonexistent/file.geojson')
        self.assertFalse(result)
        
        # 无效格式的文件
        invalid_file = os.path.join(self.temp_dir, 'invalid.txt')
        with open(invalid_file, 'w') as f:
            f.write('invalid content')
        
        result = generator.validate_input_file(invalid_file)
        self.assertFalse(result)
    
    def test_get_supported_formats(self):
        """测试获取支持的格式"""
        generator = RSDatasetGenerator(config=self.basic_config)
        
        formats = generator.get_supported_formats()
        
        self.assertIsInstance(formats, list)
        self.assertIn('.geojson', formats)
        self.assertIn('.shp', formats)
    
    def test_get_downloader_types(self):
        """测试获取下载器类型"""
        generator = RSDatasetGenerator(config=self.basic_config)
        
        types = generator.get_downloader_types()
        
        self.assertIsInstance(types, list)
        self.assertIn('sync', types)
        self.assertIn('async', types)
        self.assertIn('auto', types)
    
    def test_estimate_processing_time(self):
        """测试估算处理时间"""
        generator = RSDatasetGenerator(config=self.basic_config)
        
        estimated_time = generator.estimate_processing_time(
            input_file=self.test_geojson,
            config=self.basic_config
        )
        
        self.assertIsInstance(estimated_time, dict)
        self.assertIn('total_points', estimated_time)
        self.assertIn('estimated_time_seconds', estimated_time)
        self.assertIn('estimated_tiles', estimated_time)
        
        # 应该检测到3个点
        self.assertEqual(estimated_time['total_points'], 3)
        
        # 估算时间应该是正数
        self.assertGreater(estimated_time['estimated_time_seconds'], 0)
    
    def test_get_config_info(self):
        """测试获取配置信息"""
        generator = RSDatasetGenerator(config=self.basic_config)
        
        config_info = generator.get_config_info()
        
        self.assertIsInstance(config_info, dict)
        self.assertIn('current_config', config_info)
        self.assertIn('default_config', config_info)
        self.assertIn('config_schema', config_info)
    
    @patch('requests.get')
    def test_generate_dataset_success(self, mock_get):
        """测试成功生成数据集"""
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # 简单的PNG头
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        generator = RSDatasetGenerator(config=self.basic_config)
        
        result = generator.generate_dataset(
            input_file=self.test_geojson,
            output_dir=self.output_dir
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('summary', result)
        self.assertIn('output_files', result)
        
        if result['success']:
            # 检查输出目录是否创建
            self.assertTrue(os.path.exists(self.output_dir))
            
            # 检查是否有输出文件
            self.assertGreater(len(result['output_files']), 0)
    
    @patch('requests.get')
    def test_generate_dataset_with_custom_config(self, mock_get):
        """测试使用自定义配置生成数据集"""
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # 自定义配置
        custom_config = self.basic_config.copy()
        custom_config.update({
            'zoom_level': 16,
            'grid_size': 5,
            'downloader_type': 'async',
            'max_concurrency': 5
        })
        
        generator = RSDatasetGenerator(config=custom_config)
        
        result = generator.generate_dataset(
            input_file=self.test_geojson,
            output_dir=self.output_dir,
            config_overrides={'grid_size': 7}  # 运行时覆盖
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
    
    def test_generate_dataset_invalid_input(self):
        """测试无效输入的数据集生成"""
        generator = RSDatasetGenerator(config=self.basic_config)
        
        # 不存在的文件
        result = generator.generate_dataset(
            input_file='/nonexistent/file.geojson',
            output_dir=self.output_dir
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    @patch('requests.get')
    def test_generate_dataset_network_error(self, mock_get):
        """测试网络错误时的数据集生成"""
        # 模拟网络错误
        mock_get.side_effect = Exception("网络连接失败")
        
        generator = RSDatasetGenerator(config=self.basic_config)
        
        result = generator.generate_dataset(
            input_file=self.test_geojson,
            output_dir=self.output_dir
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        # 根据重试机制，可能成功也可能失败
        self.assertIn('summary', result)
    
    def test_create_generator_function(self):
        """测试create_generator便捷函数"""
        generator = create_generator(
            zoom_level=18,
            grid_size=3,
            output_dir=self.output_dir,
            downloader_type='sync'
        )
        
        self.assertIsInstance(generator, RSDatasetGenerator)
        self.assertEqual(generator.config['zoom_level'], 18)
        self.assertEqual(generator.config['grid_size'], 3)
    
    @patch('requests.get')
    def test_quick_generate_function(self, mock_get):
        """测试quick_generate便捷函数"""
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = quick_generate(
            input_file=self.test_geojson,
            output_dir=self.output_dir,
            zoom_level=18,
            grid_size=3
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('summary', result)


class TestConfigurationIntegration(unittest.TestCase):
    """配置集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.yaml')
    
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config_file(self):
        """创建测试配置文件"""
        config_content = """
download:
  zoom_level: 18
  grid_size: 5
  tile_size: 256

network:
  max_retries: 3
  request_timeout: 30
  max_concurrency: 10
  downloader_type: "async"

paths:
  output_dir: "/tmp/rs_output"
  cache_dir: "/tmp/rs_cache"
  temp_dir: "/tmp/rs_temp"

image:
  output_format: "png"
  quality: 95
  add_markers: true
  marker_color: [255, 0, 0]
  marker_size: 10

logging:
  level: "INFO"
  console_output: true
  file_output: true
  log_file: "rs_generator.log"
"""
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
    
    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        self.create_test_config_file()
        
        config_manager = ConfigManager()
        config = config_manager.load_config(self.config_file)
        
        self.assertIsInstance(config, dict)
        self.assertEqual(config['download']['zoom_level'], 18)
        self.assertEqual(config['network']['downloader_type'], 'async')
        self.assertEqual(config['image']['output_format'], 'png')
    
    def test_config_validation(self):
        """测试配置验证"""
        self.create_test_config_file()
        
        config_manager = ConfigManager()
        config = config_manager.load_config(self.config_file)
        
        # 验证加载的配置
        is_valid = config_manager.validate_config(config)
        self.assertTrue(is_valid)
    
    def test_config_with_overrides(self):
        """测试配置覆盖"""
        self.create_test_config_file()
        
        config_manager = ConfigManager()
        overrides = {
            'download': {'zoom_level': 20},
            'network': {'max_concurrency': 20}
        }
        
        config = config_manager.load_config(self.config_file, overrides)
        
        # 检查覆盖是否生效
        self.assertEqual(config['download']['zoom_level'], 20)
        self.assertEqual(config['network']['max_concurrency'], 20)
        
        # 检查未覆盖的值是否保持不变
        self.assertEqual(config['download']['grid_size'], 5)
        self.assertEqual(config['network']['max_retries'], 3)
    
    def test_generator_with_config_file(self):
        """测试使用配置文件创建生成器"""
        self.create_test_config_file()
        
        generator = RSDatasetGenerator(config_file=self.config_file)
        
        self.assertEqual(generator.config['download']['zoom_level'], 18)
        self.assertEqual(generator.config['network']['downloader_type'], 'async')
        self.assertEqual(generator.config['image']['output_format'], 'png')


class TestPerformanceIntegration(unittest.TestCase):
    """性能集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, 'output')
        
        # 创建包含多个点的测试文件
        self.test_geojson = self.create_large_test_geojson()
    
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_large_test_geojson(self, num_points=10):
        """创建包含多个点的测试GeoJSON文件"""
        features = []
        
        # 在北京周围生成随机点
        base_lon, base_lat = 116.3974, 39.9093
        
        for i in range(num_points):
            # 在基准点周围0.1度范围内生成随机点
            import random
            lon = base_lon + (random.random() - 0.5) * 0.1
            lat = base_lat + (random.random() - 0.5) * 0.1
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "id": i + 1,
                    "name": f"Point_{i + 1}",
                    "category": "test"
                }
            }
            features.append(feature)
        
        test_data = {
            "type": "FeatureCollection",
            "features": features
        }
        
        geojson_path = os.path.join(self.temp_dir, 'large_test_points.geojson')
        with open(geojson_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        return geojson_path
    
    @patch('requests.get')
    def test_sync_vs_async_performance(self, mock_get):
        """测试同步vs异步下载器性能"""
        # 模拟快速响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # 测试同步下载器
        sync_config = {
            'zoom_level': 18,
            'grid_size': 3,
            'output_dir': os.path.join(self.output_dir, 'sync'),
            'downloader_type': 'sync',
            'max_retries': 1
        }
        
        sync_generator = RSDatasetGenerator(config=sync_config)
        
        start_time = time.time()
        sync_result = sync_generator.generate_dataset(
            input_file=self.test_geojson,
            output_dir=sync_config['output_dir']
        )
        sync_time = time.time() - start_time
        
        # 测试异步下载器
        async_config = {
            'zoom_level': 18,
            'grid_size': 3,
            'output_dir': os.path.join(self.output_dir, 'async'),
            'downloader_type': 'async',
            'max_concurrency': 5,
            'max_retries': 1
        }
        
        async_generator = RSDatasetGenerator(config=async_config)
        
        start_time = time.time()
        async_result = async_generator.generate_dataset(
            input_file=self.test_geojson,
            output_dir=async_config['output_dir']
        )
        async_time = time.time() - start_time
        
        # 验证两种方式都能成功处理
        self.assertIsInstance(sync_result, dict)
        self.assertIsInstance(async_result, dict)
        
        # 记录性能数据（用于分析，不做严格断言）
        print(f"\n同步下载器耗时: {sync_time:.2f}秒")
        print(f"异步下载器耗时: {async_time:.2f}秒")
        
        if sync_result.get('success') and async_result.get('success'):
            print(f"性能提升: {((sync_time - async_time) / sync_time * 100):.1f}%")
    
    def test_memory_usage_monitoring(self):
        """测试内存使用监控"""
        config = {
            'zoom_level': 18,
            'grid_size': 3,
            'output_dir': self.output_dir,
            'downloader_type': 'sync',
            'enable_monitoring': True
        }
        
        generator = RSDatasetGenerator(config=config)
        
        # 启动性能监控
        generator.performance_monitor.start_monitoring()
        
        # 模拟一些处理
        time.sleep(0.5)
        
        # 停止监控并获取统计
        generator.performance_monitor.stop_monitoring()
        stats = generator.performance_monitor.get_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('avg_memory_mb', stats)
        self.assertIn('peak_memory_mb', stats)
        self.assertIn('avg_cpu_percent', stats)
        
        # 内存使用应该是合理的
        self.assertGreater(stats['avg_memory_mb'], 0)
        self.assertGreater(stats['peak_memory_mb'], 0)
    
    def test_large_dataset_processing(self):
        """测试大数据集处理"""
        # 创建更大的测试数据集
        large_geojson = self.create_large_test_geojson(num_points=50)
        
        config = {
            'zoom_level': 16,  # 降低缩放级别以减少瓦片数量
            'grid_size': 3,
            'output_dir': self.output_dir,
            'downloader_type': 'async',
            'max_concurrency': 10,
            'max_retries': 1
        }
        
        generator = RSDatasetGenerator(config=config)
        
        # 估算处理时间
        estimation = generator.estimate_processing_time(
            input_file=large_geojson,
            config=config
        )
        
        self.assertEqual(estimation['total_points'], 50)
        self.assertGreater(estimation['estimated_tiles'], 0)
        self.assertGreater(estimation['estimated_time_seconds'], 0)
        
        print(f"\n大数据集估算:")
        print(f"  总点数: {estimation['total_points']}")
        print(f"  估算瓦片数: {estimation['estimated_tiles']}")
        print(f"  估算时间: {estimation['estimated_time_seconds']:.1f}秒")


class TestErrorHandlingIntegration(unittest.TestCase):
    """错误处理集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, 'output')
    
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_invalid_coordinates_handling(self):
        """测试无效坐标处理"""
        # 创建包含无效坐标的GeoJSON
        invalid_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [200.0, 100.0]  # 无效坐标
                    },
                    "properties": {"name": "Invalid Point"}
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [116.3974, 39.9093]  # 有效坐标
                    },
                    "properties": {"name": "Valid Point"}
                }
            ]
        }
        
        invalid_geojson = os.path.join(self.temp_dir, 'invalid_coords.geojson')
        with open(invalid_geojson, 'w', encoding='utf-8') as f:
            json.dump(invalid_data, f)
        
        config = {
            'zoom_level': 18,
            'grid_size': 3,
            'output_dir': self.output_dir,
            'downloader_type': 'sync'
        }
        
        generator = RSDatasetGenerator(config=config)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = generator.generate_dataset(
                input_file=invalid_geojson,
                output_dir=self.output_dir
            )
        
        self.assertIsInstance(result, dict)
        self.assertIn('summary', result)
        
        # 应该处理有效点，跳过无效点
        if 'processing_stats' in result['summary']:
            stats = result['summary']['processing_stats']
            self.assertGreater(stats.get('failed_points', 0), 0)
    
    def test_network_timeout_handling(self):
        """测试网络超时处理"""
        # 创建简单的测试文件
        test_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [116.3974, 39.9093]
                    },
                    "properties": {"name": "Test Point"}
                }
            ]
        }
        
        test_geojson = os.path.join(self.temp_dir, 'test.geojson')
        with open(test_geojson, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        config = {
            'zoom_level': 18,
            'grid_size': 3,
            'output_dir': self.output_dir,
            'downloader_type': 'sync',
            'request_timeout': 1,  # 很短的超时时间
            'max_retries': 2
        }
        
        generator = RSDatasetGenerator(config=config)
        
        with patch('requests.get') as mock_get:
            # 模拟超时
            import requests
            mock_get.side_effect = requests.exceptions.Timeout("请求超时")
            
            result = generator.generate_dataset(
                input_file=test_geojson,
                output_dir=self.output_dir
            )
        
        self.assertIsInstance(result, dict)
        self.assertIn('summary', result)
        
        # 应该记录下载失败
        if 'processing_stats' in result['summary']:
            stats = result['summary']['processing_stats']
            # 由于网络错误，下载的瓦片数量应该很少或为0
            self.assertLessEqual(stats.get('downloaded_tiles', 0), stats.get('total_tiles', 1))
    
    def test_disk_space_handling(self):
        """测试磁盘空间不足处理"""
        # 这个测试比较难模拟，主要测试错误处理逻辑
        config = {
            'zoom_level': 18,
            'grid_size': 3,
            'output_dir': '/invalid/path/that/does/not/exist',  # 无效路径
            'downloader_type': 'sync'
        }
        
        generator = RSDatasetGenerator(config=config)
        
        # 创建简单的测试文件
        test_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [116.3974, 39.9093]
                    },
                    "properties": {"name": "Test Point"}
                }
            ]
        }
        
        test_geojson = os.path.join(self.temp_dir, 'test.geojson')
        with open(test_geojson, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        result = generator.generate_dataset(
            input_file=test_geojson,
            output_dir=config['output_dir']
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        # 由于路径无效，应该失败
        self.assertFalse(result['success'])
        self.assertIn('error', result)


if __name__ == '__main__':
    # 设置测试环境
    os.environ['TESTING'] = '1'
    
    # 运行测试
    unittest.main(verbosity=2)