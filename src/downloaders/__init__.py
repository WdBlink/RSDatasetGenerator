"""下载器模块

提供不同的瓦片下载策略实现，支持同步和异步下载。
使用策略模式和工厂模式实现可扩展的下载器架构。
"""

from .base import BaseDownloader, DownloadResult
from .sync_downloader import SyncDownloader
from .async_downloader import AsyncDownloader
from .factory import DownloaderFactory, DownloaderType

__all__ = [
    "BaseDownloader",
    "DownloadResult",
    "SyncDownloader",
    "AsyncDownloader",
    "DownloaderFactory",
    "DownloaderType"
]