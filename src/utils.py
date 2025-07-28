"""工具模块

提供日志管理、异常处理、性能监控等通用功能。
"""

import os
import sys
import time
import logging
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import deque
from pathlib import Path
from contextlib import contextmanager


class RSDatasetGeneratorError(Exception):
    """RSDatasetGenerator基础异常类"""
    pass


class ConfigurationError(RSDatasetGeneratorError):
    """配置错误异常"""
    pass


class DownloadError(RSDatasetGeneratorError):
    """下载错误异常"""
    pass


class ProcessingError(RSDatasetGeneratorError):
    """数据处理错误异常"""
    pass


class ValidationError(RSDatasetGeneratorError):
    """数据验证错误异常"""
    pass


class DataProcessingError(RSDatasetGeneratorError):
    """数据处理错误异常"""
    pass


class Logger:
    """日志管理器
    
    提供统一的日志管理功能，支持文件和控制台输出。
    """
    
    def __init__(self, name: str = "RSDatasetGenerator", level: str = "INFO", 
                 log_file: str = None, console_output: bool = True, 
                 file_output: bool = True, log_dir: str = "./logs"):
        """初始化日志管理器
        
        Args:
            name: 日志器名称
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: 指定的日志文件路径
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            log_dir: 日志文件存储目录（当log_file未指定时使用）
        """
        self.name = name
        self.level = getattr(logging, level.upper(), logging.INFO)
        self.console_output = console_output
        self.file_output = file_output
        
        # 设置日志文件路径
        if log_file:
            self.log_file = Path(log_file)
            # 确保日志文件目录存在
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.log_dir = Path(log_dir)
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = self.log_dir / f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.level)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """设置日志处理器"""
        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 文件处理器
        if self.file_output:
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        # 控制台处理器
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str, *args, **kwargs) -> None:
        """记录调试信息"""
        self.logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs) -> None:
        """记录一般信息"""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs) -> None:
        """记录警告信息"""
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs) -> None:
        """记录错误信息"""
        self.logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs) -> None:
        """记录严重错误信息"""
        self.logger.critical(message, *args, **kwargs)
    
    @contextmanager
    def log_execution_time(self, operation: str):
        """记录操作执行时间的上下文管理器
        
        Args:
            operation: 操作描述
        """
        start_time = time.time()
        self.info(f"开始执行: {operation}")
        try:
            yield
        except Exception as e:
            self.error(f"执行失败: {operation}, 错误: {str(e)}")
            raise
        else:
            elapsed = time.time() - start_time
            self.info(f"执行完成: {operation}, 耗时: {elapsed:.2f}秒")


