#!/usr/bin/env python3
import os
import sys
import json
import time
import logging
import argparse
import asyncio
import aiohttp
import mercantile
import geopandas as gpd
import psutil
from aiohttp import TCPConnector
from datetime import datetime
from collections import deque
from shapely.geometry import Point
from PIL import Image

# ========================
# 配置类
# ========================
class Config:
    def __init__(self, args):
        # 输入输出配置
        self.input_shp = args.input
        self.tile_dir = args.tile_dir
        self.output_dir = args.output_dir
        
        # 下载参数
        self.zoom = args.zoom
        self.grid_size = args.grid
        self.max_concurrency = args.threads
        self.request_timeout = args.timeout
        
        # 性能参数
        self.batch_size = args.batch
        self.stats_interval = args.stats_interval
        self.min_interval = args.min_interval
        self.max_interval = args.max_interval
        
        # 重试策略
        self.max_retries = args.retries
        self.backoff_base = args.backoff

# ========================
# 监控系统
# ========================
class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.monotonic()
        self.stats = {
            'total_tiles': 0,
            'success': 0,
            'failed': 0,
            'network_bytes': 0,
            'storage_writes': 0
        }
        self.mem_samples = deque(maxlen=60)
        
    def update(self, key, value=1):
        """更新统计指标"""
        if key in self.stats:
            self.stats[key] += value
        else:
            logging.warning(f"未知的监控指标: {key}")

    def record_memory(self):
        """记录内存使用"""
        proc = psutil.Process(os.getpid())
        self.mem_samples.append(proc.memory_info().rss)
        
    def generate_report(self):
        """生成报告（修复空序列问题）"""
        duration = time.monotonic() - self.start_time
        max_mem = max(self.mem_samples) if self.mem_samples else 0
        
        return (
            f"Tiles: {self.stats['success']} ok, {self.stats['failed']} failed | "
            f"Network: {self.stats['network_bytes']/(1024**2):.1f}MB | "
            f"Speed: {self.stats['success']/max(duration,1):.1f} tiles/s | "
            f"Memory: {max_mem/(1024**2):.1f}MB Peak"
        )
        
