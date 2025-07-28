"""命令行接口模块

提供用户友好的命令行工具，支持配置文件、参数验证和进度显示。
"""

import os
import sys
import argparse
from typing import Dict, Any, Optional
from pathlib import Path

from .config import Config, create_argument_parser
from .rs_dataset_generator import RSDatasetGenerator, create_generator
from .utils import Logger, ConfigurationError, ValidationError, DataProcessingError


def setup_logging(verbose: bool = False, log_file: str = None) -> Logger:
    """设置日志记录
    
    Args:
        verbose: 是否启用详细日志
        log_file: 日志文件路径
        
    Returns:
        配置好的日志记录器
    """
    log_level = 'DEBUG' if verbose else 'INFO'
    
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    logger = Logger(
        name='RSDatasetGenerator',
        level=log_level,
        log_file=log_file,
        console_output=True
    )
    
    return logger


def validate_arguments(args: argparse.Namespace) -> bool:
    """验证命令行参数
    
    Args:
        args: 解析后的命令行参数
        
    Returns:
        参数是否有效
    """
    errors = []
    
    # 验证输入文件
    if not os.path.exists(args.input_file):
        errors.append(f"输入文件不存在: {args.input_file}")
    
    # 验证配置文件（如果提供）
    if args.config and not os.path.exists(args.config):
        errors.append(f"配置文件不存在: {args.config}")
    
    # 验证缩放级别
    if not (1 <= args.zoom_level <= 20):
        errors.append(f"缩放级别必须在1-20之间，当前值: {args.zoom_level}")
    
    # 验证网格大小
    if not (1 <= args.grid_size <= 20):
        errors.append(f"网格大小必须在1-20之间，当前值: {args.grid_size}")
    
    # 验证并发数
    if not (1 <= args.max_concurrency <= 100):
        errors.append(f"最大并发数必须在1-100之间，当前值: {args.max_concurrency}")
    
    # 验证下载器类型
    valid_downloaders = ['sync', 'async', 'auto']
    if args.downloader_type not in valid_downloaders:
        errors.append(f"无效的下载器类型: {args.downloader_type}，有效值: {valid_downloaders}")
    
    if errors:
        print("参数验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


def create_config_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    """从命令行参数创建配置字典
    
    Args:
        args: 解析后的命令行参数
        
    Returns:
        配置字典
    """
    config_dict = {
        'zoom_level': args.zoom_level,
        'grid_size': args.grid_size,
        'max_concurrency': args.max_concurrency,
        'max_retries': args.max_retries,
        'request_timeout': args.request_timeout,
        'enable_cache': args.enable_cache,
        'downloader_type': args.downloader_type,
        'add_markers': args.add_markers,
        'delay_range': [args.min_delay, args.max_delay]
    }
    
    return config_dict


def print_banner():
    """打印程序横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    遥感数据集生成器                          ║
║                 Remote Sensing Dataset Generator             ║
║                                                              ║
║  从矢量文件生成对应的Google Maps遥感图像数据集               ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_processing_info(args: argparse.Namespace, generator: RSDatasetGenerator):
    """打印处理信息
    
    Args:
        args: 命令行参数
        generator: 数据集生成器实例
    """
    print("\n处理配置:")
    print(f"  输入文件: {args.input_file}")
    print(f"  输出目录: {args.output_dir or '自动生成'}")
    print(f"  缩放级别: {args.zoom_level}")
    print(f"  网格大小: {args.grid_size}x{args.grid_size}")
    print(f"  下载器类型: {args.downloader_type}")
    print(f"  最大并发数: {args.max_concurrency}")
    print(f"  启用缓存: {'是' if args.enable_cache else '否'}")
    print(f"  添加标记: {'是' if args.add_markers else '否'}")
    
    # 估算处理时间
    if not args.no_estimate:
        print("\n正在估算处理时间...")
        try:
            estimate = generator.estimate_processing_time(
                args.input_file,
                zoom_level=args.zoom_level,
                grid_size=args.grid_size,
                max_concurrency=args.max_concurrency
            )
            
            if estimate:
                print(f"  预计点数: {estimate.get('total_points', 'N/A')}")
                print(f"  预计瓦片数: {estimate.get('total_tiles', 'N/A')}")
                print(f"  预计处理时间: {estimate.get('estimated_total_time_formatted', 'N/A')}")
                print(f"  预计数据量: {estimate.get('estimated_data_size_formatted', 'N/A')}")
        except Exception as e:
            print(f"  估算失败: {str(e)}")
    
    print()


def print_result_summary(result: Dict[str, Any]):
    """打印处理结果摘要
    
    Args:
        result: 处理结果
    """
    stats = result.get('processing_stats', {})
    output_files = result.get('output_files', {})
    
    print("\n" + "=" * 60)
    print("                    处理完成")
    print("=" * 60)
    
    # 处理统计
    print(f"总点数: {stats.get('total_points', 0)}")
    print(f"成功处理: {stats.get('successful_points', 0)}")
    print(f"处理失败: {stats.get('failed_points', 0)}")
    print(f"成功率: {stats.get('success_rate', 0):.2f}%")
    
    # 瓦片统计
    print(f"\n总瓦片数: {stats.get('total_tiles', 0)}")
    print(f"下载成功: {stats.get('successful_tiles', 0)}")
    print(f"下载失败: {stats.get('failed_tiles', 0)}")
    print(f"下载成功率: {stats.get('tile_success_rate', 0):.2f}%")
    
    # 处理时间
    processing_time = stats.get('processing_time', 0)
    if processing_time > 0:
        print(f"\n处理时间: {processing_time:.2f} 秒")
    
    # 输出文件
    print(f"\n生成图像数: {output_files.get('images_count', 0)}")
    print(f"输出目录: {output_files.get('output_directory', '')}")
    
    # 摘要文件
    summary_files = output_files.get('summary_files', {})
    if summary_files:
        print("\n生成的摘要文件:")
        for file_type, file_path in summary_files.items():
            print(f"  - {file_type}: {file_path}")
    
    print("=" * 60)


def handle_interactive_mode():
    """处理交互模式"""
    print("\n进入交互模式...")
    print("请按照提示输入参数，或按 Ctrl+C 退出。\n")
    
    try:
        # 获取输入文件
        while True:
            input_file = input("请输入矢量文件路径: ").strip()
            if os.path.exists(input_file):
                break
            print(f"文件不存在: {input_file}，请重新输入。")
        
        # 获取输出目录
        output_dir = input("请输入输出目录（留空使用默认）: ").strip()
        if not output_dir:
            output_dir = None
        
        # 获取缩放级别
        while True:
            try:
                zoom_level = int(input("请输入缩放级别 (1-20, 默认18): ") or "18")
                if 1 <= zoom_level <= 20:
                    break
                print("缩放级别必须在1-20之间。")
            except ValueError:
                print("请输入有效的数字。")
        
        # 获取网格大小
        while True:
            try:
                grid_size = int(input("请输入网格大小 (1-20, 默认5): ") or "5")
                if 1 <= grid_size <= 20:
                    break
                print("网格大小必须在1-20之间。")
            except ValueError:
                print("请输入有效的数字。")
        
        # 获取下载器类型
        downloader_type = input("请输入下载器类型 (sync/async/auto, 默认auto): ").strip().lower() or "auto"
        if downloader_type not in ['sync', 'async', 'auto']:
            downloader_type = 'auto'
        
        # 获取并发数
        while True:
            try:
                max_concurrency = int(input("请输入最大并发数 (1-100, 默认10): ") or "10")
                if 1 <= max_concurrency <= 100:
                    break
                print("最大并发数必须在1-100之间。")
            except ValueError:
                print("请输入有效的数字。")
        
        # 其他选项
        enable_cache = input("是否启用缓存? (y/N): ").strip().lower() in ['y', 'yes', '是']
        add_markers = input("是否在图像上添加点标记? (y/N): ").strip().lower() in ['y', 'yes', '是']
        
        print("\n开始处理...")
        
        # 创建生成器并处理
        with create_generator(
            zoom_level=zoom_level,
            grid_size=grid_size,
            max_concurrency=max_concurrency,
            downloader_type=downloader_type,
            enable_cache=enable_cache,
            add_markers=add_markers
        ) as generator:
            result = generator.generate_dataset(input_file, output_dir)
            print_result_summary(result)
        
    except KeyboardInterrupt:
        print("\n用户取消操作。")
        sys.exit(0)
    except Exception as e:
        print(f"\n处理失败: {str(e)}")
        sys.exit(1)


def main():
    """主函数"""
    try:
        # 创建参数解析器
        parser = create_argument_parser()
        
        # 添加CLI特有的参数
        parser.add_argument(
            '--interactive', '-i',
            action='store_true',
            help='启用交互模式'
        )
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='启用详细日志输出'
        )
        parser.add_argument(
            '--log-file',
            type=str,
            help='日志文件路径'
        )
        parser.add_argument(
            '--no-banner',
            action='store_true',
            help='不显示程序横幅'
        )
        parser.add_argument(
            '--no-estimate',
            action='store_true',
            help='跳过处理时间估算'
        )
        parser.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='静默模式，只输出错误信息'
        )
        
        # 解析参数
        args = parser.parse_args()
        
        # 处理交互模式
        if args.interactive:
            if not args.no_banner:
                print_banner()
            handle_interactive_mode()
            return
        
        # 检查必需参数
        if not hasattr(args, 'input_file') or not args.input_file:
            parser.error("必须提供输入文件路径，或使用 --interactive 进入交互模式")
        
        # 设置日志
        if not args.quiet:
            logger = setup_logging(args.verbose, args.log_file)
        
        # 显示横幅
        if not args.no_banner and not args.quiet:
            print_banner()
        
        # 验证参数
        if not validate_arguments(args):
            sys.exit(1)
        
        # 创建配置
        config_dict = create_config_from_args(args)
        
        # 创建生成器
        generator = create_generator(
            config_file=args.config,
            **config_dict
        )
        
        # 显示处理信息
        if not args.quiet:
            print_processing_info(args, generator)
        
        # 确认开始处理
        if not args.quiet and not args.yes:
            response = input("确认开始处理? (Y/n): ").strip().lower()
            if response in ['n', 'no', '否']:
                print("用户取消操作。")
                sys.exit(0)
        
        # 开始处理
        with generator:
            result = generator.generate_dataset(
                args.input_file,
                args.output_dir
            )
        
        # 显示结果
        if not args.quiet:
            print_result_summary(result)
        
        # 检查处理结果
        stats = result.get('processing_stats', {})
        if stats.get('failed_points', 0) > 0:
            print(f"\n警告: {stats['failed_points']} 个点处理失败")
            sys.exit(2)  # 部分失败
        
        print("\n处理成功完成！")
        
    except KeyboardInterrupt:
        print("\n用户中断操作。")
        sys.exit(130)
    except ValidationError as e:
        print(f"验证错误: {str(e)}")
        sys.exit(1)
    except ConfigurationError as e:
        print(f"配置错误: {str(e)}")
        sys.exit(1)
    except DataProcessingError as e:
        print(f"数据处理错误: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"未知错误: {str(e)}")
        if '--verbose' in sys.argv or '-v' in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()