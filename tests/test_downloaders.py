#!/usr/bin/env python3
"""下载器模块测试

测试同步和异步下载器的功能，包括：
- 瓦片下载
- 错误处理
- 重试机制
- 并发控制
"""

import os
import sys
import unittest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.downloaders.sync_downloader import SyncDownloader
    from src.downloaders.async_downloader import AsyncDownloader
    from src.downloaders.base_downloader import BaseDownloader, TileCoordinate
    from src.downloaders.factory import DownloaderFactory, DownloaderType
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行测试")
    sys.exit(1)


class TestTileCoordinate(unittest.TestCase):
    """瓦片坐标测试"""
    
    def test_tile_coordinate_creation(self):
        """测试瓦片坐标创建"""
        coord = TileCoordinate(x=100, y=200, z=18)
        
        self.assertEqual(coord.x, 100)
        self.assertEqual(coord.y, 200)
        self.assertEqual(coord.z, 18)
    
    def test_tile_coordinate_validation(self):
        """测试瓦片坐标验证"""
        # 有效坐标
        valid_coord = TileCoordinate(x=100, y=200, z=18)
        self.assertTrue(valid_coord.is_valid())
        
        # 无效缩放级别
        invalid_z = TileCoordinate(x=100, y=200, z=25)
        self.assertFalse(invalid_z.is_valid())
        
        # 负坐标
        negative_coord = TileCoordinate(x=-1, y=200, z=18)
        self.assertFalse(negative_coord.is_valid())
    
    def test_tile_coordinate_bounds_check(self):
        """测试瓦片坐标边界检查"""
        # 在边界内的坐标
        coord = TileCoordinate(x=100, y=200, z=10)
        self.assertTrue(coord.is_within_bounds())
        
        # 超出边界的坐标
        max_coord = 2 ** 10  # 2^z
        out_of_bounds = TileCoordinate(x=max_coord, y=200, z=10)
        self.assertFalse(out_of_bounds.is_within_bounds())
    
    def test_tile_coordinate_to_url(self):
        """测试瓦片坐标转URL"""
        coord = TileCoordinate(x=100, y=200, z=18)
        url = coord.to_url()
        
        self.assertIsInstance(url, str)
        self.assertIn('100', url)
        self.assertIn('200', url)
        self.assertIn('18', url)
    
    def test_tile_coordinate_equality(self):
        """测试瓦片坐标相等性"""
        coord1 = TileCoordinate(x=100, y=200, z=18)
        coord2 = TileCoordinate(x=100, y=200, z=18)
        coord3 = TileCoordinate(x=101, y=200, z=18)
        
        self.assertEqual(coord1, coord2)
        self.assertNotEqual(coord1, coord3)
    
    def test_tile_coordinate_hash(self):
        """测试瓦片坐标哈希"""
        coord1 = TileCoordinate(x=100, y=200, z=18)
        coord2 = TileCoordinate(x=100, y=200, z=18)
        
        # 相同坐标应该有相同的哈希值
        self.assertEqual(hash(coord1), hash(coord2))
        
        # 可以用作字典键
        tile_dict = {coord1: "test"}
        self.assertEqual(tile_dict[coord2], "test")


class TestBaseDownloader(unittest.TestCase):
    """基础下载器测试"""
    
    def test_base_downloader_abstract(self):
        """测试基础下载器是抽象类"""
        with self.assertRaises(TypeError):
            BaseDownloader()
    
    def test_geo_to_tile_conversion(self):
        """测试地理坐标到瓦片坐标转换"""
        # 使用具体的下载器实现来测试
        downloader = SyncDownloader()
        
        # 北京坐标
        lon, lat = 116.3974, 39.9093
        zoom = 18
        
        tile_coord = downloader.geo_to_tile(lon, lat, zoom)
        
        self.assertIsInstance(tile_coord, TileCoordinate)
        self.assertEqual(tile_coord.z, zoom)
        self.assertGreater(tile_coord.x, 0)
        self.assertGreater(tile_coord.y, 0)
    
    def test_tile_to_geo_conversion(self):
        """测试瓦片坐标到地理坐标转换"""
        downloader = SyncDownloader()
        
        # 先转换为瓦片坐标，再转换回地理坐标
        original_lon, original_lat = 116.3974, 39.9093
        zoom = 18
        
        tile_coord = downloader.geo_to_tile(original_lon, original_lat, zoom)
        converted_lon, converted_lat = downloader.tile_to_geo(tile_coord.x, tile_coord.y, zoom)
        
        # 由于精度损失，使用近似比较
        self.assertAlmostEqual(original_lon, converted_lon, places=4)
        self.assertAlmostEqual(original_lat, converted_lat, places=4)
    
    def test_calculate_tile_grid(self):
        """测试计算瓦片网格"""
        downloader = SyncDownloader()
        
        center_lon, center_lat = 116.3974, 39.9093
        zoom = 18
        grid_size = 3
        
        tiles = downloader.calculate_tile_grid(center_lon, center_lat, zoom, grid_size)
        
        self.assertIsInstance(tiles, list)
        self.assertEqual(len(tiles), grid_size * grid_size)
        
        # 检查所有瓦片都是有效的
        for tile in tiles:
            self.assertIsInstance(tile, TileCoordinate)
            self.assertTrue(tile.is_valid())