# ========================
# 核心下载器
# ========================
class TileDownloader:
    def __init__(self, config):
        self.config = config
        self.monitor = PerformanceMonitor()
        self.semaphore = asyncio.Semaphore(config.max_concurrency)
        self.validate_input()
        
    def validate_input(self):
        """校验输入Shapefile合法性"""
        required_files = ['.shp', '.shx', '.dbf']
        base, ext = os.path.splitext(self.config.input_shp)
        for suffix in required_files:
            if not os.path.exists(f"{base}{suffix}"):
                raise FileNotFoundError(f"缺少Shapefile必要文件: {base}{suffix}")
                
        gdf = gpd.read_file(self.config.input_shp)
        if 'osm_id' not in gdf.columns:
            raise ValueError("Shapefile必须包含osm_id字段")
        if not all(isinstance(g, Point) for g in gdf.geometry):
            raise ValueError("仅支持点要素几何类型")

    async def run(self):
        """主运行流程"""
        points = self.load_points()
        tiles = self.calculate_tiles(points)
        
        async with aiohttp.ClientSession(
            connector=TCPConnector(ssl=False),
            timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
        ) as session:
            await self.download_tiles(session, tiles)
            await self.process_points(points)
            
        logging.info("\n下载完成: %s", self.monitor.generate_report())

    def load_points(self):
        """加载采样点数据"""
        gdf = gpd.read_file(self.config.input_shp)
        return [{
            'id': str(row['osm_id']),
            'lon': row.geometry.x,
            'lat': row.geometry.y,
            'tile': mercantile.tile(row.geometry.x, row.geometry.y, self.config.zoom)
        } for _, row in gdf.iterrows()]

    def calculate_tiles(self, points):
        """计算所有需要下载的瓦片"""
        half = self.config.grid_size // 2
        tiles = set()
        
        for p in points:
            center = p['tile']
            for dx in range(-half, half+1):
                for dy in range(-half, half+1):
                    tx = center.x + dx
                    ty = center.y + dy
                    if 0 <= tx < (1 << self.config.zoom) and 0 <= ty < (1 << self.config.zoom):
                        tiles.add((tx, ty))
        return tiles

    async def download_tiles(self, session, tiles):
        """并发下载瓦片"""
        tasks = []
        for tx, ty in tiles:
            task = asyncio.create_task(
                self.download_single(session, tx, ty)
            )
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                self.monitor.update('failed')
            else:
                self.monitor.update('success')

    async def download_single(self, session, tx, ty, retry=0):
        """单个瓦片下载（含重试）"""
        async with self.semaphore:
            try:
                # 随机延迟防止封禁
                await asyncio.sleep(random.uniform(
                    self.config.min_interval, 
                    self.config.max_interval
                ))
                
                url = f"http://mt0.google.com/vt/lyrs=s&hl=en&x={tx}&y={ty}&z={self.config.zoom}"
                async with session.get(url) as resp:
                    data = await resp.read()
                    self.monitor.update('network_bytes', len(data))
                    
                    # 保存瓦片
                    path = os.path.join(
                        self.config.tile_dir,
                        f"tile_{self.config.zoom}_{tx}_{ty}.png"
                    )
                    with open(path, 'wb') as f:
                        f.write(data)
                    return True
                    
            except Exception as e:
                if retry < self.config.max_retries:
                    backoff = self.config.backoff_base ** retry
                    await asyncio.sleep(backoff)
                    return await self.download_single(session, tx, ty, retry+1)
                else:
                    logging.error("下载失败: %s", str(e))
                    return False

    async def process_points(self, points):
        """处理每个采样点的拼接"""
        for point in points:
            try:
                merged = await self.merge_tiles(point['tile'])
                self.save_output(point, merged)
            except Exception as e:
                logging.error("处理失败 %s: %s", point['id'], str(e))

    async def merge_tiles(self, center):
        """合并瓦片为完整图像"""
        half = self.config.grid_size // 2
        img_size = 256 * self.config.grid_size
        merged = Image.new('RGB', (img_size, img_size))
        
        for dx in range(-half, half+1):
            for dy in range(-half, half+1):
                tx = center.x + dx
                ty = center.y + dy
                path = os.path.join(
                    self.config.tile_dir,
                    f"tile_{self.config.zoom}_{tx}_{ty}.png"
                )
                
                if os.path.exists(path):
                    tile = Image.open(path)
                    x = (dx + half) * 256
                    y = (dy + half) * 256
                    merged.paste(tile, (x, y))
                    
        return merged

    def save_output(self, point, image):
        """保存结果和元数据"""
        filename = f"{point['id']}_{self.config.zoom}_{point['tile'].x}_{point['tile'].y}"
        
        # 保存图像
        image.save(os.path.join(self.config.output_dir, f"{filename}.png"))
        
        # 保存元数据
        meta = {
            "id": point['id'],
            "lon": point['lon'],
            "lat": point['lat'],
            "zoom": self.config.zoom,
            "tile_x": point['tile'].x,
            "tile_y": point['tile'].y,
            "grid_size": self.config.grid_size
        }
        with open(os.path.join(self.config.output_dir, f"{filename}.json"), 'w') as f:
            json.dump(meta, f, indent=2)

# ========================
# 命令行接口
# ========================
def parse_args():
    parser = argparse.ArgumentParser(description='高性能卫星影像下载器')
    
    # 必需参数
    parser.add_argument('--input', required=True, help='输入Shapefile路径')
    parser.add_argument('--tile-dir', required=True, help='瓦片存储目录')
    parser.add_argument('--output-dir', required=True, help='结果输出目录')
    
    # 下载参数
    parser.add_argument('--zoom', type=int, default=18, help='瓦片缩放级别')
    parser.add_argument('--grid', type=int, default=5, choices=[3,5,7,9], help='瓦片网格尺寸')
    parser.add_argument('--threads', type=int, default=8, help='最大并发线程数')
    parser.add_argument('--timeout', type=float, default=30.0, help='请求超时时间（秒）')
    
    # 性能参数
    parser.add_argument('--batch', type=int, default=500, help='存储批量大小')
    parser.add_argument('--stats-interval', type=float, default=5.0, help='状态报告间隔')
    parser.add_argument('--min-interval', type=float, default=0.3, help='最小请求间隔')
    parser.add_argument('--max-interval', type=float, default=1.2, help='最大请求间隔')
    
    # 重试策略
    parser.add_argument('--retries', type=int, default=3, help='最大重试次数')
    parser.add_argument('--backoff', type=float, default=2.0, help='退避基数')
    
    return parser.parse_args()

# ========================
# 主函数
# ========================
if __name__ == "__main__":
    # 初始化日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('download.log'),
            logging.StreamHandler()
        ]
    )
    
    try:
        args = parse_args()
        os.makedirs(args.tile_dir, exist_ok=True)
        os.makedirs(args.output_dir, exist_ok=True)
        
        downloader = TileDownloader(Config(args))
        asyncio.run(downloader.run())
        
    except Exception as e:
        logging.error("程序运行失败: %s", str(e))
        sys.exit(1)