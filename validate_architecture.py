#!/usr/bin/env python3
"""项目架构验证脚本

检查项目是否符合规范的架构设计，包括：
- 模块结构
- 代码质量
- 依赖关系
- 设计模式
- 文档完整性
"""

import os
import ast
import sys
import json
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """验证结果"""
    category: str
    item: str
    status: str  # 'pass', 'warning', 'error'
    message: str
    details: Optional[str] = None


class ArchitectureValidator:
    """架构验证器"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.results: List[ValidationResult] = []
        self.src_dir = self.project_root / 'src'
        
    def validate_all(self) -> List[ValidationResult]:
        """执行所有验证
        
        Returns:
            验证结果列表
        """
        self.results.clear()
        
        # 验证项目结构
        self._validate_project_structure()
        
        # 验证模块设计
        self._validate_module_design()
        
        # 验证代码质量
        self._validate_code_quality()
        
        # 验证依赖关系
        self._validate_dependencies()
        
        # 验证设计模式
        self._validate_design_patterns()
        
        # 验证文档
        self._validate_documentation()
        
        # 验证配置
        self._validate_configuration()
        
        return self.results
    
    def _add_result(self, category: str, item: str, status: str, 
                   message: str, details: Optional[str] = None):
        """添加验证结果"""
        self.results.append(ValidationResult(
            category=category,
            item=item,
            status=status,
            message=message,
            details=details
        ))
    
    def _validate_project_structure(self):
        """验证项目结构"""
        category = "项目结构"
        
        # 检查必需的目录
        required_dirs = [
            'src',
            'src/downloaders',
            'src/processors',
            'examples'
        ]
        
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if full_path.exists():
                self._add_result(category, f"目录 {dir_path}", "pass", "存在")
            else:
                self._add_result(category, f"目录 {dir_path}", "error", "缺失")
        
        # 检查必需的文件
        required_files = [
            'main.py',
            'requirements.txt',
            'config.yaml',
            'README.md',
            'src/__init__.py',
            'src/config.py',
            'src/utils.py',
            'src/rs_dataset_generator.py',
            'src/cli.py'
        ]
        
        for file_path in required_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                self._add_result(category, f"文件 {file_path}", "pass", "存在")
            else:
                self._add_result(category, f"文件 {file_path}", "error", "缺失")
        
        # 检查__init__.py文件
        init_files = [
            'src/__init__.py',
            'src/downloaders/__init__.py',
            'src/processors/__init__.py'
        ]
        
        for init_file in init_files:
            full_path = self.project_root / init_file
            if full_path.exists():
                self._add_result(category, f"初始化文件 {init_file}", "pass", "存在")
            else:
                self._add_result(category, f"初始化文件 {init_file}", "warning", "缺失")
    
    def _validate_module_design(self):
        """验证模块设计"""
        category = "模块设计"
        
        # 检查下载器模块
        downloader_files = [
            'src/downloaders/base.py',
            'src/downloaders/sync_downloader.py',
            'src/downloaders/async_downloader.py',
            'src/downloaders/factory.py'
        ]
        
        for file_path in downloader_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                self._add_result(category, f"下载器模块 {file_path}", "pass", "存在")
                self._validate_module_content(full_path, category)
            else:
                self._add_result(category, f"下载器模块 {file_path}", "error", "缺失")
        
        # 检查处理器模块
        processor_files = [
            'src/processors/data_loader.py',
            'src/processors/image_processor.py',
            'src/processors/metadata_manager.py',
            'src/processors/data_processor.py'
        ]
        
        for file_path in processor_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                self._add_result(category, f"处理器模块 {file_path}", "pass", "存在")
                self._validate_module_content(full_path, category)
            else:
                self._add_result(category, f"处理器模块 {file_path}", "error", "缺失")
    
    def _validate_module_content(self, file_path: Path, category: str):
        """验证模块内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析AST
            tree = ast.parse(content)
            
            # 检查文档字符串
            if ast.get_docstring(tree):
                self._add_result(category, f"模块文档 {file_path.name}", "pass", "有文档字符串")
            else:
                self._add_result(category, f"模块文档 {file_path.name}", "warning", "缺少文档字符串")
            
            # 检查类和函数
            classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            if classes:
                self._add_result(category, f"类定义 {file_path.name}", "pass", f"包含 {len(classes)} 个类")
                
                # 检查类的文档字符串
                for cls in classes:
                    if ast.get_docstring(cls):
                        self._add_result(category, f"类文档 {cls.name}", "pass", "有文档字符串")
                    else:
                        self._add_result(category, f"类文档 {cls.name}", "warning", "缺少文档字符串")
            
            if functions:
                # 检查公共函数的文档字符串
                public_functions = [f for f in functions if not f.name.startswith('_')]
                for func in public_functions:
                    if ast.get_docstring(func):
                        self._add_result(category, f"函数文档 {func.name}", "pass", "有文档字符串")
                    else:
                        self._add_result(category, f"函数文档 {func.name}", "warning", "缺少文档字符串")
        
        except Exception as e:
            self._add_result(category, f"模块解析 {file_path.name}", "error", f"解析失败: {str(e)}")
    
    def _validate_code_quality(self):
        """验证代码质量"""
        category = "代码质量"
        
        # 检查Python文件
        python_files = list(self.src_dir.rglob('*.py'))
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 检查编码声明
                if 'utf-8' in content[:100] or content.startswith('#!/usr/bin/env python3'):
                    self._add_result(category, f"编码声明 {py_file.name}", "pass", "正确")
                else:
                    self._add_result(category, f"编码声明 {py_file.name}", "warning", "建议添加编码声明")
                
                # 检查导入语句
                tree = ast.parse(content)
                imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
                
                if imports:
                    # 检查是否有相对导入
                    relative_imports = [imp for imp in imports if isinstance(imp, ast.ImportFrom) and imp.level > 0]
                    if relative_imports:
                        self._add_result(category, f"导入语句 {py_file.name}", "pass", "使用相对导入")
                    else:
                        self._add_result(category, f"导入语句 {py_file.name}", "warning", "建议使用相对导入")
                
                # 检查异常处理
                try_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
                if try_nodes:
                    self._add_result(category, f"异常处理 {py_file.name}", "pass", f"包含 {len(try_nodes)} 个异常处理块")
                
                # 检查类型注解
                functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                annotated_functions = [f for f in functions if f.returns or any(arg.annotation for arg in f.args.args)]
                
                if annotated_functions and len(annotated_functions) > len(functions) * 0.5:
                    self._add_result(category, f"类型注解 {py_file.name}", "pass", "大部分函数有类型注解")
                elif annotated_functions:
                    self._add_result(category, f"类型注解 {py_file.name}", "warning", "部分函数有类型注解")
                else:
                    self._add_result(category, f"类型注解 {py_file.name}", "warning", "缺少类型注解")
            
            except Exception as e:
                self._add_result(category, f"代码分析 {py_file.name}", "error", f"分析失败: {str(e)}")
    
    def _validate_dependencies(self):
        """验证依赖关系"""
        category = "依赖关系"
        
        # 检查requirements.txt
        req_file = self.project_root / 'requirements.txt'
        if req_file.exists():
            with open(req_file, 'r', encoding='utf-8') as f:
                requirements = f.read().strip().split('\n')
            
            # 检查核心依赖
            core_deps = ['geopandas', 'Pillow', 'requests', 'aiohttp', 'pyyaml']
            for dep in core_deps:
                if any(dep.lower() in req.lower() for req in requirements):
                    self._add_result(category, f"核心依赖 {dep}", "pass", "已包含")
                else:
                    self._add_result(category, f"核心依赖 {dep}", "warning", "未找到")
            
            # 检查版本固定
            versioned_deps = [req for req in requirements if '==' in req or '>=' in req]
            if len(versioned_deps) > len(requirements) * 0.7:
                self._add_result(category, "版本管理", "pass", "大部分依赖有版本约束")
            else:
                self._add_result(category, "版本管理", "warning", "建议为更多依赖添加版本约束")
        
        # 检查循环依赖
        self._check_circular_dependencies()
    
    def _check_circular_dependencies(self):
        """检查循环依赖"""
        category = "依赖关系"
        
        # 简单的循环依赖检查
        python_files = list(self.src_dir.rglob('*.py'))
        import_graph = {}
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                imports = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if node.module.startswith('src.'):
                            imports.append(node.module)
                
                module_name = str(py_file.relative_to(self.project_root)).replace('/', '.').replace('.py', '')
                import_graph[module_name] = imports
            
            except Exception:
                continue
        
        # 检查是否有明显的循环依赖
        has_cycles = False
        for module, deps in import_graph.items():
            for dep in deps:
                if dep in import_graph and module in import_graph[dep]:
                    has_cycles = True
                    self._add_result(category, "循环依赖", "warning", f"发现循环依赖: {module} <-> {dep}")
        
        if not has_cycles:
            self._add_result(category, "循环依赖", "pass", "未发现明显的循环依赖")
    
    def _validate_design_patterns(self):
        """验证设计模式"""
        category = "设计模式"
        
        # 检查工厂模式
        factory_file = self.src_dir / 'downloaders' / 'factory.py'
        if factory_file.exists():
            self._add_result(category, "工厂模式", "pass", "下载器工厂已实现")
        else:
            self._add_result(category, "工厂模式", "warning", "未找到工厂模式实现")
        
        # 检查策略模式
        base_downloader = self.src_dir / 'downloaders' / 'base.py'
        if base_downloader.exists():
            try:
                with open(base_downloader, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'ABC' in content or 'abstractmethod' in content:
                    self._add_result(category, "策略模式", "pass", "抽象基类已定义")
                else:
                    self._add_result(category, "策略模式", "warning", "建议使用抽象基类")
            except Exception:
                pass
        
        # 检查单例模式（配置管理）
        config_file = self.src_dir / 'config.py'
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'singleton' in content.lower() or '_instance' in content:
                    self._add_result(category, "单例模式", "pass", "配置管理使用单例模式")
                else:
                    self._add_result(category, "单例模式", "warning", "配置管理建议使用单例模式")
            except Exception:
                pass
        
        # 检查观察者模式（进度报告）
        utils_file = self.src_dir / 'utils.py'
        if utils_file.exists():
            try:
                with open(utils_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'ProgressReporter' in content or 'Observer' in content:
                    self._add_result(category, "观察者模式", "pass", "进度报告使用观察者模式")
                else:
                    self._add_result(category, "观察者模式", "warning", "建议为进度报告使用观察者模式")
            except Exception:
                pass
    
    def _validate_documentation(self):
        """验证文档"""
        category = "文档"
        
        # 检查README.md
        readme_file = self.project_root / 'README.md'
        if readme_file.exists():
            with open(readme_file, 'r', encoding='utf-8') as f:
                readme_content = f.read()
            
            # 检查README内容
            required_sections = ['安装', '使用', '配置', '示例']
            for section in required_sections:
                if section in readme_content:
                    self._add_result(category, f"README {section}章节", "pass", "存在")
                else:
                    self._add_result(category, f"README {section}章节", "warning", "缺失")
            
            if len(readme_content) > 1000:
                self._add_result(category, "README详细程度", "pass", "内容详细")
            else:
                self._add_result(category, "README详细程度", "warning", "内容较简单")
        else:
            self._add_result(category, "README文件", "error", "缺失")
        
        # 检查示例文件
        examples_dir = self.project_root / 'examples'
        if examples_dir.exists():
            example_files = list(examples_dir.glob('*.py'))
            if example_files:
                self._add_result(category, "示例代码", "pass", f"包含 {len(example_files)} 个示例")
            else:
                self._add_result(category, "示例代码", "warning", "缺少示例代码")
        else:
            self._add_result(category, "示例目录", "warning", "缺失")
    
    def _validate_configuration(self):
        """验证配置"""
        category = "配置管理"
        
        # 检查配置文件
        config_file = self.project_root / 'config.yaml'
        if config_file.exists():
            try:
                import yaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                
                # 检查配置结构
                required_sections = ['download', 'paths', 'network', 'image', 'logging']
                for section in required_sections:
                    if section in config_data:
                        self._add_result(category, f"配置节 {section}", "pass", "存在")
                    else:
                        self._add_result(category, f"配置节 {section}", "warning", "缺失")
                
                self._add_result(category, "配置文件格式", "pass", "YAML格式正确")
            
            except Exception as e:
                self._add_result(category, "配置文件格式", "error", f"YAML格式错误: {str(e)}")
        else:
            self._add_result(category, "配置文件", "warning", "缺失默认配置文件")
        
        # 检查配置管理模块
        config_module = self.src_dir / 'config.py'
        if config_module.exists():
            self._add_result(category, "配置管理模块", "pass", "存在")
        else:
            self._add_result(category, "配置管理模块", "error", "缺失")
    
    def generate_report(self, output_file: str = "architecture_report.md") -> str:
        """生成验证报告
        
        Args:
            output_file: 输出文件路径
            
        Returns:
            报告内容
        """
        # 统计结果
        total = len(self.results)
        passed = len([r for r in self.results if r.status == 'pass'])
        warnings = len([r for r in self.results if r.status == 'warning'])
        errors = len([r for r in self.results if r.status == 'error'])
        
        # 计算分数
        score = (passed * 100 + warnings * 50) / (total * 100) if total > 0 else 0
        
        # 生成报告
        report_lines = [
            "# 项目架构验证报告",
            "",
            f"验证时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"项目路径: {self.project_root}",
            "",
            "## 总体评分",
            "",
            f"**架构评分: {score:.1f}/100**",
            "",
            f"- ✅ 通过: {passed}",
            f"- ⚠️ 警告: {warnings}",
            f"- ❌ 错误: {errors}",
            f"- 📊 总计: {total}",
            ""
        ]
        
        # 按类别分组
        categories = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)
        
        # 生成详细报告
        for category, results in categories.items():
            report_lines.extend([
                f"## {category}",
                ""
            ])
            
            for result in results:
                status_icon = {
                    'pass': '✅',
                    'warning': '⚠️',
                    'error': '❌'
                }.get(result.status, '❓')
                
                report_lines.append(f"- {status_icon} **{result.item}**: {result.message}")
                if result.details:
                    report_lines.append(f"  - {result.details}")
            
            report_lines.append("")
        
        # 添加建议
        if errors > 0:
            report_lines.extend([
                "## 🚨 紧急修复建议",
                "",
                "以下问题需要立即修复：",
                ""
            ])
            
            for result in self.results:
                if result.status == 'error':
                    report_lines.append(f"- **{result.item}**: {result.message}")
            
            report_lines.append("")
        
        if warnings > 0:
            report_lines.extend([
                "## 💡 改进建议",
                "",
                "以下问题建议改进：",
                ""
            ])
            
            for result in self.results:
                if result.status == 'warning':
                    report_lines.append(f"- **{result.item}**: {result.message}")
            
            report_lines.append("")
        
        # 添加最佳实践建议
        report_lines.extend([
            "## 📋 架构最佳实践检查清单",
            "",
            "### 模块化设计",
            "- [ ] 单一职责原则：每个模块只负责一个功能",
            "- [ ] 开闭原则：对扩展开放，对修改封闭",
            "- [ ] 依赖倒置：依赖抽象而不是具体实现",
            "",
            "### 代码质量",
            "- [ ] 类型注解：为函数参数和返回值添加类型注解",
            "- [ ] 文档字符串：为所有公共类和函数添加文档",
            "- [ ] 异常处理：适当的异常处理和错误信息",
            "- [ ] 单元测试：为核心功能编写测试",
            "",
            "### 性能优化",
            "- [ ] 异步支持：I/O密集型操作使用异步",
            "- [ ] 缓存机制：合理使用缓存减少重复计算",
            "- [ ] 资源管理：正确管理文件句柄和网络连接",
            "- [ ] 内存优化：避免内存泄漏和过度使用",
            "",
            "### 可维护性",
            "- [ ] 配置管理：外部化配置参数",
            "- [ ] 日志记录：完善的日志记录机制",
            "- [ ] 错误处理：友好的错误信息和恢复机制",
            "- [ ] 版本管理：清晰的版本控制和发布流程",
            ""
        ])
        
        report_content = "\n".join(report_lines)
        
        # 保存报告
        output_path = self.project_root / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return report_content


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="项目架构验证工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python validate_architecture.py
  python validate_architecture.py --project /path/to/project
  python validate_architecture.py --output custom_report.md
        """
    )
    
    parser.add_argument(
        '--project', '-p',
        default='.',
        help='项目根目录路径（默认: 当前目录）'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='architecture_report.md',
        help='输出报告文件名（默认: architecture_report.md）'
    )
    
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='同时输出JSON格式的结果'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细输出'
    )
    
    args = parser.parse_args()
    
    # 验证项目路径
    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"错误: 项目路径不存在: {project_path}")
        sys.exit(1)
    
    print(f"正在验证项目架构: {project_path}")
    print("=" * 50)
    
    # 创建验证器并执行验证
    validator = ArchitectureValidator(str(project_path))
    results = validator.validate_all()
    
    # 统计结果
    total = len(results)
    passed = len([r for r in results if r.status == 'pass'])
    warnings = len([r for r in results if r.status == 'warning'])
    errors = len([r for r in results if r.status == 'error'])
    
    # 显示摘要
    print(f"验证完成！")
    print(f"✅ 通过: {passed}")
    print(f"⚠️ 警告: {warnings}")
    print(f"❌ 错误: {errors}")
    print(f"📊 总计: {total}")
    
    # 计算分数
    score = (passed * 100 + warnings * 50) / (total * 100) if total > 0 else 0
    print(f"\n🏆 架构评分: {score:.1f}/100")
    
    # 显示详细结果
    if args.verbose:
        print("\n详细结果:")
        print("-" * 50)
        
        current_category = None
        for result in results:
            if result.category != current_category:
                current_category = result.category
                print(f"\n{current_category}:")
            
            status_icon = {
                'pass': '✅',
                'warning': '⚠️',
                'error': '❌'
            }.get(result.status, '❓')
            
            print(f"  {status_icon} {result.item}: {result.message}")
            if result.details:
                print(f"     {result.details}")
    
    # 生成报告
    print(f"\n正在生成报告: {args.output}")
    validator.generate_report(args.output)
    
    # 输出JSON格式
    if args.json:
        json_file = args.output.replace('.md', '.json')
        json_data = {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'project_path': str(project_path),
            'summary': {
                'total': total,
                'passed': passed,
                'warnings': warnings,
                'errors': errors,
                'score': score
            },
            'results': [
                {
                    'category': r.category,
                    'item': r.item,
                    'status': r.status,
                    'message': r.message,
                    'details': r.details
                }
                for r in results
            ]
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        print(f"JSON报告已保存: {json_file}")
    
    print(f"\n报告已保存: {args.output}")
    
    # 根据结果设置退出码
    if errors > 0:
        print("\n⚠️ 发现严重问题，请查看报告并修复")
        sys.exit(1)
    elif warnings > 0:
        print("\n💡 发现改进建议，请查看报告")
        sys.exit(0)
    else:
        print("\n🎉 架构验证通过！")
        sys.exit(0)


if __name__ == '__main__':
    main()