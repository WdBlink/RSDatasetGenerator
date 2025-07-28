import os
import json
import time
import random
import requests
import mercantile
import geopandas as gpd
from PIL import Image
from io import BytesIO

# 用户输入区域
shapefile_path = '/Users/tanjunxiang/Desktop/Tiles/temp_gansu.shp'
tile_zoom = 18
tile_grid_size = 9  # 必须是奇数，如 3、5、7、9
request_interval_range = (0.1, 0.3)  # 请求间隔范围（秒）
retry_wait_range = (6, 10)        # 请求失败后的等待时间范围（秒）

tile_save_dir = '/Users/tanjunxiang/Desktop/Tiles/9/small_tiles'
merged_save_dir = '/Users/tanjunxiang/Desktop/Tiles/9/merged_tiles'
os.makedirs(tile_save_dir, exist_ok=True)
os.makedirs(merged_save_dir, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

gdf = gpd.read_file(shapefile_path)

tile_cache = {}
points_info = []
half = tile_grid_size // 2
for idx, row in gdf.iterrows():
    lon, lat = row.geometry.x, row.geometry.y
    tile = mercantile.tile(lon, lat, tile_zoom)
    points_info.append({
        'id': str(row['osm_id']),
        'lon': lon,
        'lat': lat,
        'tile': tile
    })

tile_to_points = {}
for info in points_info:
    center_tile = info['tile']
    for dx in range(-half, half + 1):
        for dy in range(-half, half + 1):
            t = mercantile.Tile(center_tile.x + dx, center_tile.y + dy, tile_zoom)
            key = (t.x, t.y, t.z)
            tile_to_points.setdefault(key, []).append(info)

used_centers = set()
downloaded_tile_count = 0

total_points = len(points_info)
processed_count = 0

for info in points_info:
    point_id = info['id']
    lon, lat = info['lon'], info['lat']
    center_tile = info['tile']
    center_key = (center_tile.x, center_tile.y, center_tile.z)

    if center_key in used_centers:
        continue
    used_centers.add(center_key)
    processed_count += 1

    start_time = time.time()
    tiles = {}
    tile_used_this_image = 0

    for dx in range(-half, half + 1):
        for dy in range(-half, half + 1):
            tx = center_tile.x + dx
            ty = center_tile.y + dy
            key = (tx, ty, tile_zoom)

            if key in tile_cache:
                tiles[(dx + half, dy + half)] = tile_cache[key]
                tile_used_this_image += 1
                continue

            url = f"http://mt0.google.com/vt/lyrs=s&hl=en&x={tx}&y={ty}&z={tile_zoom}"
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content)).convert('RGB')
                tiles[(dx + half, dy + half)] = img
                tile_cache[key] = img
                downloaded_tile_count += 1
                tile_used_this_image += 1

                tile_filename = f"tile_{tile_zoom}_{tx}_{ty}.png"
                tile_path = os.path.join(tile_save_dir, tile_filename)
                img.save(tile_path)

                time.sleep(random.uniform(*request_interval_range))
            except requests.RequestException as e:
                print(f"[错误] 下载瓦片失败: x={tx}, y={ty}, z={tile_zoom}，错误信息: {e}")
                time.sleep(random.uniform(*retry_wait_range))
                continue

    if len(tiles) != tile_grid_size ** 2:
        print(f"[警告] 中心点 {point_id} 拼图瓦片缺失（{len(tiles)}/{tile_grid_size**2}），跳过。")
        continue

    full_img = Image.new('RGB', (256 * tile_grid_size, 256 * tile_grid_size))
    for (i, j), im in tiles.items():
        full_img.paste(im, (i * 256, j * 256))

    # 新文件名使用 osm_id + zoom + x + y
    merged_filename = f"{point_id}_{tile_zoom}_{center_tile.x}_{center_tile.y}.png"
    merged_path = os.path.join(merged_save_dir, merged_filename)
    full_img.save(merged_path)

    annotation = {
        "image": merged_filename,
        "tile_center": {
            "z": center_tile.z,
            "x": center_tile.x,
            "y": center_tile.y
        },
        "points": []
    }

    bounds = mercantile.bounds(center_tile)
    full_west = bounds.west - half * (bounds.east - bounds.west)
    full_north = bounds.north + half * (bounds.north - bounds.south)
    res_x = (bounds.east - bounds.west) / 256
    res_y = (bounds.north - bounds.south) / 256

    for p in tile_to_points.get(center_key, []):
        px = round((p['lon'] - full_west) / res_x)
        py = round((full_north - p['lat']) / res_y)

        if 0 <= px < full_img.width and 0 <= py < full_img.height:
            annotation["points"].append({
                "id": p['id'],
                "pixel_x": px,
                "pixel_y": py
            })

    json_name = merged_filename.replace('.png', '.json')
    json_path = os.path.join(merged_save_dir, json_name)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(annotation, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - start_time
    print(f"[{processed_count}/{total_points}] 已处理中心点 {point_id}，耗时：{elapsed:.2f} 秒，"
          f"使用瓦片数：{tile_used_this_image}，已下载瓦片总数：{downloaded_tile_count}")

print("\n✅ 所有处理完成！")