class PerformanceMonitor:
    """性能监控器
    
    监控系统资源使用情况和任务执行统计。
    """
    
    def __init__(self, max_samples: int = 100):
        """初始化性能监控器
        
        Args:
            max_samples: 最大采样数量
        """
        self.start_time = time.monotonic()
        self.max_samples = max_samples
        
        # 统计数据
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_bytes': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # 性能采样
        self.memory_samples = deque(maxlen=max_samples)
        self.cpu_samples = deque(maxlen=max_samples)
        self.speed_samples = deque(maxlen=max_samples)
        
        # 当前进程
        self.process = psutil.Process(os.getpid())
    
    def update_stats(self, key: str, value: int = 1) -> None:
        """更新统计数据
        
        Args:
            key: 统计项名称
            value: 增加的数值
        """
        if key in self.stats:
            self.stats[key] += value
        else:
            raise ValueError(f"未知的统计项: {key}")
    
    def record_performance(self) -> None:
        """记录当前性能指标"""
        try:
            # 内存使用（MB）
            memory_mb = self.process.memory_info().rss / (1024 * 1024)
            self.memory_samples.append(memory_mb)
            
            # CPU使用率
            cpu_percent = self.process.cpu_percent()
            self.cpu_samples.append(cpu_percent)
            
            # 下载速度（任务/秒）
            elapsed = max(time.monotonic() - self.start_time, 1)
            speed = self.stats['completed_tasks'] / elapsed
            self.speed_samples.append(speed)
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 进程可能已经结束或无权限访问
            pass
    
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前统计信息
        
        Returns:
            包含各项统计数据的字典
        """
        elapsed = time.monotonic() - self.start_time
        
        # 计算平均值和峰值
        avg_memory = sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0
        peak_memory = max(self.memory_samples) if self.memory_samples else 0
        avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        current_speed = self.speed_samples[-1] if self.speed_samples else 0
        
        return {
            'elapsed_time': elapsed,
            'total_tasks': self.stats['total_tasks'],
            'completed_tasks': self.stats['completed_tasks'],
            'failed_tasks': self.stats['failed_tasks'],
            'success_rate': (self.stats['completed_tasks'] / max(self.stats['total_tasks'], 1)) * 100,
            'download_success_rate': (self.stats['successful_downloads'] / max(self.stats['total_downloads'], 1)) * 100,
            'total_bytes_mb': self.stats['total_bytes'] / (1024 * 1024),
            'cache_hit_rate': (self.stats['cache_hits'] / max(self.stats['cache_hits'] + self.stats['cache_misses'], 1)) * 100,
            'avg_memory_mb': avg_memory,
            'peak_memory_mb': peak_memory,
            'avg_cpu_percent': avg_cpu,
            'current_speed_tasks_per_sec': current_speed,
            'avg_speed_tasks_per_sec': self.stats['completed_tasks'] / max(elapsed, 1)
        }
    
    def generate_report(self) -> str:
        """生成性能报告
        
        Returns:
            格式化的性能报告字符串
        """
        stats = self.get_current_stats()
        
        report = [
            "\n" + "=" * 60,
            "性能监控报告",
            "=" * 60,
            f"运行时间: {stats['elapsed_time']:.1f}秒",
            f"任务统计: {stats['completed_tasks']}/{stats['total_tasks']} (成功率: {stats['success_rate']:.1f}%)",
            f"下载统计: {stats['successful_downloads']}/{stats['total_downloads']} (成功率: {stats['download_success_rate']:.1f}%)",
            f"数据传输: {stats['total_bytes_mb']:.1f}MB",
            f"缓存命中率: {stats['cache_hit_rate']:.1f}%",
            f"内存使用: 当前 {stats['avg_memory_mb']:.1f}MB, 峰值 {stats['peak_memory_mb']:.1f}MB",
            f"CPU使用: 平均 {stats['avg_cpu_percent']:.1f}%",
            f"处理速度: 当前 {stats['current_speed_tasks_per_sec']:.2f} 任务/秒, 平均 {stats['avg_speed_tasks_per_sec']:.2f} 任务/秒",
            "=" * 60
        ]
        
        return "\n".join(report)
    
    def reset(self) -> None:
        """重置监控数据"""
        self.start_time = time.monotonic()
        self.stats = {key: 0 for key in self.stats}
        self.memory_samples.clear()
        self.cpu_samples.clear()
        self.speed_samples.clear()


class ProgressReporter:
    """进度报告器
    
    提供任务进度的实时报告功能。
    """
    
    def __init__(self, logger, report_interval: float = 5.0):
        """初始化进度报告器
        
        Args:
            logger: 日志器实例
            report_interval: 报告间隔（秒）
        """
        self.logger = logger
        self.report_interval = report_interval
        self.reset()
    
    def reset(self):
        """重置进度报告器"""
        self.total_tasks = 0
        self.completed_tasks = 0
        self.last_report_time = time.time()
        self.start_time = time.time()
        self.current_task_name = ""
    
    def start_task(self, task_name: str, total_tasks: int) -> None:
        """开始新任务
        
        Args:
            task_name: 任务名称
            total_tasks: 总任务数
        """
        self.current_task_name = task_name
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.start_time = time.time()
        self.last_report_time = self.start_time
        self.logger.info(f"开始{task_name}: 总计 {total_tasks} 个任务")
    
    def update_progress(self, completed: int) -> None:
        """更新进度
        
        Args:
            completed: 已完成的任务数
        """
        self.completed_tasks = completed
        
        current_time = time.time()
        if current_time - self.last_report_time >= self.report_interval:
            self._report_progress()
            self.last_report_time = current_time
    
    def update(self, increment: int = 1) -> None:
        """增量更新进度
        
        Args:
            increment: 增加的任务数
        """
        self.completed_tasks += increment
        
        current_time = time.time()
        if current_time - self.last_report_time >= self.report_interval:
            self._report_progress()
            self.last_report_time = current_time
    
    def _report_progress(self) -> None:
        """报告当前进度"""
        elapsed = time.time() - self.start_time
        progress_percent = (self.completed_tasks / self.total_tasks) * 100
        speed = self.completed_tasks / max(elapsed, 1)
        
        if self.completed_tasks > 0:
            eta = (self.total_tasks - self.completed_tasks) / speed
            eta_str = f", 预计剩余: {eta:.0f}秒"
        else:
            eta_str = ""
        
        self.logger.info(
            f"进度: {self.completed_tasks}/{self.total_tasks} "
            f"({progress_percent:.1f}%), "
            f"速度: {speed:.2f} 任务/秒{eta_str}"
        )
    
    def finish_task(self) -> None:
        """完成当前任务"""
        elapsed = time.time() - self.start_time
        avg_speed = self.completed_tasks / max(elapsed, 1)
        
        self.logger.info(
            f"{self.current_task_name}完成! 总计: {self.completed_tasks}/{self.total_tasks}, "
            f"耗时: {elapsed:.1f}秒, "
            f"平均速度: {avg_speed:.2f} 任务/秒"
        )
    
    def finish(self) -> None:
        """完成进度报告（向后兼容）"""
        self.finish_task()


def validate_shapefile(shapefile_path: str) -> None:
    """验证Shapefile文件的完整性和格式
    
    Args:
        shapefile_path: Shapefile路径
        
    Raises:
        ValidationError: 文件验证失败
    """
    if not os.path.exists(shapefile_path):
        raise ValidationError(f"Shapefile不存在: {shapefile_path}")
    
    # 检查必要的文件
    base_path = os.path.splitext(shapefile_path)[0]
    required_extensions = ['.shp', '.shx', '.dbf']
    
    for ext in required_extensions:
        file_path = f"{base_path}{ext}"
        if not os.path.exists(file_path):
            raise ValidationError(f"缺少Shapefile必要文件: {file_path}")
    
    # 验证文件可读性
    try:
        import geopandas as gpd
        gdf = gpd.read_file(shapefile_path)
        
        # 检查必要字段
        if 'osm_id' not in gdf.columns:
            raise ValidationError("Shapefile必须包含'osm_id'字段")
        
        # 检查几何类型
        from shapely.geometry import Point
        if not all(isinstance(geom, Point) for geom in gdf.geometry):
            raise ValidationError("Shapefile必须包含点要素")
        
        # 检查坐标系
        if gdf.crs is None:
            raise ValidationError("Shapefile缺少坐标系信息")
            
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(f"Shapefile格式验证失败: {str(e)}")


def ensure_directory(directory: str) -> None:
    """确保目录存在，如果不存在则创建
    
    Args:
        directory: 目录路径
    """
    Path(directory).mkdir(parents=True, exist_ok=True)


def format_bytes(bytes_count: int) -> str:
    """格式化字节数为人类可读格式
    
    Args:
        bytes_count: 字节数
        
    Returns:
        格式化后的字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f}{unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f}PB"


def format_duration(seconds: float) -> str:
    """格式化时间长度为人类可读格式
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化后的字符串
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"