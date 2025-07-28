#!/usr/bin/env python3
"""基本使用示例

展示如何使用遥感数据集生成器的基本功能。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src import RSDatasetGenerator, quick_generate


def example_1_basic_usage():
    """示例1: 基本使用方法"""
    print("=== 示例1: 基本使用方法 ===")
    
    # 输入文件路径（请替换为实际文件路径）
    input_file = "data/sample_points.shp"
    output_dir = "output/basic_example"
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"警告: 输入文件不存在: {input_file}")
        print("请准备一个包含地理点的Shapefile文件")
        return
    
    try:
        # 使用上下文管理器创建生成器
        with RSDatasetGenerator() as generator:
            # 生成数据集
            result = generator.generate_dataset(
                input_file=input_file,
                output_dir=output_dir,
                zoom_level=18,
                grid_size=3,
                max_concurrency=5
            )
            
            # 打印结果
            stats = result.get('processing_stats', {})
            print(f"处理完成！")
            print(f"总点数: {stats.get('total_points', 0)}")
            print(f"成功处理: {stats.get('successful_points', 0)}")
            print(f"成功率: {stats.get('success_rate', 0):.2f}%")
            
    except Exception as e:
        print(f"处理失败: {str(e)}")


def example_2_quick_generate():
    """示例2: 快速生成方法"""
    print("\n=== 示例2: 快速生成方法 ===")
    
    input_file = "data/sample_points.shp"
    
    if not os.path.exists(input_file):
        print(f"警告: 输入文件不存在: {input_file}")
        return
    
    try:
        # 使用快速生成函数
        result = quick_generate(
            input_file=input_file,
            output_dir="output/quick_example",
            zoom_level=17,
            grid_size=5,
            downloader_type='async',
            enable_cache=True
        )
        
        print("快速生成完成！")
        print(f"输出目录: {result.get('output_files', {}).get('output_directory', '')}")
        
    except Exception as e:
        print(f"快速生成失败: {str(e)}")


def example_3_custom_config():
    """示例3: 自定义配置"""
    print("\n=== 示例3: 自定义配置 ===")
    
    input_file = "data/sample_points.shp"
    
    if not os.path.exists(input_file):
        print(f"警告: 输入文件不存在: {input_file}")
        return
    
    try:
        # 创建自定义配置
        custom_config = {
            'zoom_level': 19,
            'grid_size': 7,
            'max_concurrency': 15,
            'downloader_type': 'async',
            'enable_cache': True,
            'add_markers': True,
            'max_retries': 5,
            'request_timeout': 60
        }
        
        # 使用自定义配置创建生成器
        with RSDatasetGenerator(**custom_config) as generator:
            # 验证输入文件
            if not generator.validate_input(input_file):
                print("输入文件验证失败")
                return
            
            # 估算处理时间
            estimate = generator.estimate_processing_time(input_file)
            if estimate:
                print(f"预计处理时间: {estimate.get('estimated_total_time_formatted', 'N/A')}")
                print(f"预计数据量: {estimate.get('estimated_data_size_formatted', 'N/A')}")
            
            # 生成数据集
            result = generator.generate_dataset(
                input_file=input_file,
                output_dir="output/custom_example"
            )
            
            print("自定义配置处理完成！")
            
    except Exception as e:
        print(f"自定义配置处理失败: {str(e)}")


def example_4_batch_processing():
    """示例4: 批量处理"""
    print("\n=== 示例4: 批量处理 ===")
    
    # 模拟多个输入文件
    input_files = [
        "data/points_1.shp",
        "data/points_2.shp",
        "data/points_3.shp"
    ]
    
    # 检查文件是否存在
    existing_files = [f for f in input_files if os.path.exists(f)]
    
    if not existing_files:
        print("警告: 没有找到可处理的输入文件")
        print("请准备一些Shapefile文件进行批量处理")
        return
    
    try:
        # 批量处理配置
        batch_config = {
            'zoom_level': 18,
            'grid_size': 5,
            'max_concurrency': 8,
            'downloader_type': 'async',
            'enable_cache': True
        }
        
        # 创建生成器
        with RSDatasetGenerator(**batch_config) as generator:
            for i, input_file in enumerate(existing_files, 1):
                print(f"\n处理文件 {i}/{len(existing_files)}: {input_file}")
                
                try:
                    # 为每个文件创建独立的输出目录
                    file_name = os.path.splitext(os.path.basename(input_file))[0]
                    output_dir = f"output/batch_example/{file_name}"
                    
                    # 处理文件
                    result = generator.generate_dataset(
                        input_file=input_file,
                        output_dir=output_dir
                    )
                    
                    stats = result.get('processing_stats', {})
                    print(f"  完成: {stats.get('successful_points', 0)} 个点")
                    
                except Exception as e:
                    print(f"  处理失败: {str(e)}")
        
        print("\n批量处理完成！")
        
    except Exception as e:
        print(f"批量处理失败: {str(e)}")


def example_5_config_file():
    """示例5: 使用配置文件"""
    print("\n=== 示例5: 使用配置文件 ===")
    
    input_file = "data/sample_points.shp"
    config_file = "config.yaml"
    
    if not os.path.exists(input_file):
        print(f"警告: 输入文件不存在: {input_file}")
        return
    
    if not os.path.exists(config_file):
        print(f"警告: 配置文件不存在: {config_file}")
        return
    
    try:
        # 使用配置文件创建生成器
        with RSDatasetGenerator(config_file=config_file) as generator:
            # 获取配置信息
            config_info = generator.get_config_info()
            print("当前配置:")
            print(f"  缩放级别: {config_info.get('download_config', {}).get('zoom_level')}")
            print(f"  网格大小: {config_info.get('download_config', {}).get('grid_size')}")
            print(f"  下载器类型: {config_info.get('download_config', {}).get('downloader_type')}")
            
            # 生成数据集
            result = generator.generate_dataset(
                input_file=input_file,
                output_dir="output/config_example"
            )
            
            print("配置文件处理完成！")
            
    except Exception as e:
        print(f"配置文件处理失败: {str(e)}")


def create_sample_data():
    """创建示例数据（如果不存在）"""
    print("\n=== 创建示例数据 ===")
    
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        import pandas as pd
        
        # 创建示例点数据
        points = [
            Point(116.3974, 39.9093),  # 北京天安门
            Point(121.4737, 31.2304),  # 上海外滩
            Point(113.2644, 23.1291),  # 广州塔
        ]
        
        # 创建GeoDataFrame
        gdf = gpd.GeoDataFrame({
            'id': ['beijing', 'shanghai', 'guangzhou'],
            'name': ['北京天安门', '上海外滩', '广州塔'],
            'geometry': points
        }, crs='EPSG:4326')
        
        # 确保数据目录存在
        os.makedirs('data', exist_ok=True)
        
        # 保存为Shapefile
        output_file = 'data/sample_points.shp'
        gdf.to_file(output_file)
        
        print(f"示例数据已创建: {output_file}")
        print(f"包含 {len(gdf)} 个地理点")
        
        return True
        
    except ImportError:
        print("无法创建示例数据: 缺少geopandas依赖")
        print("请安装: pip install geopandas")
        return False
    except Exception as e:
        print(f"创建示例数据失败: {str(e)}")
        return False


def main():
    """主函数"""
    print("遥感数据集生成器 - 使用示例")
    print("=" * 50)
    
    # 检查是否有示例数据，如果没有则创建
    if not os.path.exists('data/sample_points.shp'):
        print("未找到示例数据，尝试创建...")
        if not create_sample_data():
            print("\n请手动准备Shapefile文件并更新示例中的文件路径")
            return
    
    # 运行所有示例
    try:
        example_1_basic_usage()
        example_2_quick_generate()
        example_3_custom_config()
        example_4_batch_processing()
        example_5_config_file()
        
        print("\n" + "=" * 50)
        print("所有示例运行完成！")
        print("请查看 output/ 目录中的生成结果")
        
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"\n运行示例时出错: {str(e)}")


if __name__ == '__main__':
    main()