class TestSyncDownloader(unittest.TestCase):
    """同步下载器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = SyncDownloader(
            cache_dir=self.temp_dir,
            max_retries=2,
            request_timeout=10
        )
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_downloader_initialization(self):
        """测试下载器初始化"""
        self.assertEqual(self.downloader.cache_dir, self.temp_dir)
        self.assertEqual(self.downloader.max_retries, 2)
        self.assertEqual(self.downloader.request_timeout, 10)
    
    @patch('requests.get')
    def test_download_single_tile_success(self, mock_get):
        """测试成功下载单个瓦片"""
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake_image_data'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        tile_coord = TileCoordinate(x=100, y=200, z=18)
        result = self.downloader.download_tile(tile_coord)
        
        self.assertTrue(result)
        
        # 检查文件是否保存
        expected_path = os.path.join(self.temp_dir, '18', '100', '200.png')
        self.assertTrue(os.path.exists(expected_path))
    
    @patch('requests.get')
    def test_download_single_tile_failure(self, mock_get):
        """测试下载单个瓦片失败"""
        # 模拟HTTP错误
        mock_get.side_effect = Exception("网络错误")
        
        tile_coord = TileCoordinate(x=100, y=200, z=18)
        result = self.downloader.download_tile(tile_coord)
        
        self.assertFalse(result)
    
    @patch('requests.get')
    def test_download_with_retry(self, mock_get):
        """测试重试机制"""
        # 第一次失败，第二次成功
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake_image_data'
        mock_response.raise_for_status.return_value = None
        
        mock_get.side_effect = [Exception("网络错误"), mock_response]
        
        tile_coord = TileCoordinate(x=100, y=200, z=18)
        result = self.downloader.download_tile(tile_coord)
        
        self.assertTrue(result)
        self.assertEqual(mock_get.call_count, 2)
    
    def test_cache_check(self):
        """测试缓存检查"""
        tile_coord = TileCoordinate(x=100, y=200, z=18)
        
        # 初始时缓存中没有文件
        self.assertFalse(self.downloader.is_tile_cached(tile_coord))
        
        # 创建缓存文件
        cache_path = self.downloader.get_tile_path(tile_coord)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'wb') as f:
            f.write(b'cached_data')
        
        # 现在应该检测到缓存
        self.assertTrue(self.downloader.is_tile_cached(tile_coord))
    
    @patch('requests.get')
    def test_download_tiles_batch(self, mock_get):
        """测试批量下载瓦片"""
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake_image_data'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        tiles = [
            TileCoordinate(x=100, y=200, z=18),
            TileCoordinate(x=101, y=200, z=18),
            TileCoordinate(x=100, y=201, z=18)
        ]
        
        results = self.downloader.download_tiles(tiles)
        
        self.assertEqual(len(results), 3)
        self.assertTrue(all(results))
    
    def test_get_tile_path(self):
        """测试获取瓦片路径"""
        tile_coord = TileCoordinate(x=100, y=200, z=18)
        path = self.downloader.get_tile_path(tile_coord)
        
        expected_path = os.path.join(self.temp_dir, '18', '100', '200.png')
        self.assertEqual(path, expected_path)


class TestAsyncDownloader(unittest.TestCase):
    """异步下载器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = AsyncDownloader(
            cache_dir=self.temp_dir,
            max_concurrency=5,
            max_retries=2,
            request_timeout=10
        )
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_async_downloader_initialization(self):
        """测试异步下载器初始化"""
        self.assertEqual(self.downloader.cache_dir, self.temp_dir)
        self.assertEqual(self.downloader.max_concurrency, 5)
        self.assertEqual(self.downloader.max_retries, 2)
        self.assertEqual(self.downloader.request_timeout, 10)
    
    @patch('aiohttp.ClientSession.get')
    async def test_async_download_single_tile_success(self, mock_get):
        """测试异步成功下载单个瓦片"""
        # 模拟成功的异步HTTP响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b'fake_image_data')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_get.return_value = mock_response
        
        tile_coord = TileCoordinate(x=100, y=200, z=18)
        
        async with self.downloader:
            result = await self.downloader.download_tile_async(tile_coord)
        
        self.assertTrue(result)
    
    @patch('aiohttp.ClientSession.get')
    async def test_async_download_single_tile_failure(self, mock_get):
        """测试异步下载单个瓦片失败"""
        # 模拟异步HTTP错误
        mock_get.side_effect = Exception("网络错误")
        
        tile_coord = TileCoordinate(x=100, y=200, z=18)
        
        async with self.downloader:
            result = await self.downloader.download_tile_async(tile_coord)
        
        self.assertFalse(result)
    
    @patch('aiohttp.ClientSession.get')
    async def test_async_download_tiles_batch(self, mock_get):
        """测试异步批量下载瓦片"""
        # 模拟成功的异步HTTP响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b'fake_image_data')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_get.return_value = mock_response
        
        tiles = [
            TileCoordinate(x=100, y=200, z=18),
            TileCoordinate(x=101, y=200, z=18),
            TileCoordinate(x=100, y=201, z=18)
        ]
        
        async with self.downloader:
            results = await self.downloader.download_tiles_async(tiles)
        
        self.assertEqual(len(results), 3)
        self.assertTrue(all(results))
    
    def test_sync_wrapper(self):
        """测试同步包装器"""
        tiles = [
            TileCoordinate(x=100, y=200, z=18),
            TileCoordinate(x=101, y=200, z=18)
        ]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模拟成功的异步HTTP响应
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=b'fake_image_data')
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_get.return_value = mock_response
            
            # 使用同步接口
            results = self.downloader.download_tiles(tiles)
            
            self.assertEqual(len(results), 2)
    
    def test_context_manager(self):
        """测试上下文管理器"""
        async def test_context():
            async with self.downloader as downloader:
                self.assertIsNotNone(downloader.session)
            
            # 退出上下文后session应该被关闭
            self.assertIsNone(downloader.session)
        
        asyncio.run(test_context())


