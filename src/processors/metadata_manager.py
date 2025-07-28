"""元数据管理模块

提供元数据的创建、保存和管理功能。
支持多种格式的元数据输出。
"""

import json
import os
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from .image_processor import ImageMetadata
from .data_loader import GeoPoint
from ..utils import DataProcessingError, ensure_directory


@dataclass
class ProcessingStats:
    """处理统计信息"""
    total_points: int
    successful_points: int
    failed_points: int
    total_tiles: int
    successful_tiles: int
    failed_tiles: int
    processing_time: float
    start_time: str
    end_time: str
    
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_points == 0:
            return 0.0
        return self.successful_points / self.total_points * 100
    
    def tile_success_rate(self) -> float:
        """计算瓦片成功率"""
        if self.total_tiles == 0:
            return 0.0
        return self.successful_tiles / self.total_tiles * 100


@dataclass
class DatasetMetadata:
    """数据集元数据"""
    dataset_name: str
    creation_time: str
    source_file: str
    output_directory: str
    zoom_level: int
    grid_size: int
    tile_size: int
    total_images: int
    processing_stats: ProcessingStats
    config_snapshot: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class MetadataManager:
    """元数据管理器
    
    负责管理和保存各种元数据信息。
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = config.logger
        self.output_dir = Path(config.paths.output_dir)
        
        # 确保输出目录存在
        ensure_directory(str(self.output_dir))
    
    def save_image_metadata(self, metadata: ImageMetadata, point_index: int, 
                          output_format: str = 'json') -> str:
        """保存图像元数据
        
        Args:
            metadata: 图像元数据
            point_index: 点索引
            output_format: 输出格式 ('json', 'yaml', 'xml')
            
        Returns:
            保存的文件路径
        """
        filename = f"point_{point_index:06d}_metadata.{output_format}"
        file_path = self.output_dir / filename
        
        try:
            if output_format.lower() == 'json':
                self._save_json_metadata(metadata, file_path)
            elif output_format.lower() == 'yaml':
                self._save_yaml_metadata(metadata, file_path)
            elif output_format.lower() == 'xml':
                self._save_xml_metadata(metadata, file_path)
            else:
                raise ValueError(f"不支持的元数据格式: {output_format}")
            
            self.logger.debug(f"保存图像元数据: {file_path}")
            return str(file_path)
            
        except Exception as e:
            raise DataProcessingError(f"保存图像元数据失败: {str(e)}")
    
    def _save_json_metadata(self, metadata: ImageMetadata, file_path: Path):
        """保存JSON格式元数据"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _save_yaml_metadata(self, metadata: ImageMetadata, file_path: Path):
        """保存YAML格式元数据"""
        try:
            import yaml
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(metadata.to_dict(), f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
        except ImportError:
            raise DataProcessingError("需要安装PyYAML库来支持YAML格式")
    
    def _save_xml_metadata(self, metadata: ImageMetadata, file_path: Path):
        """保存XML格式元数据"""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.Element("ImageMetadata")
            
            # 基本信息
            basic_info = ET.SubElement(root, "BasicInfo")
            ET.SubElement(basic_info, "Width").text = str(metadata.width)
            ET.SubElement(basic_info, "Height").text = str(metadata.height)
            ET.SubElement(basic_info, "ZoomLevel").text = str(metadata.zoom_level)
            ET.SubElement(basic_info, "TileSize").text = str(metadata.tile_size)
            ET.SubElement(basic_info, "GridSize").text = str(metadata.grid_size)
            
            # 中心点
            center_point = ET.SubElement(root, "CenterPoint")
            ET.SubElement(center_point, "Longitude").text = str(metadata.center_point.longitude)
            ET.SubElement(center_point, "Latitude").text = str(metadata.center_point.latitude)
            ET.SubElement(center_point, "Index").text = str(metadata.center_point.index)
            
            # 边界
            bounds = ET.SubElement(root, "Bounds")
            for key, value in metadata.bounds.items():
                ET.SubElement(bounds, key).text = str(value)
            
            # 像素坐标
            pixel_coords = ET.SubElement(root, "PixelCoordinates")
            for coord in metadata.pixel_coordinates:
                coord_elem = ET.SubElement(pixel_coords, "Coordinate")
                for key, value in coord.items():
                    ET.SubElement(coord_elem, key).text = str(value)
            
            # 保存文件
            tree = ET.ElementTree(root)
            tree.write(file_path, encoding='utf-8', xml_declaration=True)
            
        except Exception as e:
            raise DataProcessingError(f"保存XML元数据失败: {str(e)}")
    
    def create_dataset_summary(self, points: List[GeoPoint], 
                             processing_stats: ProcessingStats,
                             config_snapshot: Dict[str, Any]) -> DatasetMetadata:
        """创建数据集摘要
        
        Args:
            points: 处理的地理点列表
            processing_stats: 处理统计信息
            config_snapshot: 配置快照
            
        Returns:
            数据集元数据
        """
        dataset_name = f"rs_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return DatasetMetadata(
            dataset_name=dataset_name,
            creation_time=datetime.now().isoformat(),
            source_file=config_snapshot.get('input_file', ''),
            output_directory=str(self.output_dir),
            zoom_level=config_snapshot.get('zoom_level', 0),
            grid_size=config_snapshot.get('grid_size', 0),
            tile_size=256,
            total_images=len(points),
            processing_stats=processing_stats,
            config_snapshot=config_snapshot
        )
    
    def save_dataset_summary(self, dataset_metadata: DatasetMetadata) -> str:
        """保存数据集摘要
        
        Args:
            dataset_metadata: 数据集元数据
            
        Returns:
            保存的文件路径
        """
        summary_file = self.output_dir / "dataset_summary.json"
        
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(dataset_metadata.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"保存数据集摘要: {summary_file}")
            return str(summary_file)
            
        except Exception as e:
            raise DataProcessingError(f"保存数据集摘要失败: {str(e)}")
    
    def create_coordinate_mapping(self, image_metadatas: List[ImageMetadata]) -> str:
        """创建坐标映射文件
        
        Args:
            image_metadatas: 图像元数据列表
            
        Returns:
            保存的文件路径
        """
        mapping_file = self.output_dir / "coordinate_mapping.json"
        
        try:
            # 创建坐标映射
            coordinate_mapping = {
                'total_points': len(image_metadatas),
                'mappings': []
            }
            
            for i, metadata in enumerate(image_metadatas):
                for coord_info in metadata.pixel_coordinates:
                    mapping_entry = {
                        'image_index': i,
                        'image_file': f"point_{coord_info['point_index']:06d}.png",
                        'point_index': coord_info['point_index'],
                        'geo_coordinates': {
                            'longitude': coord_info['longitude'],
                            'latitude': coord_info['latitude']
                        },
                        'pixel_coordinates': {
                            'x': coord_info['pixel_x'],
                            'y': coord_info['pixel_y']
                        },
                        'properties': coord_info.get('properties', {})
                    }
                    coordinate_mapping['mappings'].append(mapping_entry)
            
            # 保存文件
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(coordinate_mapping, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"创建坐标映射文件: {mapping_file}")
            return str(mapping_file)
            
        except Exception as e:
            raise DataProcessingError(f"创建坐标映射文件失败: {str(e)}")
    
    def export_to_csv(self, image_metadatas: List[ImageMetadata]) -> str:
        """导出为CSV格式
        
        Args:
            image_metadatas: 图像元数据列表
            
        Returns:
            保存的文件路径
        """
        csv_file = self.output_dir / "dataset_export.csv"
        
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 写入表头
                headers = [
                    'image_file', 'point_index', 'longitude', 'latitude',
                    'pixel_x', 'pixel_y', 'image_width', 'image_height',
                    'zoom_level', 'grid_size', 'min_lon', 'min_lat',
                    'max_lon', 'max_lat'
                ]
                writer.writerow(headers)
                
                # 写入数据
                for i, metadata in enumerate(image_metadatas):
                    for coord_info in metadata.pixel_coordinates:
                        row = [
                            f"point_{coord_info['point_index']:06d}.png",
                            coord_info['point_index'],
                            coord_info['longitude'],
                            coord_info['latitude'],
                            coord_info['pixel_x'],
                            coord_info['pixel_y'],
                            metadata.width,
                            metadata.height,
                            metadata.zoom_level,
                            metadata.grid_size,
                            metadata.bounds['min_lon'],
                            metadata.bounds['min_lat'],
                            metadata.bounds['max_lon'],
                            metadata.bounds['max_lat']
                        ]
                        writer.writerow(row)
            
            self.logger.info(f"导出CSV文件: {csv_file}")
            return str(csv_file)
            
        except Exception as e:
            raise DataProcessingError(f"导出CSV文件失败: {str(e)}")
    
    def create_processing_report(self, processing_stats: ProcessingStats, 
                               config_snapshot: Dict[str, Any]) -> str:
        """创建处理报告
        
        Args:
            processing_stats: 处理统计信息
            config_snapshot: 配置快照
            
        Returns:
            保存的文件路径
        """
        report_file = self.output_dir / "processing_report.txt"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("遥感数据集生成报告\n")
                f.write("=" * 50 + "\n\n")
                
                # 基本信息
                f.write("基本信息:\n")
                f.write("-" * 20 + "\n")
                f.write(f"开始时间: {processing_stats.start_time}\n")
                f.write(f"结束时间: {processing_stats.end_time}\n")
                f.write(f"处理时长: {processing_stats.processing_time:.2f} 秒\n")
                f.write(f"输出目录: {self.output_dir}\n\n")
                
                # 配置信息
                f.write("配置信息:\n")
                f.write("-" * 20 + "\n")
                f.write(f"输入文件: {config_snapshot.get('input_file', 'N/A')}\n")
                f.write(f"缩放级别: {config_snapshot.get('zoom_level', 'N/A')}\n")
                f.write(f"网格大小: {config_snapshot.get('grid_size', 'N/A')}\n")
                f.write(f"最大并发数: {config_snapshot.get('max_concurrency', 'N/A')}\n")
                f.write(f"下载器类型: {config_snapshot.get('downloader_type', 'N/A')}\n\n")
                
                # 处理统计
                f.write("处理统计:\n")
                f.write("-" * 20 + "\n")
                f.write(f"总点数: {processing_stats.total_points}\n")
                f.write(f"成功处理: {processing_stats.successful_points}\n")
                f.write(f"处理失败: {processing_stats.failed_points}\n")
                f.write(f"成功率: {processing_stats.success_rate():.2f}%\n\n")
                
                # 瓦片统计
                f.write("瓦片统计:\n")
                f.write("-" * 20 + "\n")
                f.write(f"总瓦片数: {processing_stats.total_tiles}\n")
                f.write(f"成功下载: {processing_stats.successful_tiles}\n")
                f.write(f"下载失败: {processing_stats.failed_tiles}\n")
                f.write(f"下载成功率: {processing_stats.tile_success_rate():.2f}%\n\n")
                
                # 性能指标
                if processing_stats.processing_time > 0:
                    points_per_second = processing_stats.successful_points / processing_stats.processing_time
                    tiles_per_second = processing_stats.successful_tiles / processing_stats.processing_time
                    
                    f.write("性能指标:\n")
                    f.write("-" * 20 + "\n")
                    f.write(f"点处理速度: {points_per_second:.2f} 点/秒\n")
                    f.write(f"瓦片下载速度: {tiles_per_second:.2f} 瓦片/秒\n")
            
            self.logger.info(f"创建处理报告: {report_file}")
            return str(report_file)
            
        except Exception as e:
            raise DataProcessingError(f"创建处理报告失败: {str(e)}")
    
    def cleanup_temp_files(self, keep_cache: bool = False):
        """清理临时文件
        
        Args:
            keep_cache: 是否保留缓存文件
        """
        try:
            if not keep_cache:
                cache_dir = self.output_dir / "cache"
                if cache_dir.exists():
                    import shutil
                    shutil.rmtree(cache_dir)
                    self.logger.info("清理缓存文件")
            
            # 清理其他临时文件
            temp_patterns = ['*.tmp', '*.temp', '.DS_Store']
            for pattern in temp_patterns:
                for temp_file in self.output_dir.glob(pattern):
                    temp_file.unlink()
                    self.logger.debug(f"删除临时文件: {temp_file}")
                    
        except Exception as e:
            self.logger.warning(f"清理临时文件时出错: {str(e)}")