#!/usr/bin/env python3
"""遗留代码迁移脚本

帮助用户从旧版本的getTiles脚本迁移到新的架构设计。
这个脚本会分析旧代码中的配置参数，并生成对应的新版本调用代码。
"""

import os
import re
import sys
import ast
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class LegacyCodeAnalyzer:
    """遗留代码分析器"""
    
    def __init__(self):
        self.config_patterns = {
            'input_shapefile': r'input_shapefile\s*=\s*["\']([^"\']*)["\']',
            'zoom_level': r'zoom_level\s*=\s*(\d+)',
            'grid_size': r'grid_size\s*=\s*(\d+)',
            'request_interval': r'request_interval\s*=\s*([\d\.]+)',
            'retry_wait_time': r'retry_wait_time\s*=\s*([\d\.]+)',
            'max_retries': r'max_retries\s*=\s*(\d+)',
            'output_dir': r'output_dir\s*=\s*["\']([^"\']*)["\']'
        }
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """分析遗留代码文件
        
        Args:
            file_path: 遗留代码文件路径
            
        Returns:
            提取的配置参数字典
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        config = {}
        
        # 提取配置参数
        for param_name, pattern in self.config_patterns.items():
            match = re.search(pattern, content)
            if match:
                value = match.group(1)
                # 尝试转换数据类型
                if param_name in ['zoom_level', 'grid_size', 'max_retries']:
                    config[param_name] = int(value)
                elif param_name in ['request_interval', 'retry_wait_time']:
                    config[param_name] = float(value)
                else:
                    config[param_name] = value
        
        # 分析代码结构
        config['code_analysis'] = self._analyze_code_structure(content)
        
        return config
    
    def _analyze_code_structure(self, content: str) -> Dict[str, Any]:
        """分析代码结构
        
        Args:
            content: 代码内容
            
        Returns:
            代码结构分析结果
        """
        analysis = {
            'has_async': 'async' in content or 'await' in content,
            'has_multiprocessing': 'multiprocessing' in content or 'Pool' in content,
            'has_threading': 'threading' in content or 'Thread' in content,
            'has_cache': 'cache' in content.lower(),
            'has_retry': 'retry' in content.lower(),
            'has_progress': 'tqdm' in content or 'progress' in content.lower(),
            'imports': self._extract_imports(content)
        }
        
        return analysis
    
    def _extract_imports(self, content: str) -> List[str]:
        """提取导入的模块
        
        Args:
            content: 代码内容
            
        Returns:
            导入的模块列表
        """
        imports = []
        
        # 匹配import语句
        import_patterns = [
            r'^import\s+([\w\.]+)',
            r'^from\s+([\w\.]+)\s+import'
        ]
        
        for line in content.split('\n'):
            line = line.strip()
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    imports.append(match.group(1))
        
        return list(set(imports))


class MigrationGenerator:
    """迁移代码生成器"""
    
    def __init__(self):
        self.template_basic = '''
#!/usr/bin/env python3
"""从遗留代码迁移的脚本

这个脚本是从 {legacy_file} 自动生成的。
使用新的RSDatasetGenerator架构。
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src import RSDatasetGenerator

def main():
    """主函数"""
    # 配置参数（从遗留代码提取）
    config = {config_dict}
    
    # 输入文件路径
    input_file = "{input_file}"
    output_dir = "{output_dir}"
    
    try:
        # 创建生成器并处理
        with RSDatasetGenerator(**config) as generator:
            result = generator.generate_dataset(
                input_file=input_file,
                output_dir=output_dir
            )
            
            # 打印结果
            stats = result.get('processing_stats', {{}})
            print(f"处理完成！")
            print(f"总点数: {{stats.get('total_points', 0)}}")
            print(f"成功处理: {{stats.get('successful_points', 0)}}")
            print(f"成功率: {{stats.get('success_rate', 0):.2f}}%")
            
    except Exception as e:
        print(f"处理失败: {{str(e)}}")
        sys.exit(1)

if __name__ == '__main__':
    main()
'''
        
        self.template_advanced = '''
