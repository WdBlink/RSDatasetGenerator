"""下载器工厂模块

实现下载器的创建和管理。
使用工厂模式根据配置创建合适的下载器实例。
"""

from enum import Enum
from typing import Type, Dict

from .base import BaseDownloader
from .sync_downloader import SyncDownloader
from .async_downloader import AsyncDownloader
from ..utils import ConfigurationError


class DownloaderType(Enum):
    """下载器类型枚举"""
    SYNC = "sync"
    ASYNC = "async"
    AUTO = "auto"


class DownloaderFactory:
    """下载器工厂
    
    负责根据配置创建合适的下载器实例。
    支持同步和异步两种下载器类型。
    """
    
    # 下载器类型映射
    _downloaders: Dict[DownloaderType, Type[BaseDownloader]] = {
        DownloaderType.SYNC: SyncDownloader,
        DownloaderType.ASYNC: AsyncDownloader,
    }
    
    @classmethod
    def create_downloader(cls, config, downloader_type: DownloaderType = None) -> BaseDownloader:
        """创建下载器实例
        
        Args:
            config: 配置对象
            downloader_type: 下载器类型，如果为None则从配置中获取
            
        Returns:
            下载器实例
            
        Raises:
            ConfigurationError: 配置错误
        """
        # 确定下载器类型
        if downloader_type is None:
            downloader_type = cls._get_downloader_type_from_config(config)
        
        # 自动选择下载器类型
        if downloader_type == DownloaderType.AUTO:
            downloader_type = cls._auto_select_downloader_type(config)
        
        # 获取下载器类
        downloader_class = cls._downloaders.get(downloader_type)
        if downloader_class is None:
            raise ConfigurationError(f"不支持的下载器类型: {downloader_type}")
        
        # 创建下载器实例
        try:
            downloader = downloader_class(config)
            config.logger.info(f"创建下载器: {downloader_class.__name__}")
            return downloader
        except Exception as e:
            raise ConfigurationError(f"创建下载器失败: {str(e)}")
    
    @classmethod
    def _get_downloader_type_from_config(cls, config) -> DownloaderType:
        """从配置中获取下载器类型
        
        Args:
            config: 配置对象
            
        Returns:
            下载器类型
        """
        downloader_type_str = getattr(config.download, 'downloader_type', 'auto')
        
        try:
            return DownloaderType(downloader_type_str.lower())
        except ValueError:
            config.logger.warning(
                f"无效的下载器类型配置: {downloader_type_str}，使用自动选择"
            )
            return DownloaderType.AUTO
    
    @classmethod
    def _auto_select_downloader_type(cls, config) -> DownloaderType:
        """自动选择下载器类型
        
        根据配置参数自动选择最合适的下载器类型。
        
        Args:
            config: 配置对象
            
        Returns:
            下载器类型
        """
        # 获取相关配置参数
        max_concurrency = getattr(config.download, 'max_concurrency', 1)
        expected_tiles = getattr(config.download, 'expected_tiles', 0)
        
        # 决策逻辑
        if max_concurrency <= 1:
            # 单线程，使用同步下载器
            selected_type = DownloaderType.SYNC
            reason = "单线程配置"
        elif expected_tiles < 100:
            # 小规模下载，使用同步下载器
            selected_type = DownloaderType.SYNC
            reason = "小规模下载"
        else:
            # 大规模下载或高并发，使用异步下载器
            selected_type = DownloaderType.ASYNC
            reason = "大规模下载或高并发"
        
        config.logger.info(
            f"自动选择下载器类型: {selected_type.value} (原因: {reason}, "
            f"并发数: {max_concurrency}, 预期瓦片数: {expected_tiles})"
        )
        
        return selected_type
    
    @classmethod
    def get_available_types(cls) -> list:
        """获取可用的下载器类型
        
        Returns:
            可用的下载器类型列表
        """
        return list(cls._downloaders.keys())
    
    @classmethod
    def register_downloader(cls, downloader_type: DownloaderType, downloader_class: Type[BaseDownloader]):
        """注册新的下载器类型
        
        Args:
            downloader_type: 下载器类型
            downloader_class: 下载器类
        """
        if not issubclass(downloader_class, BaseDownloader):
            raise ValueError(f"下载器类必须继承自BaseDownloader: {downloader_class}")
        
        cls._downloaders[downloader_type] = downloader_class
    
    @classmethod
    def get_downloader_info(cls, downloader_type: DownloaderType) -> dict:
        """获取下载器信息
        
        Args:
            downloader_type: 下载器类型
            
        Returns:
            下载器信息字典
        """
        downloader_class = cls._downloaders.get(downloader_type)
        if downloader_class is None:
            return {}
        
        return {
            'type': downloader_type.value,
            'class_name': downloader_class.__name__,
            'module': downloader_class.__module__,
            'description': downloader_class.__doc__ or "无描述"
        }
    
    @classmethod
    def validate_downloader_config(cls, config, downloader_type: DownloaderType = None) -> bool:
        """验证下载器配置
        
        Args:
            config: 配置对象
            downloader_type: 下载器类型
            
        Returns:
            配置是否有效
        """
        try:
            if downloader_type is None:
                downloader_type = cls._get_downloader_type_from_config(config)
            
            if downloader_type == DownloaderType.AUTO:
                downloader_type = cls._auto_select_downloader_type(config)
            
            downloader_class = cls._downloaders.get(downloader_type)
            if downloader_class is None:
                return False
            
            # 检查必要的配置项
            required_attrs = [
                'download.max_retries',
                'download.request_timeout',
                'download.request_interval_range',
                'download.retry_wait_range'
            ]
            
            for attr_path in required_attrs:
                obj = config
                for attr in attr_path.split('.'):
                    if not hasattr(obj, attr):
                        config.logger.error(f"缺少必要的配置项: {attr_path}")
                        return False
                    obj = getattr(obj, attr)
            
            # 异步下载器的额外检查
            if downloader_type == DownloaderType.ASYNC:
                if not hasattr(config.download, 'max_concurrency'):
                    config.logger.error("异步下载器需要max_concurrency配置")
                    return False
                
                if config.download.max_concurrency < 1:
                    config.logger.error("max_concurrency必须大于0")
                    return False
            
            return True
            
        except Exception as e:
            config.logger.error(f"验证下载器配置时出错: {str(e)}")
            return False