class TestDownloaderFactory(unittest.TestCase):
    """下载器工厂测试"""
    
    def test_create_sync_downloader(self):
        """测试创建同步下载器"""
        downloader = DownloaderFactory.create_downloader(
            downloader_type=DownloaderType.SYNC,
            cache_dir='/tmp/test',
            max_retries=3
        )
        
        self.assertIsInstance(downloader, SyncDownloader)
        self.assertEqual(downloader.cache_dir, '/tmp/test')
        self.assertEqual(downloader.max_retries, 3)
    
    def test_create_async_downloader(self):
        """测试创建异步下载器"""
        downloader = DownloaderFactory.create_downloader(
            downloader_type=DownloaderType.ASYNC,
            cache_dir='/tmp/test',
            max_concurrency=10,
            max_retries=3
        )
        
        self.assertIsInstance(downloader, AsyncDownloader)
        self.assertEqual(downloader.cache_dir, '/tmp/test')
        self.assertEqual(downloader.max_concurrency, 10)
        self.assertEqual(downloader.max_retries, 3)
    
    def test_create_auto_downloader_small_batch(self):
        """测试自动选择下载器（小批量）"""
        downloader = DownloaderFactory.create_downloader(
            downloader_type=DownloaderType.AUTO,
            max_concurrency=2  # 小并发数，应该选择同步下载器
        )
        
        self.assertIsInstance(downloader, SyncDownloader)
    
    def test_create_auto_downloader_large_batch(self):
        """测试自动选择下载器（大批量）"""
        downloader = DownloaderFactory.create_downloader(
            downloader_type=DownloaderType.AUTO,
            max_concurrency=20  # 大并发数，应该选择异步下载器
        )
        
        self.assertIsInstance(downloader, AsyncDownloader)
    
    def test_register_custom_downloader(self):
        """测试注册自定义下载器"""
        class CustomDownloader(BaseDownloader):
            def download_tile(self, tile_coord):
                return True
            
            def download_tiles(self, tile_coords):
                return [True] * len(tile_coords)
        
        # 注册自定义下载器
        DownloaderFactory.register_downloader('custom', CustomDownloader)
        
        # 检查是否注册成功
        available = DownloaderFactory.get_available_downloaders()
        self.assertIn('custom', available)
        
        # 创建自定义下载器
        downloader = DownloaderFactory.create_downloader('custom')
        self.assertIsInstance(downloader, CustomDownloader)
    
    def test_get_downloader_info(self):
        """测试获取下载器信息"""
        info = DownloaderFactory.get_downloader_info()
        
        self.assertIsInstance(info, dict)
        self.assertIn('sync', info)
        self.assertIn('async', info)
        
        # 检查信息结构
        sync_info = info['sync']
        self.assertIn('class', sync_info)
        self.assertIn('description', sync_info)
        self.assertIn('features', sync_info)
    
    def test_validate_config_valid(self):
        """测试有效配置验证"""
        valid_config = {
            'downloader_type': 'async',
            'max_concurrency': 10,
            'max_retries': 3,
            'request_timeout': 30,
            'cache_dir': '/tmp/test'
        }
        
        self.assertTrue(DownloaderFactory.validate_config(valid_config))
    
    def test_validate_config_invalid(self):
        """测试无效配置验证"""
        invalid_configs = [
            {'downloader_type': 'invalid_type'},
            {'max_concurrency': -1},
            {'max_retries': -1},
            {'request_timeout': 0}
        ]
        
        for config in invalid_configs:
            with self.subTest(config=config):
                self.assertFalse(DownloaderFactory.validate_config(config))
    
    def test_create_downloader_invalid_type(self):
        """测试创建无效类型的下载器"""
        with self.assertRaises(ValueError):
            DownloaderFactory.create_downloader('invalid_type')


