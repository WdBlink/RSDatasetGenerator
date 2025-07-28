"""数据处理器主模块

整合数据加载、图像处理和元数据管理功能。
提供统一的数据处理接口。
"""

import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .data_loader import DataLoader, GeoPoint
from .image_processor import ImageProcessor, ImageMetadata
from .metadata_manager import MetadataManager, ProcessingStats
from ..downloaders.base import TileInfo
from ..downloaders.factory import DownloaderFactory
from ..utils import DataProcessingError, ProgressReporter, ensure_directory


class DataProcessor:
    """数据处理器
    
    负责整个数据处理流程的协调和管理。
    包括数据加载、瓦片下载、图像处理和元数据管理。
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = config.logger
        
        # 初始化组件
        self.data_loader = DataLoader
        self.image_processor = ImageProcessor(config)
        self.metadata_manager = MetadataManager(config)
        self.downloader = None
        
        # 处理统计
        self.stats = {
            'total_points': 0,
            'successful_points': 0,
            'failed_points': 0,
            'total_tiles': 0,
            'successful_tiles': 0,
            'failed_tiles': 0,
            'start_time': None,
            'end_time': None
        }
        
        # 进度报告器
        self.progress_reporter = ProgressReporter(config.logger)
    
    def process_dataset(self, input_file: str) -> Dict[str, Any]:
        """处理整个数据集
        
        Args:
            input_file: 输入文件路径
            
        Returns:
            处理结果摘要
        """
        self.logger.info(f"开始处理数据集: {input_file}")
        self.stats['start_time'] = datetime.now()
        
        try:
            # 1. 加载地理点数据
            points = self._load_points(input_file)
            self.stats['total_points'] = len(points)
            
            # 2. 创建下载器
            self.downloader = DownloaderFactory.create_downloader(self.config)
            
            # 3. 确保输出目录存在
            ensure_directory(self.config.paths.output_dir)
            
            # 4. 处理每个点
            image_metadatas = self._process_points(points)
            
            # 5. 生成数据集摘要和报告
            summary = self._generate_summary(points, image_metadatas)
            
            self.logger.info("数据集处理完成")
            return summary
            
        except Exception as e:
            self.logger.error(f"数据集处理失败: {str(e)}")
            raise DataProcessingError(f"数据集处理失败: {str(e)}")
        
        finally:
            self.stats['end_time'] = datetime.now()
            if self.downloader:
                # 清理下载器资源
                if hasattr(self.downloader, '__del__'):
                    del self.downloader
    
    def _load_points(self, input_file: str) -> List[GeoPoint]:
        """加载地理点数据
        
        Args:
            input_file: 输入文件路径
            
        Returns:
            地理点列表
        """
        self.logger.info("加载地理点数据...")
        
        try:
            points = self.data_loader.load_points(input_file, self.config)
            
            if not points:
                raise DataProcessingError("没有找到有效的地理点数据")
            
            self.logger.info(f"成功加载 {len(points)} 个地理点")
            
            # 验证点的有效性
            valid_points = []
            for point in points:
                if point.validate():
                    valid_points.append(point)
                else:
                    self.logger.warning(
                        f"跳过无效坐标点: ({point.longitude}, {point.latitude})"
                    )
            
            if len(valid_points) != len(points):
                self.logger.warning(
                    f"过滤掉 {len(points) - len(valid_points)} 个无效坐标点"
                )
            
            return valid_points
            
        except Exception as e:
            raise DataProcessingError(f"加载地理点数据失败: {str(e)}")
    
    def _process_points(self, points: List[GeoPoint]) -> List[ImageMetadata]:
        """处理所有地理点
        
        Args:
            points: 地理点列表
            
        Returns:
            图像元数据列表
        """
        total_points = len(points)
        self.logger.info(f"开始处理 {total_points} 个地理点")
        
        image_metadatas = []
        
        # 初始化进度报告
        self.progress_reporter.start_task("处理地理点", total_points)
        
        for i, point in enumerate(points):
            try:
                # 处理单个点
                image_metadata = self._process_single_point(point, i)
                
                if image_metadata:
                    image_metadatas.append(image_metadata)
                    self.stats['successful_points'] += 1
                else:
                    self.stats['failed_points'] += 1
                
                # 更新进度
                self.progress_reporter.update_progress(i + 1)
                
                # 定期报告进度
                if (i + 1) % 10 == 0 or (i + 1) == total_points:
                    success_rate = self.stats['successful_points'] / (i + 1) * 100
                    self.logger.info(
                        f"处理进度: {i + 1}/{total_points} "
                        f"(成功率: {success_rate:.1f}%)"
                    )
                
            except Exception as e:
                self.logger.error(f"处理点 {i} 失败: {str(e)}")
                self.stats['failed_points'] += 1
                continue
        
        self.progress_reporter.finish_task()
        
        self.logger.info(
            f"点处理完成: 成功 {self.stats['successful_points']}, "
            f"失败 {self.stats['failed_points']}"
        )
        
        return image_metadatas
    
    def _process_single_point(self, point: GeoPoint, point_index: int) -> Optional[ImageMetadata]:
        """处理单个地理点
        
        Args:
            point: 地理点
            point_index: 点索引
            
        Returns:
            图像元数据，如果处理失败则返回None
        """
        try:
            self.logger.debug(f"处理点 {point_index}: ({point.longitude}, {point.latitude})")
            
            # 1. 计算需要下载的瓦片
            tiles = self._calculate_tiles_for_point(point)
            self.stats['total_tiles'] += len(tiles)
            
            # 2. 下载瓦片
            download_results = self._download_tiles(tiles)
            
            # 3. 统计下载结果
            successful_downloads = sum(1 for r in download_results if r.success)
            failed_downloads = len(download_results) - successful_downloads
            
            self.stats['successful_tiles'] += successful_downloads
            self.stats['failed_tiles'] += failed_downloads
            
            # 4. 检查是否有足够的瓦片进行处理
            if successful_downloads == 0:
                self.logger.warning(f"点 {point_index} 没有成功下载任何瓦片")
                return None
            
            # 5. 处理图像
            image, metadata = self.image_processor.process_point_image(
                point, download_results, 
                self.config.download.zoom_level,
                self.config.download.grid_size
            )
            
            # 6. 保存图像
            image_path = self._save_image(image, point_index)
            
            # 7. 保存元数据
            metadata_path = self.metadata_manager.save_image_metadata(
                metadata, point_index, 'json'
            )
            
            self.logger.debug(
                f"点 {point_index} 处理完成: 图像={image_path}, 元数据={metadata_path}"
            )
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"处理点 {point_index} 时出错: {str(e)}")
            return None
    
    def _calculate_tiles_for_point(self, point: GeoPoint) -> List[TileInfo]:
        """计算点周围需要下载的瓦片
        
        Args:
            point: 地理点
            
        Returns:
            瓦片信息列表
        """
        # 使用下载器的瓦片计算方法
        return self.downloader.calculate_tiles_around_point(
            point.longitude, point.latitude,
            self.config.download.zoom_level,
            self.config.download.grid_size
        )
    
    def _download_tiles(self, tiles: List[TileInfo]) -> List:
        """下载瓦片
        
        Args:
            tiles: 瓦片信息列表
            
        Returns:
            下载结果列表
        """
        return self.downloader.download_tiles(tiles)
    
    def _save_image(self, image, point_index: int) -> str:
        """保存图像
        
        Args:
            image: PIL图像对象
            point_index: 点索引
            
        Returns:
            保存的文件路径
        """
        filename = f"point_{point_index:06d}.png"
        file_path = Path(self.config.paths.output_dir) / filename
        
        try:
            image.save(file_path, 'PNG', optimize=True)
            return str(file_path)
        except Exception as e:
            raise DataProcessingError(f"保存图像失败: {str(e)}")
    
    def _generate_summary(self, points: List[GeoPoint], 
                         image_metadatas: List[ImageMetadata]) -> Dict[str, Any]:
        """生成处理摘要
        
        Args:
            points: 地理点列表
            image_metadatas: 图像元数据列表
            
        Returns:
            处理摘要
        """
        # 计算处理时间
        if self.stats['start_time'] and self.stats['end_time']:
            processing_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        else:
            processing_time = 0.0
        
        # 创建处理统计
        processing_stats = ProcessingStats(
            total_points=self.stats['total_points'],
            successful_points=self.stats['successful_points'],
            failed_points=self.stats['failed_points'],
            total_tiles=self.stats['total_tiles'],
            successful_tiles=self.stats['successful_tiles'],
            failed_tiles=self.stats['failed_tiles'],
            processing_time=processing_time,
            start_time=self.stats['start_time'].isoformat() if self.stats['start_time'] else '',
            end_time=self.stats['end_time'].isoformat() if self.stats['end_time'] else ''
        )
        
        # 创建配置快照
        config_snapshot = {
            'input_file': getattr(self.config.paths, 'input_file', ''),
            'output_dir': self.config.paths.output_dir,
            'zoom_level': self.config.download.zoom_level,
            'grid_size': self.config.download.grid_size,
            'max_concurrency': self.config.download.max_concurrency,
            'downloader_type': getattr(self.config.download, 'downloader_type', 'auto'),
            'tile_cache_enabled': self.config.download.enable_cache,
            'max_retries': self.config.download.max_retries
        }
        
        # 创建数据集元数据
        dataset_metadata = self.metadata_manager.create_dataset_summary(
            points, processing_stats, config_snapshot
        )
        
        # 保存各种输出文件
        summary_files = {}
        
        try:
            # 保存数据集摘要
            summary_files['dataset_summary'] = self.metadata_manager.save_dataset_summary(
                dataset_metadata
            )
            
            # 创建坐标映射文件
            if image_metadatas:
                summary_files['coordinate_mapping'] = self.metadata_manager.create_coordinate_mapping(
                    image_metadatas
                )
                
                # 导出CSV文件
                summary_files['csv_export'] = self.metadata_manager.export_to_csv(
                    image_metadatas
                )
            
            # 创建处理报告
            summary_files['processing_report'] = self.metadata_manager.create_processing_report(
                processing_stats, config_snapshot
            )
            
        except Exception as e:
            self.logger.warning(f"生成摘要文件时出错: {str(e)}")
        
        # 清理临时文件
        try:
            keep_cache = getattr(self.config.download, 'keep_cache', False)
            self.metadata_manager.cleanup_temp_files(keep_cache)
        except Exception as e:
            self.logger.warning(f"清理临时文件时出错: {str(e)}")
        
        # 返回摘要
        return {
            'dataset_metadata': dataset_metadata.to_dict(),
            'processing_stats': {
                'total_points': processing_stats.total_points,
                'successful_points': processing_stats.successful_points,
                'failed_points': processing_stats.failed_points,
                'success_rate': processing_stats.success_rate(),
                'total_tiles': processing_stats.total_tiles,
                'successful_tiles': processing_stats.successful_tiles,
                'failed_tiles': processing_stats.failed_tiles,
                'tile_success_rate': processing_stats.tile_success_rate(),
                'processing_time': processing_stats.processing_time
            },
            'output_files': {
                'images_count': len(image_metadatas),
                'output_directory': self.config.paths.output_dir,
                'summary_files': summary_files
            }
        }
    
    def validate_input(self, input_file: str) -> bool:
        """验证输入文件
        
        Args:
            input_file: 输入文件路径
            
        Returns:
            文件是否有效
        """
        try:
            loader = self.data_loader.create_loader(input_file, self.config)
            return loader.validate_file(input_file)
        except Exception as e:
            self.logger.error(f"验证输入文件失败: {str(e)}")
            return False
    
    def estimate_processing_time(self, input_file: str) -> Dict[str, Any]:
        """估算处理时间
        
        Args:
            input_file: 输入文件路径
            
        Returns:
            时间估算信息
        """
        try:
            # 加载点数据
            points = self.data_loader.load_points(input_file, self.config)
            total_points = len(points)
            
            # 计算总瓦片数
            tiles_per_point = self.config.download.grid_size ** 2
            total_tiles = total_points * tiles_per_point
            
            # 估算时间（基于经验值）
            # 同步下载: ~0.5秒/瓦片, 异步下载: ~0.1秒/瓦片
            downloader_type = getattr(self.config.download, 'downloader_type', 'auto')
            if downloader_type == 'sync':
                estimated_seconds_per_tile = 0.5
            else:
                estimated_seconds_per_tile = 0.1
            
            estimated_download_time = total_tiles * estimated_seconds_per_tile
            estimated_processing_time = total_points * 0.1  # 图像处理时间
            estimated_total_time = estimated_download_time + estimated_processing_time
            
            return {
                'total_points': total_points,
                'total_tiles': total_tiles,
                'estimated_download_time': estimated_download_time,
                'estimated_processing_time': estimated_processing_time,
                'estimated_total_time': estimated_total_time,
                'estimated_total_time_formatted': self._format_duration(estimated_total_time)
            }
            
        except Exception as e:
            self.logger.error(f"估算处理时间失败: {str(e)}")
            return {}
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时间长度
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串
        """
        if seconds < 60:
            return f"{seconds:.1f} 秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} 分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} 小时"