#!/usr/bin/env python3
"""从遗留代码迁移的高级脚本

这个脚本是从 {legacy_file} 自动生成的。
包含了原始代码的高级功能。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src import RSDatasetGenerator
from src.utils import Logger, PerformanceMonitor

def main():
    """主函数"""
    # 配置参数（从遗留代码提取）
    config = {config_dict}
    
    # 输入文件路径
    input_file = "{input_file}"
    output_dir = "{output_dir}"
    
    # 设置日志
    logger = Logger(
        name='MigratedScript',
        level='INFO',
        console_output=True
    )
    
    # 性能监控
    monitor = PerformanceMonitor()
    
    try:
        logger.info("开始处理遥感数据集...")
        
        # 创建生成器
        with RSDatasetGenerator(**config) as generator:
            # 验证输入
            if not generator.validate_input(input_file):
                logger.error("输入文件验证失败")
                return
            
            # 估算处理时间
            estimate = generator.estimate_processing_time(input_file)
            if estimate:
                logger.info(f"预计处理时间: {{estimate.get('estimated_total_time_formatted', 'N/A')}}")
            
            # 开始监控
            monitor.start_monitoring()
            
            # 处理数据集
            result = generator.generate_dataset(
                input_file=input_file,
                output_dir=output_dir
            )
            
            # 停止监控
            monitor.stop_monitoring()
            
            # 打印详细结果
            stats = result.get('processing_stats', {{}})
            output_files = result.get('output_files', {{}})
            
            logger.info("=" * 50)
            logger.info("处理完成")
            logger.info("=" * 50)
            logger.info(f"总点数: {{stats.get('total_points', 0)}}")
            logger.info(f"成功处理: {{stats.get('successful_points', 0)}}")
            logger.info(f"处理失败: {{stats.get('failed_points', 0)}}")
            logger.info(f"成功率: {{stats.get('success_rate', 0):.2f}}%")
            logger.info(f"总瓦片数: {{stats.get('total_tiles', 0)}}")
            logger.info(f"下载成功: {{stats.get('successful_tiles', 0)}}")
            logger.info(f"生成图像数: {{output_files.get('images_count', 0)}}")
            logger.info(f"输出目录: {{output_files.get('output_directory', '')}}")
            
            # 性能统计
            perf_stats = monitor.get_statistics()
            if perf_stats:
                logger.info(f"平均CPU使用率: {{perf_stats.get('avg_cpu_percent', 0):.1f}}%")
                logger.info(f"峰值内存使用: {{perf_stats.get('peak_memory_mb', 0):.1f}} MB")
            
    except Exception as e:
        logger.error(f"处理失败: {{str(e)}}")
        sys.exit(1)

if __name__ == '__main__':
    main()
'''
    
    def generate_migration_script(self, legacy_config: Dict[str, Any], 
                                output_file: str, advanced: bool = False) -> str:
        """生成迁移脚本
        
        Args:
            legacy_config: 遗留配置参数
            output_file: 输出文件路径
            advanced: 是否生成高级版本
            
        Returns:
            生成的脚本内容
        """
        # 转换配置参数
        new_config = self._convert_config(legacy_config)
        
        # 选择模板
        template = self.template_advanced if advanced else self.template_basic
        
        # 格式化配置字典
        config_str = self._format_config_dict(new_config)
        
        # 生成脚本内容
        script_content = template.format(
            legacy_file=legacy_config.get('source_file', 'unknown'),
            config_dict=config_str,
            input_file=legacy_config.get('input_shapefile', 'input.shp'),
            output_dir=legacy_config.get('output_dir', 'output')
        )
        
        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # 设置执行权限
        os.chmod(output_file, 0o755)
        
        return script_content
    
    def _convert_config(self, legacy_config: Dict[str, Any]) -> Dict[str, Any]:
        """转换遗留配置到新格式
        
        Args:
            legacy_config: 遗留配置
            
        Returns:
            新格式配置
        """
        new_config = {}
        
        # 直接映射的参数
        direct_mappings = {
            'zoom_level': 'zoom_level',
            'grid_size': 'grid_size',
            'max_retries': 'max_retries'
        }
        
        for old_key, new_key in direct_mappings.items():
            if old_key in legacy_config:
                new_config[new_key] = legacy_config[old_key]
        
        # 需要转换的参数
        if 'request_interval' in legacy_config:
            # 将请求间隔转换为延迟范围
            interval = legacy_config['request_interval']
            new_config['delay_range'] = [interval * 0.5, interval * 1.5]
        
        # 根据代码分析推断配置
        code_analysis = legacy_config.get('code_analysis', {})
        
        if code_analysis.get('has_async'):
            new_config['downloader_type'] = 'async'
            new_config['max_concurrency'] = 10
        else:
            new_config['downloader_type'] = 'sync'
            new_config['max_concurrency'] = 1
        
        if code_analysis.get('has_cache'):
            new_config['enable_cache'] = True
        
        # 设置默认值
        defaults = {
            'zoom_level': 18,
            'grid_size': 5,
            'max_concurrency': 5,
            'downloader_type': 'auto',
            'enable_cache': True,
            'max_retries': 3,
            'request_timeout': 30
        }
        
        for key, default_value in defaults.items():
            if key not in new_config:
                new_config[key] = default_value
        
        return new_config
    
    def _format_config_dict(self, config: Dict[str, Any]) -> str:
        """格式化配置字典为Python代码
        
        Args:
            config: 配置字典
            
        Returns:
            格式化的字符串
        """
        lines = []
        lines.append('{')
        
        for key, value in config.items():
            if isinstance(value, str):
                lines.append(f'        "{key}": "{value}",')
            elif isinstance(value, list):
                lines.append(f'        "{key}": {value},')
            else:
                lines.append(f'        "{key}": {value},')
        
        lines.append('    }')
        
        return '\n'.join(lines)


class MigrationTool:
    """迁移工具主类"""
    
    def __init__(self):
        self.analyzer = LegacyCodeAnalyzer()
        self.generator = MigrationGenerator()
    
    def migrate_file(self, legacy_file: str, output_dir: str = "migrated", 
                    advanced: bool = False) -> str:
        """迁移单个文件
        
        Args:
            legacy_file: 遗留代码文件路径
            output_dir: 输出目录
            advanced: 是否生成高级版本
            
        Returns:
            生成的迁移脚本路径
        """
        print(f"正在分析文件: {legacy_file}")
        
        # 分析遗留代码
        config = self.analyzer.analyze_file(legacy_file)
        config['source_file'] = legacy_file
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成输出文件名
        base_name = os.path.splitext(os.path.basename(legacy_file))[0]
        suffix = '_advanced' if advanced else '_migrated'
        output_file = os.path.join(output_dir, f"{base_name}{suffix}.py")
        
        # 生成迁移脚本
        print(f"正在生成迁移脚本: {output_file}")
        self.generator.generate_migration_script(config, output_file, advanced)
        
        # 生成配置文件
        config_file = os.path.join(output_dir, f"{base_name}_config.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"迁移完成！")
        print(f"  迁移脚本: {output_file}")
        print(f"  配置文件: {config_file}")
        
        return output_file
    
    def migrate_directory(self, legacy_dir: str, output_dir: str = "migrated", 
                         pattern: str = "*.py") -> List[str]:
        """迁移目录中的所有文件
        
        Args:
            legacy_dir: 遗留代码目录
            output_dir: 输出目录
            pattern: 文件匹配模式
            
        Returns:
            生成的迁移脚本路径列表
        """
        import glob
        
        legacy_files = glob.glob(os.path.join(legacy_dir, pattern))
        migrated_files = []
        
        for legacy_file in legacy_files:
            try:
                migrated_file = self.migrate_file(legacy_file, output_dir)
                migrated_files.append(migrated_file)
            except Exception as e:
                print(f"迁移文件 {legacy_file} 失败: {str(e)}")
        
        return migrated_files
    
    def generate_migration_report(self, legacy_files: List[str], 
                                output_file: str = "migration_report.md") -> str:
        """生成迁移报告
        
        Args:
            legacy_files: 遗留文件列表
            output_file: 报告文件路径
            
        Returns:
            报告内容
        """
        report_lines = [
            "# 遗留代码迁移报告",
            "",
            f"迁移时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"迁移文件数: {len(legacy_files)}",
            "",
            "## 迁移详情",
            ""
        ]
        
        for legacy_file in legacy_files:
            try:
                config = self.analyzer.analyze_file(legacy_file)
                
                report_lines.extend([
                    f"### {os.path.basename(legacy_file)}",
                    "",
                    f"- **文件路径**: `{legacy_file}`",
                    f"- **缩放级别**: {config.get('zoom_level', 'N/A')}",
                    f"- **网格大小**: {config.get('grid_size', 'N/A')}",
                    f"- **输入文件**: {config.get('input_shapefile', 'N/A')}",
                    f"- **输出目录**: {config.get('output_dir', 'N/A')}",
                    ""
                ])
                
                code_analysis = config.get('code_analysis', {})
                if code_analysis:
                    report_lines.extend([
                        "**代码特性**:",
                        f"- 异步支持: {'是' if code_analysis.get('has_async') else '否'}",
                        f"- 缓存支持: {'是' if code_analysis.get('has_cache') else '否'}",
                        f"- 重试机制: {'是' if code_analysis.get('has_retry') else '否'}",
                        f"- 进度显示: {'是' if code_analysis.get('has_progress') else '否'}",
                        ""
                    ])
                
            except Exception as e:
                report_lines.extend([
                    f"### {os.path.basename(legacy_file)} (分析失败)",
                    "",
                    f"- **错误**: {str(e)}",
                    ""
                ])
        
        report_lines.extend([
            "## 迁移说明",
            "",
            "1. 迁移脚本使用新的RSDatasetGenerator架构",
            "2. 配置参数已自动转换为新格式",
            "3. 建议在使用前检查和调整配置参数",
            "4. 如有问题，请参考新架构的文档",
            ""
        ])
        
        report_content = "\n".join(report_lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return report_content


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="遗留代码迁移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python migrate_legacy.py getTiles-v5.py
  python migrate_legacy.py getTiles-yb-v1.py --advanced
  python migrate_legacy.py --directory legacy_code/
        """
    )
    
    parser.add_argument(
        'input',
        nargs='?',
        help='输入文件或目录路径'
    )
    
    parser.add_argument(
        '--directory', '-d',
        action='store_true',
        help='迁移整个目录'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='migrated',
        help='输出目录（默认: migrated）'
    )
    
    parser.add_argument(
        '--advanced', '-a',
        action='store_true',
        help='生成高级版本（包含监控和详细日志）'
    )
    
    parser.add_argument(
        '--pattern', '-p',
        default='*.py',
        help='文件匹配模式（默认: *.py）'
    )
    
    parser.add_argument(
        '--report', '-r',
        action='store_true',
        help='生成迁移报告'
    )
    
    args = parser.parse_args()
    
    # 检查输入
    if not args.input:
        # 尝试查找当前目录中的遗留文件
        legacy_candidates = ['getTiles-v5.py', 'getTiles-yb-v1.py']
        found_files = [f for f in legacy_candidates if os.path.exists(f)]
        
        if found_files:
            print("找到遗留文件:")
            for i, f in enumerate(found_files, 1):
                print(f"  {i}. {f}")
            
            try:
                choice = input("\n请选择要迁移的文件 (输入数字): ").strip()
                file_index = int(choice) - 1
                if 0 <= file_index < len(found_files):
                    args.input = found_files[file_index]
                else:
                    print("无效选择")
                    return
            except (ValueError, KeyboardInterrupt):
                print("操作取消")
                return
        else:
            parser.print_help()
            return
    
    # 创建迁移工具
    tool = MigrationTool()
    
    try:
        if args.directory or os.path.isdir(args.input):
            # 迁移目录
            print(f"迁移目录: {args.input}")
            migrated_files = tool.migrate_directory(
                args.input, 
                args.output, 
                args.pattern
            )
            
            if args.report:
                # 生成报告
                legacy_files = []
                import glob
                legacy_files = glob.glob(os.path.join(args.input, args.pattern))
                
                report_file = os.path.join(args.output, "migration_report.md")
                tool.generate_migration_report(legacy_files, report_file)
                print(f"迁移报告: {report_file}")
            
            print(f"\n迁移完成！共迁移 {len(migrated_files)} 个文件")
            
        else:
            # 迁移单个文件
            if not os.path.exists(args.input):
                print(f"文件不存在: {args.input}")
                return
            
            migrated_file = tool.migrate_file(
                args.input, 
                args.output, 
                args.advanced
            )
            
            if args.report:
                report_file = os.path.join(args.output, "migration_report.md")
                tool.generate_migration_report([args.input], report_file)
                print(f"迁移报告: {report_file}")
        
        print("\n使用说明:")
        print("1. 检查生成的迁移脚本中的配置参数")
        print("2. 确保输入文件路径正确")
        print("3. 运行迁移脚本测试功能")
        print("4. 如有问题，请参考新架构的文档")
        
    except Exception as e:
        print(f"迁移失败: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()