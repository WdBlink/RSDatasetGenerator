"""异步下载器模块

实现基于aiohttp的异步瓦片下载功能。
适用于大规模数据下载，提供高并发性能。
"""

import asyncio
import time
import random
from typing import List, Optional
from PIL import Image
from io import BytesIO
import aiohttp
from aiohttp import TCPConnector, ClientTimeout

from .base import BaseDownloader, TileInfo, DownloadResult
from ..utils import DownloadError


class AsyncDownloader(BaseDownloader):
    """异步下载器
    
    使用aiohttp库实现的异步瓦片下载器。
    特点：
    - 高并发性能
    - 资源使用效率高
    - 适合大规模下载
    - 支持连接池管理
    """
    
    def __init__(self, config):
        """初始化异步下载器
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        
        # 并发控制
        self.semaphore = asyncio.Semaphore(config.download.max_concurrency)
        
        # 会话配置
        self.connector = TCPConnector(
            limit=config.download.max_concurrency * 2,
            limit_per_host=config.download.max_concurrency,
            ssl=False
        )
        
        self.timeout = ClientTimeout(total=config.download.request_timeout)
        
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.logger.info(f"异步下载器初始化完成，最大并发数: {config.download.max_concurrency}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self._close_session()
    
    async def _ensure_session(self):
        """确保会话已创建"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout,
                headers=self.config.network.headers
            )
    
    async def _close_session(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    def download_tile(self, tile_info: TileInfo) -> DownloadResult:
        """下载单个瓦片（同步接口）
        
        Args:
            tile_info: 瓦片信息
            
        Returns:
            下载结果
        """
        # 为了保持接口一致性，提供同步包装
        return asyncio.run(self.download_tile_async(tile_info))
    
    async def download_tile_async(self, tile_info: TileInfo) -> DownloadResult:
        """异步下载单个瓦片
        
        Args:
            tile_info: 瓦片信息
            
        Returns:
            下载结果
        """
        start_time = time.time()
        
        # 检查缓存
        cached_image = self.load_cached_tile(tile_info)
        if cached_image is not None:
            return DownloadResult(
                tile_info=tile_info,
                success=True,
                image=cached_image,
                download_time=0.0,
                from_cache=True
            )
        
        # 验证坐标
        if not self.validate_tile_coordinates(tile_info.x, tile_info.y, tile_info.z):
            return DownloadResult(
                tile_info=tile_info,
                success=False,
                error=f"无效的瓦片坐标: ({tile_info.x}, {tile_info.y}, {tile_info.z})"
            )
        
        # 确保会话存在
        await self._ensure_session()
        
        # 尝试下载
        for attempt in range(self.config.download.max_retries + 1):
            try:
                result = await self._download_with_retry_async(tile_info, attempt)
                if result.success:
                    result.download_time = time.time() - start_time
                    self.monitor.update_stats('successful_downloads')
                    return result
                
            except Exception as e:
                self.logger.warning(
                    f"下载瓦片失败 (尝试 {attempt + 1}/{self.config.download.max_retries + 1}): "
                    f"{tile_info.url}, 错误: {str(e)}"
                )
                
                if attempt < self.config.download.max_retries:
                    # 指数退避
                    backoff_time = self.config.download.backoff_base ** attempt
                    retry_wait = random.uniform(*self.config.download.retry_wait_range)
                    total_wait = backoff_time + retry_wait
                    
                    self.logger.debug(f"等待 {total_wait:.1f} 秒后重试")
                    await asyncio.sleep(total_wait)
        
        # 所有重试都失败
        self.monitor.update_stats('failed_downloads')
        return DownloadResult(
            tile_info=tile_info,
            success=False,
            error=f"下载失败，已重试 {self.config.download.max_retries} 次",
            download_time=time.time() - start_time
        )
    
    async def _download_with_retry_async(self, tile_info: TileInfo, attempt: int) -> DownloadResult:
        """执行单次异步下载尝试
        
        Args:
            tile_info: 瓦片信息
            attempt: 尝试次数
            
        Returns:
            下载结果
            
        Raises:
            DownloadError: 下载失败
        """
        async with self.semaphore:  # 控制并发数
            try:
                # 添加随机延迟
                if attempt > 0:
                    min_interval, max_interval = self.config.download.request_interval_range
                    delay = random.uniform(min_interval, max_interval)
                    await asyncio.sleep(delay)
                
                # 发送请求
                async with self.session.get(tile_info.url) as response:
                    # 检查响应状态
                    response.raise_for_status()
                    
                    # 检查内容类型
                    content_type = response.headers.get('content-type', '')
                    if not content_type.startswith('image/'):
                        raise DownloadError(f"响应不是图像类型: {content_type}")
                    
                    # 读取图像数据
                    image_data = await response.read()
                    if len(image_data) == 0:
                        raise DownloadError("响应内容为空")
                    
                    # 解析图像
                    try:
                        image = Image.open(BytesIO(image_data)).convert('RGB')
                    except Exception as e:
                        raise DownloadError(f"图像解析失败: {str(e)}")
                    
                    # 验证图像尺寸
                    if image.size != (256, 256):
                        self.logger.warning(
                            f"瓦片尺寸异常: {image.size}, 预期: (256, 256), "
                            f"瓦片: ({tile_info.x}, {tile_info.y}, {tile_info.z})"
                        )
                    
                    # 保存瓦片
                    self.save_tile(tile_info, image)
                    
                    return DownloadResult(
                        tile_info=tile_info,
                        success=True,
                        image=image,
                        file_size=len(image_data)
                    )
                    
            except asyncio.TimeoutError:
                raise DownloadError("请求超时")
            except aiohttp.ClientConnectionError:
                raise DownloadError("连接错误")
            except aiohttp.ClientResponseError as e:
                if e.status == 404:
                    raise DownloadError("瓦片不存在 (404)")
                elif e.status == 429:
                    raise DownloadError("请求过于频繁 (429)")
                elif e.status >= 500:
                    raise DownloadError(f"服务器错误 ({e.status})")
                else:
                    raise DownloadError(f"HTTP错误 ({e.status})")
            except Exception as e:
                raise DownloadError(f"未知错误: {str(e)}")
    
    def download_tiles(self, tiles: List[TileInfo]) -> List[DownloadResult]:
        """批量下载瓦片（同步接口）
        
        Args:
            tiles: 瓦片信息列表
            
        Returns:
            下载结果列表
        """
        return asyncio.run(self.download_tiles_async(tiles))
    
    async def download_tiles_async(self, tiles: List[TileInfo]) -> List[DownloadResult]:
        """异步批量下载瓦片
        
        Args:
            tiles: 瓦片信息列表
            
        Returns:
            下载结果列表
        """
        total_tiles = len(tiles)
        self.logger.info(f"开始异步下载 {total_tiles} 个瓦片，最大并发数: {self.config.download.max_concurrency}")
        self.monitor.update_stats('total_downloads', total_tiles)
        
        # 确保会话存在
        await self._ensure_session()
        
        # 创建下载任务
        tasks = []
        for tile_info in tiles:
            task = asyncio.create_task(self.download_tile_async(tile_info))
            tasks.append(task)
        
        # 执行下载并收集结果
        results = []
        completed_count = 0
        
        try:
            # 使用as_completed来获取完成的任务
            for coro in asyncio.as_completed(tasks):
                try:
                    result = await coro
                    results.append(result)
                    completed_count += 1
                    
                    # 记录进度
                    if completed_count % 50 == 0 or completed_count == total_tiles:
                        success_count = sum(1 for r in results if r.success)
                        self.logger.info(
                            f"下载进度: {completed_count}/{total_tiles} "
                            f"(成功: {success_count}, 失败: {completed_count - success_count})"
                        )
                    
                    # 更新性能监控
                    if completed_count % 10 == 0:
                        self.monitor.record_performance()
                        
                except Exception as e:
                    self.logger.error(f"下载任务异常: {str(e)}")
                    # 创建失败结果
                    results.append(DownloadResult(
                        tile_info=TileInfo(0, 0, 0, "", ""),  # 占位符
                        success=False,
                        error=str(e)
                    ))
                    completed_count += 1
        
        except KeyboardInterrupt:
            self.logger.warning("用户中断下载，正在取消剩余任务...")
            # 取消未完成的任务
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # 等待所有任务完成或取消
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count
        
        self.logger.info(
            f"异步下载完成: 总计 {len(results)}, 成功 {success_count}, 失败 {failure_count}"
        )
        
        return results
    
    async def download_tiles_batch(self, tiles: List[TileInfo], batch_size: int = 100) -> List[DownloadResult]:
        """分批异步下载瓦片
        
        Args:
            tiles: 瓦片信息列表
            batch_size: 批次大小
            
        Returns:
            下载结果列表
        """
        total_tiles = len(tiles)
        all_results = []
        
        self.logger.info(f"开始分批下载 {total_tiles} 个瓦片，批次大小: {batch_size}")
        
        # 分批处理
        for i in range(0, total_tiles, batch_size):
            batch = tiles[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_tiles + batch_size - 1) // batch_size
            
            self.logger.info(f"处理批次 {batch_num}/{total_batches} ({len(batch)} 个瓦片)")
            
            batch_results = await self.download_tiles_async(batch)
            all_results.extend(batch_results)
            
            # 批次间休息
            if i + batch_size < total_tiles:
                await asyncio.sleep(1.0)
        
        return all_results
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            # 在事件循环中关闭会话
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._close_session())
                else:
                    loop.run_until_complete(self._close_session())
            except RuntimeError:
                # 如果没有事件循环，忽略清理
                pass