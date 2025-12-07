# File: storm_pipeline/storm_monitor.py
# PHÁT HIỆN BÃO TỪ DỮ LIỆU NOAA GFS (KHÔNG DÙNG JMA)

import xarray as xr
import numpy as np
import glob
import os
from datetime import datetime

def detect_low_pressure_centers(pressure_data, lat_data, lon_data, threshold=1016):
    """Phát hiện các tâm áp thấp từ dữ liệu áp suất."""
    storms = []
    
    # Chuyển đổi từ Pascal (Pa) sang hectoPascal (hPa) nếu cần
    if pressure_data.max() > 20000: # Ngưỡng an toàn, nếu áp suất > 20000 Pa thì chắc chắn là Pa
        pressure_data = pressure_data / 100
    
    height, width = pressure_data.shape
    
    # Bỏ qua các cạnh để tránh lỗi index
    for i in range(2, height-2):
        for j in range(2, width-2):
            center_pressure = pressure_data[i, j]
            
            # So sánh với 8 điểm xung quanh
            surrounding = [
                pressure_data[i-1, j-1], pressure_data[i-1, j], pressure_data[i-1, j+1],
                pressure_data[i, j-1],                       pressure_data[i, j+1],
                pressure_data[i+1, j-1], pressure_data[i+1, j], pressure_data[i+1, j+1]
            ]
            
            # Điều kiện 1: Áp suất trung tâm phải thấp hơn ngưỡng (đã tăng lên 1016)
            # Điều kiện 2: Phải là điểm có áp suất thấp nhất trong vùng lân cận (local minimum)
            if center_pressure < threshold and all(center_pressure < p for p in surrounding):
                # Kiểm tra độ dốc áp suất trong khu vực 5x5
                region = pressure_data[i-2:i+3, j-2:j+3]
                avg_pressure = np.mean(region)
                
                # Điều kiện 3: Chênh lệch áp suất phải đủ lớn (đã giảm xuống > 2)
                # để loại bỏ các vùng nhiễu động nhỏ, không đáng kể.
                if center_pressure - avg_pressure < -2: # Chênh lệch > 2 hPa so với trung bình khu vực
                    storms.append({
                        'lat': float(lat_data[i]),
                        'lon': float(lon_data[j]),
                        'pressure': float(center_pressure),
                        'avg_regional_pressure': float(avg_pressure)
                    })
    
    return storms

def analyze_wind_speed(u_wind, v_wind, lat_idx, lon_idx, radius=3):
    """Tính tốc độ gió xung quanh tâm áp thấp."""
    try:
        u_region = u_wind[lat_idx-radius:lat_idx+radius+1, lon_idx-radius:lon_idx+radius+1]
        v_region = v_wind[lat_idx-radius:lat_idx+radius+1, lon_idx-radius:lon_idx+radius+1]
        
        wind_speed = np.sqrt(u_region**2 + v_region**2)
        max_wind = float(np.max(wind_speed))
        avg_wind = float(np.mean(wind_speed))
        
        return max_wind, avg_wind
    except:
        return 0.0, 0.0

def classify_storm(pressure, max_wind_ms):
    """Phân loại cường độ bão."""
    max_wind_knots = max_wind_ms * 1.944
    
    if pressure >= 1000 or max_wind_knots < 34:
        return "Tropical Depression"
    elif max_wind_knots < 64:
        return "Tropical Storm"
    elif max_wind_knots < 83:
        return "Typhoon (Category 1)"
    elif max_wind_knots < 96:
        return "Typhoon (Category 2)"
    elif max_wind_knots < 113:
        return "Typhoon (Category 3)"
    elif max_wind_knots < 137:
        return "Typhoon (Category 4)"
    else:
        return "Super Typhoon (Category 5)"

def check_for_storm():
    """Kiểm tra bão từ dữ liệu GFS NOAA mới nhất."""
    print(f"\n{'='*60}")
    print(f"🔍 PHÁT HIỆN BÃO TỪ DỮ LIỆU NOAA GFS")
    print(f"Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        data_dir = "data"
        pattern = os.path.join(data_dir, "*_f000.grib2")
        files = glob.glob(pattern)
        
        if not files:
            pattern = os.path.join(data_dir, "*.grib2")
            files = glob.glob(pattern)
        
        if not files:
            print("❌ Không tìm thấy dữ liệu GFS")
            return None
        
        latest_file = max(files, key=lambda p: os.path.getmtime(p))
        print(f"📂 Đang phân tích: {os.path.basename(latest_file)}")
        
        try:
            ds = xr.open_dataset(
                latest_file,
                engine="cfgrib",
                backend_kwargs={'indexpath': '', 'filter_by_keys': {'stepType': 'instant'}}
            )
        except:
            ds = xr.open_dataset(
                latest_file,
                engine="cfgrib",
                backend_kwargs={'indexpath': '', 'filter_by_keys': {'stepType': 'avg'}}
            )
        
        pressure = ds['prmsl'].data
        u_wind = ds['u10'].data
        v_wind = ds['v10'].data
        lat = ds['latitude'].data
        lon = ds['longitude'].data
        
        ds.close()
        
        print("🌀 Đang quét tâm áp thấp...")
        low_pressure_centers = detect_low_pressure_centers(pressure, lat, lon, threshold=1010)
        
        if not low_pressure_centers:
            print("✅ Không phát hiện hoạt động bão trong khu vực")
            return None
        
        print(f"📊 Phát hiện {len(low_pressure_centers)} tâm áp thấp")
        
        storms = []
        for idx, center in enumerate(low_pressure_centers, 1):
            lat_idx = np.argmin(np.abs(lat - center['lat']))
            lon_idx = np.argmin(np.abs(lon - center['lon']))
            
            max_wind, avg_wind = analyze_wind_speed(u_wind, v_wind, lat_idx, lon_idx)
            classification = classify_storm(center['pressure'], max_wind)
            
            storm_info = {
                'id': f"NOAA-{idx}",
                'name': f"Low Pressure System {idx}",
                'classification': classification,
                'lat': center['lat'],
                'lon': center['lon'],
                'pressure': center['pressure'],
                'max_wind_speed_ms': max_wind,
                'max_wind_speed_kmh': max_wind * 3.6,
                'avg_wind_speed_ms': avg_wind,
                'source': 'NOAA GFS',
                'timestamp': datetime.now().isoformat(),
                'data_file': os.path.basename(latest_file)
            }
            
            storms.append(storm_info)
            
            print(f"\n🌀 Tâm áp thấp #{idx}:")
            print(f"   Vị trí: {center['lat']:.2f}°N, {center['lon']:.2f}°E")
            print(f"   Áp suất: {center['pressure']:.1f} hPa")
            print(f"   Gió max: {max_wind:.1f} m/s ({max_wind*3.6:.1f} km/h)")
            print(f"   Phân loại: {classification}")
        
        strongest_storm = min(storms, key=lambda s: s['pressure'])
        
        print(f"\n{'='*60}")
        print(f"⚠️  BÃO MẠNH NHẤT: {strongest_storm['classification']}")
        print(f"   Áp suất: {strongest_storm['pressure']:.1f} hPa")
        print(f"   Gió: {strongest_storm['max_wind_speed_kmh']:.1f} km/h")
        print(f"{'='*60}")
        
        return strongest_storm
        
    except Exception as e:
        print(f"❌ Lỗi khi phát hiện bão: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("=== TEST STORM DETECTION FROM NOAA ===")
    result = check_for_storm()
    if result:
        print(f"\n✅ KẾT QUẢ: {result}")
    else:
        print("\n✓ Không phát hiện bão")
