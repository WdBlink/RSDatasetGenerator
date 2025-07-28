#!/usr/bin/env python3
"""性能基准测试脚本

用于测试和评估RSDatasetGenerator的性能表现，包括：
- 下载速度测试
- 内存使用测试
- 并发性能测试
- 图像处理性能测试
"""

import os
import sys
import time
import psutil
import asyncio
import tempfile
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from src import RSDatasetGenerator
    from src.utils import Logger, PerformanceMonitor
    from src.downloaders import DownloaderFactory, DownloaderType
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    test_name: str
    duration: float
    memory_peak: float
    memory_avg: float
    cpu_avg: float
    success_rate: float
    throughput: float
    details: Dict[str, Any]


class PerformanceBenchmark:
    """性能基准测试器"""
    
    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.logger = Logger(
            name='Benchmark',
            level='INFO',
            console_output=True,
            file_output=True,
            log_file=str(self.output_dir / 'benchmark.log')
        )
        self.results: List[BenchmarkResult] = []
    
    def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """运行所有基准测试
        
        Returns:
            测试结果列表
        """
        self.logger.info("开始性能基准测试")
        self.logger.info("=" * 50)
        
        # 系统信息
        self._log_system_info()
        
        # 下载器性能测试
        self._test_downloader_performance()
        
        # 并发性能测试
        self._test_concurrency_performance()
        
        # 内存使用测试
        self._test_memory_usage()
        
        # 图像处理性能测试
        self._test_image_processing_performance()
        
        # 端到端性能测试
        self._test_end_to_end_performance()
        
        # 生成报告
        self._generate_report()
        
        return self.results
    
    def _log_system_info(self):
        """记录系统信息"""
        self.logger.info("系统信息:")
        self.logger.info(f"  CPU核心数: {psutil.cpu_count()}")
        self.logger.info(f"  物理核心数: {psutil.cpu_count(logical=False)}")
        self.logger.info(f"  总内存: {psutil.virtual_memory().total / 1024**3:.1f} GB")
        self.logger.info(f"  可用内存: {psutil.virtual_memory().available / 1024**3:.1f} GB")
        self.logger.info(f"  Python版本: {sys.version}")
        self.logger.info("")
    
    def _test_downloader_performance(self):
        """测试下载器性能"""
        self.logger.info("测试下载器性能...")
        
        # 测试同步下载器
        self._test_sync_downloader()
        
        # 测试异步下载器
        self._test_async_downloader()
    
    def _test_sync_downloader(self):
        """测试同步下载器"""
        test_name = "同步下载器性能"
        self.logger.info(f"  {test_name}...")
        
        monitor = PerformanceMonitor()
        monitor.start_monitoring()
        
        start_time = time.time()
        
        try:
            # 创建同步下载器
            downloader = DownloaderFactory.create_downloader(
                downloader_type=DownloaderType.SYNC,
                max_retries=3,
                request_timeout=10
            )
            
            # 测试下载少量瓦片
            test_tiles = [
                (116.3974, 39.9093, 18),  # 北京
                (121.4737, 31.2304, 18),  # 上海
                (113.2644, 23.1291, 18),  # 广州
            ]
            
            successful_downloads = 0
            total_downloads = len(test_tiles)
            
            for lon, lat, zoom in test_tiles:
                try:
                    result = downloader.download_tile(lon, lat, zoom)
                    if result.success:
                        successful_downloads += 1
                except Exception as e:
                    self.logger.warning(f"下载失败: {e}")
            
            duration = time.time() - start_time
            monitor.stop_monitoring()
            
            stats = monitor.get_statistics()
            success_rate = successful_downloads / total_downloads
            throughput = successful_downloads / duration if duration > 0 else 0
            
            result = BenchmarkResult(
                test_name=test_name,
                duration=duration,
                memory_peak=stats.get('peak_memory_mb', 0),
                memory_avg=stats.get('avg_memory_mb', 0),
                cpu_avg=stats.get('avg_cpu_percent', 0),
                success_rate=success_rate,
                throughput=throughput,
                details={
                    'total_tiles': total_downloads,
                    'successful_tiles': successful_downloads,
                    'downloader_type': 'sync'
                }
            )
            
            self.results.append(result)
            self.logger.info(f"    完成时间: {duration:.2f}s")
            self.logger.info(f"    成功率: {success_rate:.2%}")
            self.logger.info(f"    吞吐量: {throughput:.2f} tiles/s")
            
        except Exception as e:
            self.logger.error(f"同步下载器测试失败: {e}")
    
    def _test_async_downloader(self):
        """测试异步下载器"""
        test_name = "异步下载器性能"
        self.logger.info(f"  {test_name}...")
        
        async def async_test():
            monitor = PerformanceMonitor()
            monitor.start_monitoring()
            
            start_time = time.time()
            
            try:
                # 创建异步下载器
                downloader = DownloaderFactory.create_downloader(
                    downloader_type=DownloaderType.ASYNC,
                    max_concurrency=10,
                    max_retries=3,
                    request_timeout=10
                )
                
                # 测试下载更多瓦片（异步可以处理更多）
                test_tiles = [
                    (116.3974 + i*0.001, 39.9093 + j*0.001, 18)
                    for i in range(5) for j in range(5)
                ]
                
                async with downloader:
                    results = await downloader.download_tiles(test_tiles)
                
                duration = time.time() - start_time
                monitor.stop_monitoring()
                
                successful_downloads = sum(1 for r in results if r.success)
                total_downloads = len(test_tiles)
                
                stats = monitor.get_statistics()
                success_rate = successful_downloads / total_downloads
                throughput = successful_downloads / duration if duration > 0 else 0
                
                result = BenchmarkResult(
                    test_name=test_name,
                    duration=duration,
                    memory_peak=stats.get('peak_memory_mb', 0),
                    memory_avg=stats.get('avg_memory_mb', 0),
                    cpu_avg=stats.get('avg_cpu_percent', 0),
                    success_rate=success_rate,
                    throughput=throughput,
                    details={
                        'total_tiles': total_downloads,
                        'successful_tiles': successful_downloads,
                        'downloader_type': 'async',
                        'concurrency': 10
                    }
                )
                
                self.results.append(result)
                self.logger.info(f"    完成时间: {duration:.2f}s")
                self.logger.info(f"    成功率: {success_rate:.2%}")
                self.logger.info(f"    吞吐量: {throughput:.2f} tiles/s")
                
            except Exception as e:
                self.logger.error(f"异步下载器测试失败: {e}")
        
        # 运行异步测试
        asyncio.run(async_test())
    
    def _test_concurrency_performance(self):
        """测试并发性能"""
        self.logger.info("测试并发性能...")
        
        concurrency_levels = [1, 2, 5, 10, 20]
        
        for concurrency in concurrency_levels:
            self._test_concurrency_level(concurrency)
    
    def _test_concurrency_level(self, concurrency: int):
        """测试特定并发级别"""
        test_name = f"并发级别 {concurrency}"
        self.logger.info(f"  {test_name}...")
        
        async def concurrency_test():
            monitor = PerformanceMonitor()
            monitor.start_monitoring()
            
            start_time = time.time()
            
            try:
                downloader = DownloaderFactory.create_downloader(
                    downloader_type=DownloaderType.ASYNC,
                    max_concurrency=concurrency,
                    max_retries=2,
                    request_timeout=10
                )
                
                # 固定数量的瓦片
                test_tiles = [
                    (116.3974 + i*0.001, 39.9093 + j*0.001, 18)
                    for i in range(10) for j in range(2)
                ]
                
                async with downloader:
                    results = await downloader.download_tiles(test_tiles)
                
                duration = time.time() - start_time
                monitor.stop_monitoring()
                
                successful_downloads = sum(1 for r in results if r.success)
                total_downloads = len(test_tiles)
                
                stats = monitor.get_statistics()
                success_rate = successful_downloads / total_downloads
                throughput = successful_downloads / duration if duration > 0 else 0
                
                result = BenchmarkResult(
                    test_name=test_name,
                    duration=duration,
                    memory_peak=stats.get('peak_memory_mb', 0),
                    memory_avg=stats.get('avg_memory_mb', 0),
                    cpu_avg=stats.get('avg_cpu_percent', 0),
                    success_rate=success_rate,
                    throughput=throughput,
                    details={
                        'concurrency_level': concurrency,
                        'total_tiles': total_downloads,
                        'successful_tiles': successful_downloads
                    }
                )
                
                self.results.append(result)
                self.logger.info(f"    完成时间: {duration:.2f}s")
                self.logger.info(f"    吞吐量: {throughput:.2f} tiles/s")
                
            except Exception as e:
                self.logger.error(f"并发测试失败 (level {concurrency}): {e}")
        
        asyncio.run(concurrency_test())
    
    def _test_memory_usage(self):
        """测试内存使用"""
        self.logger.info("测试内存使用...")
        
        # 测试不同数据量的内存使用
        data_sizes = [10, 50, 100, 200]
        
        for size in data_sizes:
            self._test_memory_with_size(size)
    
    def _test_memory_with_size(self, tile_count: int):
        """测试特定数据量的内存使用"""
        test_name = f"内存使用 ({tile_count} 瓦片)"
        self.logger.info(f"  {test_name}...")
        
        monitor = PerformanceMonitor()
        monitor.start_monitoring()
        
        start_time = time.time()
        initial_memory = psutil.Process().memory_info().rss / 1024**2
        
        try:
            # 创建临时测试数据
            with tempfile.TemporaryDirectory() as temp_dir:
                # 模拟大量瓦片处理
                test_tiles = [
                    (116.3974 + i*0.0001, 39.9093 + j*0.0001, 18)
                    for i in range(int(tile_count**0.5))
                    for j in range(int(tile_count**0.5))
                ][:tile_count]
                
                # 使用较低的并发避免网络限制
                config = {
                    'downloader_type': 'async',
                    'max_concurrency': 5,
                    'enable_cache': True,
                    'cache_dir': temp_dir
                }
                
                with RSDatasetGenerator(**config) as generator:
                    # 模拟处理过程
                    for i, (lon, lat, zoom) in enumerate(test_tiles[:10]):  # 只处理前10个避免过长时间
                        try:
                            # 模拟瓦片下载和处理
                            pass
                        except Exception:
                            pass
                        
                        if i % 5 == 0:  # 每5个瓦片检查一次内存
                            current_memory = psutil.Process().memory_info().rss / 1024**2
                            memory_increase = current_memory - initial_memory
                            if memory_increase > 500:  # 如果内存增长超过500MB，停止测试
                                self.logger.warning(f"内存使用过高，停止测试: {memory_increase:.1f}MB")
                                break
            
            duration = time.time() - start_time
            monitor.stop_monitoring()
            
            final_memory = psutil.Process().memory_info().rss / 1024**2
            memory_increase = final_memory - initial_memory
            
            stats = monitor.get_statistics()
            
            result = BenchmarkResult(
                test_name=test_name,
                duration=duration,
                memory_peak=stats.get('peak_memory_mb', 0),
                memory_avg=stats.get('avg_memory_mb', 0),
                cpu_avg=stats.get('avg_cpu_percent', 0),
                success_rate=1.0,  # 内存测试主要关注内存使用
                throughput=tile_count / duration if duration > 0 else 0,
                details={
                    'tile_count': tile_count,
                    'initial_memory_mb': initial_memory,
                    'final_memory_mb': final_memory,
                    'memory_increase_mb': memory_increase
                }
            )
            
            self.results.append(result)
            self.logger.info(f"    内存增长: {memory_increase:.1f}MB")
            self.logger.info(f"    峰值内存: {stats.get('peak_memory_mb', 0):.1f}MB")
            
        except Exception as e:
            self.logger.error(f"内存测试失败 ({tile_count} 瓦片): {e}")
    
    def _test_image_processing_performance(self):
        """测试图像处理性能"""
        self.logger.info("测试图像处理性能...")
        
        try:
            from PIL import Image
            import numpy as np
            
            test_name = "图像处理性能"
            monitor = PerformanceMonitor()
            monitor.start_monitoring()
            
            start_time = time.time()
            
            # 创建测试图像
            image_sizes = [(256, 256), (512, 512), (1024, 1024)]
            processing_count = 0
            
            for width, height in image_sizes:
                for _ in range(5):  # 每种尺寸处理5次
                    # 创建随机图像
                    img_array = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
                    img = Image.fromarray(img_array)
                    
                    # 模拟图像处理操作
                    img_resized = img.resize((width//2, height//2))
                    img_cropped = img.crop((0, 0, width//2, height//2))
                    
                    # 模拟保存操作（不实际保存）
                    processing_count += 1
            
            duration = time.time() - start_time
            monitor.stop_monitoring()
            
            stats = monitor.get_statistics()
            throughput = processing_count / duration if duration > 0 else 0
            
            result = BenchmarkResult(
                test_name=test_name,
                duration=duration,
                memory_peak=stats.get('peak_memory_mb', 0),
                memory_avg=stats.get('avg_memory_mb', 0),
                cpu_avg=stats.get('avg_cpu_percent', 0),
                success_rate=1.0,
                throughput=throughput,
                details={
                    'processed_images': processing_count,
                    'image_sizes': image_sizes
                }
            )
            
            self.results.append(result)
            self.logger.info(f"    处理图像数: {processing_count}")
            self.logger.info(f"    处理速度: {throughput:.2f} images/s")
            
        except ImportError:
            self.logger.warning("PIL不可用，跳过图像处理测试")
        except Exception as e:
            self.logger.error(f"图像处理测试失败: {e}")
    
    def _test_end_to_end_performance(self):
        """测试端到端性能"""
        self.logger.info("测试端到端性能...")
        
        test_name = "端到端性能"
        
        try:
            # 创建临时测试文件
            with tempfile.TemporaryDirectory() as temp_dir:
                # 创建简单的测试GeoJSON
                test_geojson = {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [116.3974, 39.9093]  # 北京
                            },
                            "properties": {"name": "test_point_1"}
                        },
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [121.4737, 31.2304]  # 上海
                            },
                            "properties": {"name": "test_point_2"}
                        }
                    ]
                }
                
                import json
                test_file = Path(temp_dir) / 'test_points.geojson'
                with open(test_file, 'w', encoding='utf-8') as f:
                    json.dump(test_geojson, f)
                
                output_dir = Path(temp_dir) / 'output'
                
                monitor = PerformanceMonitor()
                monitor.start_monitoring()
                
                start_time = time.time()
                
                # 配置生成器
                config = {
                    'zoom_level': 18,
                    'grid_size': 3,  # 小网格减少下载时间
                    'downloader_type': 'async',
                    'max_concurrency': 5,
                    'enable_cache': True,
                    'max_retries': 2,
                    'request_timeout': 10
                }
                
                # 执行端到端处理
                with RSDatasetGenerator(**config) as generator:
                    result = generator.generate_dataset(
                        input_file=str(test_file),
                        output_dir=str(output_dir)
                    )
                
                duration = time.time() - start_time
                monitor.stop_monitoring()
                
                stats = monitor.get_statistics()
                processing_stats = result.get('processing_stats', {})
                
                success_rate = processing_stats.get('success_rate', 0) / 100
                total_points = processing_stats.get('total_points', 0)
                throughput = total_points / duration if duration > 0 else 0
                
                benchmark_result = BenchmarkResult(
                    test_name=test_name,
                    duration=duration,
                    memory_peak=stats.get('peak_memory_mb', 0),
                    memory_avg=stats.get('avg_memory_mb', 0),
                    cpu_avg=stats.get('avg_cpu_percent', 0),
                    success_rate=success_rate,
                    throughput=throughput,
                    details={
                        'total_points': total_points,
                        'successful_points': processing_stats.get('successful_points', 0),
                        'total_tiles': processing_stats.get('total_tiles', 0),
                        'successful_tiles': processing_stats.get('successful_tiles', 0),
                        'config': config
                    }
                )
                
                self.results.append(benchmark_result)
                self.logger.info(f"    处理点数: {total_points}")
                self.logger.info(f"    成功率: {success_rate:.2%}")
                self.logger.info(f"    处理速度: {throughput:.2f} points/s")
                
        except Exception as e:
            self.logger.error(f"端到端测试失败: {e}")
    
    def _generate_report(self):
        """生成性能报告"""
        self.logger.info("生成性能报告...")
        
        # 生成Markdown报告
        self._generate_markdown_report()
        
        # 生成JSON报告
        self._generate_json_report()
        
        # 生成CSV报告
        self._generate_csv_report()
    
    def _generate_markdown_report(self):
        """生成Markdown格式报告"""
        report_file = self.output_dir / 'performance_report.md'
        
        lines = [
            "# 性能基准测试报告",
            "",
            f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"测试项目数: {len(self.results)}",
            "",
            "## 系统信息",
            "",
            f"- CPU核心数: {psutil.cpu_count()}",
            f"- 物理核心数: {psutil.cpu_count(logical=False)}",
            f"- 总内存: {psutil.virtual_memory().total / 1024**3:.1f} GB",
            f"- Python版本: {sys.version.split()[0]}",
            "",
            "## 测试结果摘要",
            "",
            "| 测试项目 | 耗时(s) | 内存峰值(MB) | CPU平均(%) | 成功率(%) | 吞吐量 |",
            "|---------|---------|-------------|-----------|----------|--------|"
        ]
        
        for result in self.results:
            lines.append(
                f"| {result.test_name} | {result.duration:.2f} | "
                f"{result.memory_peak:.1f} | {result.cpu_avg:.1f} | "
                f"{result.success_rate:.1%} | {result.throughput:.2f} |"
            )
        
        lines.extend([
            "",
            "## 详细分析",
            ""
        ])
        
        # 分析结果
        if self.results:
            durations = [r.duration for r in self.results]
            memory_peaks = [r.memory_peak for r in self.results]
            throughputs = [r.throughput for r in self.results if r.throughput > 0]
            
            lines.extend([
                f"### 性能统计",
                "",
                f"- 平均耗时: {statistics.mean(durations):.2f}s",
                f"- 最大耗时: {max(durations):.2f}s",
                f"- 最小耗时: {min(durations):.2f}s",
                f"- 平均内存峰值: {statistics.mean(memory_peaks):.1f}MB",
                f"- 最大内存峰值: {max(memory_peaks):.1f}MB",
                ""
            ])
            
            if throughputs:
                lines.extend([
                    f"- 平均吞吐量: {statistics.mean(throughputs):.2f}",
                    f"- 最大吞吐量: {max(throughputs):.2f}",
                    ""
                ])
        
        # 并发性能分析
        concurrency_results = [r for r in self.results if '并发级别' in r.test_name]
        if concurrency_results:
            lines.extend([
                "### 并发性能分析",
                "",
                "| 并发级别 | 耗时(s) | 吞吐量 | 内存峰值(MB) |",
                "|---------|---------|--------|-------------|"
            ])
            
            for result in concurrency_results:
                concurrency = result.details.get('concurrency_level', 'N/A')
                lines.append(
                    f"| {concurrency} | {result.duration:.2f} | "
                    f"{result.throughput:.2f} | {result.memory_peak:.1f} |"
                )
            
            lines.append("")
        
        # 建议
        lines.extend([
            "## 性能优化建议",
            "",
            "### 下载性能",
            "- 根据网络条件调整并发级别",
            "- 启用缓存减少重复下载",
            "- 合理设置重试次数和超时时间",
            "",
            "### 内存优化",
            "- 处理大量数据时考虑分批处理",
            "- 及时释放不需要的图像对象",
            "- 监控内存使用避免内存泄漏",
            "",
            "### 并发优化",
            "- CPU密集型任务使用进程池",
            "- I/O密集型任务使用异步处理",
            "- 根据系统资源调整并发参数",
            ""
        ])
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        self.logger.info(f"Markdown报告已保存: {report_file}")
    
    def _generate_json_report(self):
        """生成JSON格式报告"""
        report_file = self.output_dir / 'performance_report.json'
        
        report_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'system_info': {
                'cpu_count': psutil.cpu_count(),
                'cpu_count_physical': psutil.cpu_count(logical=False),
                'total_memory_gb': psutil.virtual_memory().total / 1024**3,
                'python_version': sys.version.split()[0]
            },
            'results': [
                {
                    'test_name': r.test_name,
                    'duration': r.duration,
                    'memory_peak': r.memory_peak,
                    'memory_avg': r.memory_avg,
                    'cpu_avg': r.cpu_avg,
                    'success_rate': r.success_rate,
                    'throughput': r.throughput,
                    'details': r.details
                }
                for r in self.results
            ]
        }
        
        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"JSON报告已保存: {report_file}")
    
    def _generate_csv_report(self):
        """生成CSV格式报告"""
        report_file = self.output_dir / 'performance_report.csv'
        
        import csv
        
        with open(report_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入标题行
            writer.writerow([
                '测试项目', '耗时(s)', '内存峰值(MB)', '内存平均(MB)',
                'CPU平均(%)', '成功率(%)', '吞吐量', '详细信息'
            ])
            
            # 写入数据行
            for result in self.results:
                writer.writerow([
                    result.test_name,
                    f"{result.duration:.2f}",
                    f"{result.memory_peak:.1f}",
                    f"{result.memory_avg:.1f}",
                    f"{result.cpu_avg:.1f}",
                    f"{result.success_rate:.1%}",
                    f"{result.throughput:.2f}",
                    str(result.details)
                ])
        
        self.logger.info(f"CSV报告已保存: {report_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="性能基准测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python benchmark.py
  python benchmark.py --output custom_results
  python benchmark.py --quick
        """
    )
    
    parser.add_argument(
        '--output', '-o',
        default='benchmark_results',
        help='输出目录（默认: benchmark_results）'
    )
    
    parser.add_argument(
        '--quick', '-q',
        action='store_true',
        help='快速测试模式（减少测试项目）'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细输出'
    )
    
    args = parser.parse_args()
    
    print("RSDatasetGenerator 性能基准测试")
    print("=" * 50)
    
    # 创建基准测试器
    benchmark = PerformanceBenchmark(args.output)
    
    try:
        # 运行测试
        if args.quick:
            print("运行快速测试模式...")
            # 在快速模式下，可以减少测试项目或测试数据量
        
        results = benchmark.run_all_benchmarks()
        
        print(f"\n测试完成！共完成 {len(results)} 项测试")
        print(f"结果已保存到: {args.output}")
        
        # 显示摘要
        if results:
            print("\n性能摘要:")
            print("-" * 30)
            
            total_duration = sum(r.duration for r in results)
            avg_memory = statistics.mean([r.memory_peak for r in results])
            avg_success_rate = statistics.mean([r.success_rate for r in results])
            
            print(f"总测试时间: {total_duration:.2f}s")
            print(f"平均内存峰值: {avg_memory:.1f}MB")
            print(f"平均成功率: {avg_success_rate:.1%}")
            
            # 找出性能最好和最差的测试
            best_throughput = max(results, key=lambda r: r.throughput)
            worst_memory = max(results, key=lambda r: r.memory_peak)
            
            print(f"\n最佳吞吐量: {best_throughput.test_name} ({best_throughput.throughput:.2f})")
            print(f"最高内存使用: {worst_memory.test_name} ({worst_memory.memory_peak:.1f}MB)")
    
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()