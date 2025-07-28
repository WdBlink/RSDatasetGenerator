"""遥感数据集生成器主模块

提供统一的API接口，整合所有功能模块。
这是项目的核心入口点。
"""

import os
import sys
from typing import Dict, Any, Optional
from pathlib import Path

from .config import Config
from .processors.data_processor import DataProcessor
from .downloaders.factory import DownloaderFactory, DownloaderType
from .utils import (
    Logger, ConfigurationError, ValidationError, 
    DataProcessingError, DownloadError
)


class RSDatasetGenerator:
    """遥感数据集生成器
    
    这是项目的主要类，提供完整的遥感数据集生成功能。
    支持从矢量文件生成对应的遥感图像数据集。
    
    主要功能：
    - 读取Shapefile/GeoJSON等矢量文件
    - 从Google Maps下载对应区域的遥感瓦片
    - 拼接瓦片生成完整图像
    - 生成像素坐标映射和元数据
    - 支持批量处理和并发下载
    """
    
    def __init__(self, config_file: Optional[str] = None, **kwargs):
        """初始化遥感数据集生成器
        
        Args:
            config_file: 配置文件路径（可选）
            **kwargs: 额外的配置参数
        """
        # 加载配置
        self.config = Config()
        
        if config_file:
            self.config.load_from_file(config_file)
        
        # 应用额外的配置参数
        if kwargs:
            self.config.update_from_dict(kwargs)
        
        # 初始化日志（在验证之前，以便记录错误）
        self.logger = self.config.logger
        
        # 初始化数据处理器
        self.data_processor = None
        
        self.logger.info("遥感数据集生成器初始化完成")
    
    def generate_dataset(self, input_file: str, output_dir: str = None, 
                        **processing_options) -> Dict[str, Any]:
        """生成遥感数据集
        
        Args:
            input_file: 输入矢量文件路径（Shapefile或GeoJSON）
            output_dir: 输出目录路径（可选）
            **processing_options: 处理选项
                - zoom_level: 缩放级别 (默认: 18)
                - grid_size: 网格大小 (默认: 5)
                - max_concurrency: 最大并发数 (默认: 10)
                - downloader_type: 下载器类型 ('sync', 'async', 'auto')
                - enable_cache: 是否启用缓存 (默认: True)
                - add_markers: 是否在图像上添加点标记 (默认: False)
                
        Returns:
            处理结果摘要字典
            
        Raises:
            ValidationError: 输入验证失败
            ConfigurationError: 配置错误
            DataProcessingError: 数据处理失败
        """
        try:
            # 1. 验证输入文件
            self._validate_input_file(input_file)
            
            # 2. 更新配置
            self._update_config_for_processing(input_file, output_dir, processing_options)
            
            # 3. 验证配置
            self.config.validate()
            
            # 4. 验证下载器配置
            self._validate_downloader_config()
            
            # 5. 初始化数据处理器
            self.data_processor = DataProcessor(self.config)
            
            # 6. 估算处理时间
            time_estimate = self.data_processor.estimate_processing_time(input_file)
            if time_estimate:
                self.logger.info(
                    f"预计处理时间: {time_estimate.get('estimated_total_time_formatted', 'N/A')}, "
                    f"总点数: {time_estimate.get('total_points', 0)}, "
                    f"总瓦片数: {time_estimate.get('total_tiles', 0)}"
                )
            
            # 7. 开始处理
            self.logger.info("开始生成遥感数据集...")
            result = self.data_processor.process_dataset(input_file)
            
            # 8. 记录处理结果
            self._log_processing_result(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"生成数据集失败: {str(e)}")
            raise
    
    def validate_input(self, input_file: str) -> bool:
        """验证输入文件
        
        Args:
            input_file: 输入文件路径
            
        Returns:
            文件是否有效
        """
        try:
            return self._validate_input_file(input_file, raise_on_error=False)
        except Exception:
            return False
    
    def get_supported_formats(self) -> list:
        """获取支持的输入文件格式
        
        Returns:
            支持的文件格式列表
        """
        from .processors.data_loader import DataLoader
        return DataLoader.get_supported_formats()
    
    def get_available_downloader_types(self) -> list:
        """获取可用的下载器类型
        
        Returns:
            可用的下载器类型列表
        """
        return [dt.value for dt in DownloaderFactory.get_available_types()]
    
    def estimate_processing_time(self, input_file: str, **options) -> Dict[str, Any]:
        """估算处理时间
        
        Args:
            input_file: 输入文件路径
            **options: 处理选项
            
        Returns:
            时间估算信息
        """
        try:
            # 临时更新配置
            temp_config = self.config.copy() if hasattr(self.config, 'copy') else self.config
            
            if options:
                for key, value in options.items():
                    if hasattr(temp_config.download, key):
                        setattr(temp_config.download, key, value)
            
            # 创建临时数据处理器
            temp_processor = DataProcessor(temp_config)
            
            return temp_processor.estimate_processing_time(input_file)
            
        except Exception as e:
            self.logger.error(f"估算处理时间失败: {str(e)}")
            return {}
    
    def _validate_input_file(self, input_file: str, raise_on_error: bool = True) -> bool:
        """验证输入文件
        
        Args:
            input_file: 输入文件路径
            raise_on_error: 是否在错误时抛出异常
            
        Returns:
            文件是否有效
            
        Raises:
            ValidationError: 文件验证失败（当raise_on_error=True时）
        """
        # 检查文件是否存在
        if not os.path.exists(input_file):
            error_msg = f"输入文件不存在: {input_file}"
            if raise_on_error:
                raise ValidationError(error_msg)
            self.logger.error(error_msg)
            return False
        
        # 检查文件格式
        supported_formats = self.get_supported_formats()
        file_ext = os.path.splitext(input_file)[1].lower()
        
        if file_ext not in supported_formats:
            error_msg = f"不支持的文件格式: {file_ext}，支持的格式: {supported_formats}"
            if raise_on_error:
                raise ValidationError(error_msg)
            self.logger.error(error_msg)
            return False
        
        # 使用数据处理器验证文件内容
        if self.data_processor:
            is_valid = self.data_processor.validate_input(input_file)
            if not is_valid and raise_on_error:
                raise ValidationError(f"输入文件内容验证失败: {input_file}")
            return is_valid
        
        return True
    
    def _update_config_for_processing(self, input_file: str, output_dir: str, 
                                    processing_options: Dict[str, Any]):
        """更新处理配置
        
        Args:
            input_file: 输入文件路径
            output_dir: 输出目录路径
            processing_options: 处理选项
        """
        # 设置输入文件
        self.config.paths.input_shapefile = input_file
        
        # 设置输出目录
        if output_dir:
            self.config.paths.output_dir = output_dir
        elif not hasattr(self.config.paths, 'output_dir') or not self.config.paths.output_dir:
            # 默认输出目录
            input_name = os.path.splitext(os.path.basename(input_file))[0]
            self.config.paths.output_dir = f"output_{input_name}"
        
        # 应用处理选项
        for key, value in processing_options.items():
            if hasattr(self.config.download, key):
                setattr(self.config.download, key, value)
                self.logger.debug(f"设置配置项 {key} = {value}")
            else:
                self.logger.warning(f"未知的配置项: {key}")
        
        # 确保输出目录存在
        os.makedirs(self.config.paths.output_dir, exist_ok=True)
        
        self.logger.info(f"输入文件: {input_file}")
        self.logger.info(f"输出目录: {self.config.paths.output_dir}")
    
    def _validate_downloader_config(self):
        """验证下载器配置
        
        Raises:
            ConfigurationError: 配置验证失败
        """
        try:
            # 获取下载器类型
            downloader_type_str = getattr(self.config.download, 'downloader_type', 'auto')
            
            if downloader_type_str != 'auto':
                try:
                    downloader_type = DownloaderType(downloader_type_str.lower())
                except ValueError:
                    raise ConfigurationError(f"无效的下载器类型: {downloader_type_str}")
            else:
                downloader_type = DownloaderType.AUTO
            
            # 验证下载器配置
            is_valid = DownloaderFactory.validate_downloader_config(self.config, downloader_type)
            
            if not is_valid:
                raise ConfigurationError("下载器配置验证失败")
            
            self.logger.debug("下载器配置验证通过")
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"验证下载器配置时出错: {str(e)}")
    
    def _log_processing_result(self, result: Dict[str, Any]):
        """记录处理结果
        
        Args:
            result: 处理结果
        """
        try:
            stats = result.get('processing_stats', {})
            output_files = result.get('output_files', {})
            
            self.logger.info("=" * 50)
            self.logger.info("数据集生成完成")
            self.logger.info("=" * 50)
            
            # 处理统计
            self.logger.info(f"总点数: {stats.get('total_points', 0)}")
            self.logger.info(f"成功处理: {stats.get('successful_points', 0)}")
            self.logger.info(f"处理失败: {stats.get('failed_points', 0)}")
            self.logger.info(f"成功率: {stats.get('success_rate', 0):.2f}%")
            
            # 瓦片统计
            self.logger.info(f"总瓦片数: {stats.get('total_tiles', 0)}")
            self.logger.info(f"下载成功: {stats.get('successful_tiles', 0)}")
            self.logger.info(f"下载失败: {stats.get('failed_tiles', 0)}")
            self.logger.info(f"下载成功率: {stats.get('tile_success_rate', 0):.2f}%")
            
            # 处理时间
            processing_time = stats.get('processing_time', 0)
            if processing_time > 0:
                self.logger.info(f"处理时间: {processing_time:.2f} 秒")
            
            # 输出文件
            self.logger.info(f"生成图像数: {output_files.get('images_count', 0)}")
            self.logger.info(f"输出目录: {output_files.get('output_directory', '')}")
            
            # 摘要文件
            summary_files = output_files.get('summary_files', {})
            if summary_files:
                self.logger.info("生成的摘要文件:")
                for file_type, file_path in summary_files.items():
                    self.logger.info(f"  - {file_type}: {file_path}")
            
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.warning(f"记录处理结果时出错: {str(e)}")
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取当前配置信息
        
        Returns:
            配置信息字典
        """
        try:
            return {
                'download_config': {
                    'zoom_level': self.config.download.zoom_level,
                    'grid_size': self.config.download.grid_size,
                    'max_concurrency': self.config.download.max_concurrency,
                    'max_retries': self.config.download.max_retries,
                    'request_timeout': self.config.download.request_timeout,
                    'enable_cache': self.config.download.enable_cache,
                    'downloader_type': getattr(self.config.download, 'downloader_type', 'auto')
                },
                'path_config': {
                    'output_dir': getattr(self.config.paths, 'output_dir', ''),
                    'cache_dir': getattr(self.config.paths, 'cache_dir', ''),
                    'log_dir': getattr(self.config.paths, 'log_dir', '')
                },
                'network_config': {
                    'base_url': self.config.network.base_url,
                    'user_agent': self.config.network.headers.get('User-Agent', ''),
                    'timeout': self.config.network.timeout
                }
            }
        except Exception as e:
            self.logger.error(f"获取配置信息失败: {str(e)}")
            return {}
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        # 清理资源
        if self.data_processor:
            del self.data_processor
        
        if hasattr(self, 'logger'):
            self.logger.info("遥感数据集生成器已关闭")


def create_generator(config_file: str = None, **kwargs) -> RSDatasetGenerator:
    """创建遥感数据集生成器实例
    
    这是一个便捷函数，用于快速创建生成器实例。
    
    Args:
        config_file: 配置文件路径
        **kwargs: 额外的配置参数
        
    Returns:
        遥感数据集生成器实例
    """
    return RSDatasetGenerator(config_file, **kwargs)


def quick_generate(input_file: str, output_dir: str = None, **options) -> Dict[str, Any]:
    """快速生成遥感数据集
    
    这是一个便捷函数，用于快速生成数据集而无需手动管理生成器实例。
    
    Args:
        input_file: 输入矢量文件路径
        output_dir: 输出目录路径
        **options: 处理选项
        
    Returns:
        处理结果摘要
    """
    with create_generator(**options) as generator:
        return generator.generate_dataset(input_file, output_dir, **options)