class TestDownloaderIntegration(unittest.TestCase):
    """下载器集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_sync_async_compatibility(self):
        """测试同步和异步下载器的兼容性"""
        # 创建相同的瓦片坐标
        tiles = [
            TileCoordinate(x=100, y=200, z=18),
            TileCoordinate(x=101, y=200, z=18)
        ]
        
        sync_downloader = SyncDownloader(cache_dir=self.temp_dir)
        async_downloader = AsyncDownloader(cache_dir=self.temp_dir)
        
        # 两个下载器应该生成相同的路径
        for tile in tiles:
            sync_path = sync_downloader.get_tile_path(tile)
            async_path = async_downloader.get_tile_path(tile)
            self.assertEqual(sync_path, async_path)
    
    def test_coordinate_conversion_consistency(self):
        """测试坐标转换的一致性"""
        sync_downloader = SyncDownloader()
        async_downloader = AsyncDownloader()
        
        # 测试地理坐标
        lon, lat, zoom = 116.3974, 39.9093, 18
        
        # 两个下载器应该产生相同的瓦片坐标
        sync_tile = sync_downloader.geo_to_tile(lon, lat, zoom)
        async_tile = async_downloader.geo_to_tile(lon, lat, zoom)
        
        self.assertEqual(sync_tile, async_tile)
        
        # 反向转换也应该一致
        sync_geo = sync_downloader.tile_to_geo(sync_tile.x, sync_tile.y, zoom)
        async_geo = async_downloader.tile_to_geo(async_tile.x, async_tile.y, zoom)
        
        self.assertAlmostEqual(sync_geo[0], async_geo[0], places=10)
        self.assertAlmostEqual(sync_geo[1], async_geo[1], places=10)


if __name__ == '__main__':
    # 设置测试环境
    os.environ['TESTING'] = '1'
    
    # 运行测试
    unittest.main(verbosity=2)