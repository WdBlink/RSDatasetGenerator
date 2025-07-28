"""同步下载器模块

实现基于requests的同步瓦片下载功能。
适用于小规模数据下载或网络环境不稳定的情况。
"""

import time
import random
import requests
from typing import List, Optional
from PIL import Image
from io import BytesIO

from .base import BaseDownloader, TileInfo, DownloadResult
from ..utils import DownloadError


class SyncDownloader(BaseDownloader):
    """同步下载器
    
    使用requests库实现的同步瓦片下载器。
    特点：
    - 简单可靠
    - 内置重试机制
    - 适合小规模下载
    - 网络异常处理完善
    """
    
    def __init__(self, config):
        """初始化同步下载器
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        
        # 创建requests会话
        self.session = requests.Session()
        self.session.headers.update(self.config.network.headers)
        
        # 设置代理（如果配置了）
        if self.config.network.use_proxy and self.config.network.proxy_url:
            self.session.proxies = {
                'http': self.config.network.proxy_url,
                'https': self.config.network.proxy_url
            }
        
        self.logger.info("同步下载器初始化完成")
    
    def download_tile(self, tile_info: TileInfo) -> DownloadResult:
        """下载单个瓦片
        
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
        
        # 尝试下载
        for attempt in range(self.config.download.max_retries + 1):
            try:
                result = self._download_with_retry(tile_info, attempt)
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
                    time.sleep(total_wait)
        
        # 所有重试都失败
        self.monitor.update_stats('failed_downloads')
        return DownloadResult(
            tile_info=tile_info,
            success=False,
            error=f"下载失败，已重试 {self.config.download.max_retries} 次",
            download_time=time.time() - start_time
        )
    
    def _download_with_retry(self, tile_info: TileInfo, attempt: int) -> DownloadResult:
        """执行单次下载尝试
        
        Args:
            tile_info: 瓦片信息
            attempt: 尝试次数
            
        Returns:
            下载结果
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            # 添加随机延迟
            if attempt > 0:
                self.add_random_delay()
            
            # 发送请求
            response = self.session.get(
                tile_info.url,
                timeout=self.config.download.request_timeout,
                stream=True
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise DownloadError(f"响应不是图像类型: {content_type}")
            
            # 读取图像数据
            image_data = response.content
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
            
        except requests.exceptions.Timeout:
            raise DownloadError("请求超时")
        except requests.exceptions.ConnectionError:
            raise DownloadError("连接错误")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise DownloadError("瓦片不存在 (404)")
            elif e.response.status_code == 429:
                raise DownloadError("请求过于频繁 (429)")
            elif e.response.status_code >= 500:
                raise DownloadError(f"服务器错误 ({e.response.status_code})")
            else:
                raise DownloadError(f"HTTP错误 ({e.response.status_code})")
        except Exception as e:
            raise DownloadError(f"未知错误: {str(e)}")
    
    def download_tiles(self, tiles: List[TileInfo]) -> List[DownloadResult]:
        """批量下载瓦片
        
        Args:
            tiles: 瓦片信息列表
            
        Returns:
            下载结果列表
        """
        results = []
        total_tiles = len(tiles)
        
        self.logger.info(f"开始下载 {total_tiles} 个瓦片")
        self.monitor.update_stats('total_downloads', total_tiles)
        
        for i, tile_info in enumerate(tiles, 1):
            try:
                result = self.download_tile(tile_info)
                results.append(result)
                
                # 记录进度
                if i % 10 == 0 or i == total_tiles:
                    success_count = sum(1 for r in results if r.success)
                    self.logger.info(
                        f"下载进度: {i}/{total_tiles} "
                        f"(成功: {success_count}, 失败: {i - success_count})"
                    )
                
                # 更新性能监控
                self.monitor.record_performance()
                
                # 添加请求间隔
                if i < total_tiles:  # 最后一个请求不需要延迟
                    self.add_random_delay()
                    
            except KeyboardInterrupt:
                self.logger.warning("用户中断下载")
                break
            except Exception as e:
                self.logger.error(f"下载瓦片时发生未预期错误: {str(e)}")
                results.append(DownloadResult(
                    tile_info=tile_info,
                    success=False,
                    error=str(e)
                ))
        
        # 统计结果
        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count
        
        self.logger.info(
            f"下载完成: 总计 {len(results)}, 成功 {success_count}, 失败 {failure_count}"
        )
        
        return results
    
    def __del__(self):
        """析构函数，关闭会话"""
        if hasattr(self, 'session'):
            self.session.close()