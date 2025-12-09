# File: storm_pipeline/storm_detector_bot.py
# BOT TỰ ĐỘNG PHÁT HIỆN BÃO & GIÔNG - BIỂN ĐÔNG

import xarray as xr
import numpy as np
import glob
import os
from datetime import datetime
import json

class StormDetectorBot:
    """
    Bot tự động quét dữ liệu GRIB2 và phát hiện:
    - Bão nhiệt đới (Tropical Storm)
    - Giông bão (Thunderstorm)
    - Áp thấp nhiệt đới (Tropical Depression)
    - Vùng gió mạnh (Strong Wind)
    """
    
    def __init__(self, data_dir=None):
        if data_dir:
            self.data_dir = data_dir
        else:
            # Construct a more reliable default path
            PIPELINE_ROOT = os.path.dirname(os.path.abspath(__file__))
            REALTIME_ROOT = os.path.dirname(PIPELINE_ROOT)
            SERVICES_ROOT = os.path.dirname(REALTIME_ROOT)
            PROJECT_ROOT = os.path.dirname(SERVICES_ROOT)
            self.data_dir = os.path.join(PROJECT_ROOT, "project_data", "data")
            
        self.alerts = []
        
        # Ngưỡng phát hiện
        self.THRESHOLDS = {
            'typhoon': {'pressure': 960, 'wind': 33},          # Bão mạnh
            'tropical_storm': {'pressure': 990, 'wind': 17},   # Bão nhiệt đới
            'depression': {'pressure': 1005, 'wind': 10},      # Áp thấp
            'thunderstorm': {'temp': 26, 'wind': 12},          # Giông bão
            'strong_wind': {'wind': 15}                         # Gió mạnh
        }
    
    def scan_south_china_sea(self):
        """
        Quét toàn bộ Biển Đông và phát hiện các điểm nguy hiểm.
        """
        print(f"\n{'='*70}")
        print(f"🤖 STORM DETECTOR BOT")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        try:
            # Lấy file GRIB2 mới nhất
            pattern = os.path.join(self.data_dir, "*_f000.grib2")
            files = glob.glob(pattern)
            
            if not files:
                pattern = os.path.join(self.data_dir, "*.grib2")
                files = glob.glob(pattern)
            
            if not files:
                print("❌ Không tìm thấy dữ liệu GRIB")
                return []
            
            latest_file = max(files, key=lambda p: os.path.getmtime(p))
            print(f"📂 Analyzing: {os.path.basename(latest_file)}")
            
            # Mở file GRIB2 nhiều lần với các bộ lọc khác nhau cho từng loại dữ liệu
            ds_pressure = xr.open_dataset(latest_file, engine="cfgrib", backend_kwargs={'indexpath': '', 'filter_by_keys': {'typeOfLevel': 'meanSea'}})
            ds_wind = xr.open_dataset(latest_file, engine="cfgrib", backend_kwargs={'indexpath': '', 'filter_by_keys': {'typeOfLevel': 'heightAboveGround', 'level': 10}})
            ds_temp = xr.open_dataset(latest_file, engine="cfgrib", backend_kwargs={'indexpath': '', 'filter_by_keys': {'typeOfLevel': 'surface'}})
            
            # Lấy dữ liệu
            pressure = ds_pressure['prmsl'].data / 100  # Pa → hPa
            u_wind = ds_wind['u10'].data
            v_wind = ds_wind['v10'].data
            temp = ds_temp['t'].data # Lấy nhiệt độ mặt đất
            
            # Lấy lat/lon từ một trong các dataset (chúng giống nhau)
            lat = ds_pressure['latitude'].data
            lon = ds_pressure['longitude'].data
            
            # Convert nhiệt độ Kelvin → Celsius nếu cần
            if temp.max() > 200:
                temp = temp - 273.15
            
            # Đóng tất cả các dataset đã mở
            ds_pressure.close()
            ds_wind.close()
            ds_temp.close()
            
            # Tính tốc độ gió
            wind_speed = np.sqrt(u_wind**2 + v_wind**2)
            
            # Quét từng điểm
            self.alerts = []
            height, width = pressure.shape
            
            print(f"🔍 Scanning {height * width} grid points...")
            
            for i in range(0, height, 5):  # Quét mỗi 5 điểm để tăng tốc
                for j in range(0, width, 5):
                    point_lat = lat[i]
                    point_lon = lon[j]
                    
                    # Chỉ quét khu vực Biển Đông
                    if not (3 <= point_lat <= 26 and 100 <= point_lon <= 121):
                        continue
                    
                    point_pressure = pressure[i, j]
                    point_wind = wind_speed[i, j]
                    point_temp = temp[i, j]
                    
                    # Kiểm tra các điều kiện nguy hiểm
                    alert = self._check_danger(
                        point_lat, point_lon, 
                        point_pressure, point_wind, point_temp
                    )
                    
                    if alert:
                        self.alerts.append(alert)
            
            # Gộp các alert gần nhau
            self.alerts = self._merge_nearby_alerts(self.alerts)
            
            # Hiển thị kết quả
            print(f"\n{'─'*70}")
            if self.alerts:
                print(f"⚠️  PHÁT HIỆN {len(self.alerts)} VÙNG NGUY HIỂM:")
                for idx, alert in enumerate(self.alerts, 1):
                    print(f"\n🚨 Alert #{idx}:")
                    print(f"   Type: {alert['type_vi']} ({alert['severity']})")
                    print(f"   Location: {alert['lat']:.2f}°N, {alert['lon']:.2f}°E")
                    print(f"   Details: {alert['details']}")
            else:
                print("✅ Biển Đông yên bình - Không phát hiện nguy hiểm")
            print(f"{'─'*70}\n")
            
            return self.alerts
            
        except Exception as e:
            print(f"❌ Lỗi khi quét: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _check_danger(self, lat, lon, pressure, wind, temp):
        """
        Kiểm tra một điểm có nguy hiểm không.
        """
        alerts = []
        
        # 1. Kiểm tra Bão (Typhoon)
        if pressure < self.THRESHOLDS['typhoon']['pressure'] and \
           wind > self.THRESHOLDS['typhoon']['wind']:
            return {
                'type': 'typhoon',
                'type_vi': 'BÃO MẠNH',
                'severity': 'EXTREME',
                'lat': float(lat),
                'lon': float(lon),
                'pressure': float(pressure),
                'wind_speed': float(wind),
                'wind_speed_kmh': float(wind * 3.6),
                'details': f"Áp suất {pressure:.1f} hPa, Gió {wind*3.6:.1f} km/h",
                'color': '#8B0000',  # Đỏ đậm
                'icon': '🌀'
            }
        
        # 2. Kiểm tra Bão nhiệt đới (Tropical Storm)
        if pressure < self.THRESHOLDS['tropical_storm']['pressure'] and \
           wind > self.THRESHOLDS['tropical_storm']['wind']:
            return {
                'type': 'tropical_storm',
                'type_vi': 'BÃO NHIỆT ĐỚI',
                'severity': 'HIGH',
                'lat': float(lat),
                'lon': float(lon),
                'pressure': float(pressure),
                'wind_speed': float(wind),
                'wind_speed_kmh': float(wind * 3.6),
                'details': f"Áp suất {pressure:.1f} hPa, Gió {wind*3.6:.1f} km/h",
                'color': '#FF0000',  # Đỏ
                'icon': '🌀'
            }
        
        # 3. Kiểm tra Áp thấp nhiệt đới
        if pressure < self.THRESHOLDS['depression']['pressure'] and \
           wind > self.THRESHOLDS['depression']['wind']:
            return {
                'type': 'depression',
                'type_vi': 'ÁP THẤP NHIỆT ĐỚI',
                'severity': 'MEDIUM',
                'lat': float(lat),
                'lon': float(lon),
                'pressure': float(pressure),
                'wind_speed': float(wind),
                'wind_speed_kmh': float(wind * 3.6),
                'details': f"Áp suất {pressure:.1f} hPa, Gió {wind*3.6:.1f} km/h",
                'color': '#FF6600',  # Cam đỏ
                'icon': '🌪️'
            }
        
        # 4. Kiểm tra Giông bão (Thunderstorm)
        if temp > self.THRESHOLDS['thunderstorm']['temp'] and \
           wind > self.THRESHOLDS['thunderstorm']['wind'] and \
           pressure < 1010:
            return {
                'type': 'thunderstorm',
                'type_vi': 'GIÔNG BÃO',
                'severity': 'MEDIUM',
                'lat': float(lat),
                'lon': float(lon),
                'pressure': float(pressure),
                'wind_speed': float(wind),
                'wind_speed_kmh': float(wind * 3.6),
                'temp': float(temp),
                'details': f"Nhiệt độ {temp:.1f}°C, Gió {wind*3.6:.1f} km/h",
                'color': '#FFCC00',  # Vàng
                'icon': '⚡'
            }
        
        # 5. Kiểm tra Gió mạnh
        if wind > self.THRESHOLDS['strong_wind']['wind']:
            return {
                'type': 'strong_wind',
                'type_vi': 'GIÓ MẠNH',
                'severity': 'LOW',
                'lat': float(lat),
                'lon': float(lon),
                'wind_speed': float(wind),
                'wind_speed_kmh': float(wind * 3.6),
                'details': f"Gió {wind*3.6:.1f} km/h",
                'color': '#FFA500',  # Cam
                'icon': '💨'
            }
        
        return None
    
    def _merge_nearby_alerts(self, alerts, threshold=0.5):
        """
        Gộp các alert gần nhau (< 0.5 độ) thành 1 alert.
        """
        if not alerts:
            return []
        
        merged = []
        used = set()
        
        for i, alert1 in enumerate(alerts):
            if i in used:
                continue
            
            group = [alert1]
            used.add(i)
            
            for j, alert2 in enumerate(alerts):
                if j in used or j <= i:
                    continue
                
                # Tính khoảng cách
                dist = np.sqrt(
                    (alert1['lat'] - alert2['lat'])**2 + 
                    (alert1['lon'] - alert2['lon'])**2
                )
                
                if dist < threshold and alert1['type'] == alert2['type']:
                    group.append(alert2)
                    used.add(j)
            
            # Lấy alert nghiêm trọng nhất trong group
            group.sort(key=lambda x: x.get('pressure', 1020))
            merged.append(group[0])
        
        return merged
    
    def get_alerts_json(self):
        """
        Trả về alerts dưới dạng JSON để gửi qua API/WebSocket.
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'alerts': self.alerts,
            'count': len(self.alerts),
            'summary': self._get_summary()
        }
    
    def _get_summary(self):
        """
        Tóm tắt tình hình.
        """
        if not self.alerts:
            return "Biển Đông yên bình"
        
        severity_count = {}
        for alert in self.alerts:
            sev = alert['severity']
            severity_count[sev] = severity_count.get(sev, 0) + 1
        
        parts = []
        if 'EXTREME' in severity_count:
            parts.append(f"{severity_count['EXTREME']} vùng CỰC NGUY HIỂM")
        if 'HIGH' in severity_count:
            parts.append(f"{severity_count['HIGH']} vùng nguy hiểm cao")
        if 'MEDIUM' in severity_count:
            parts.append(f"{severity_count['MEDIUM']} vùng nguy hiểm trung bình")
        
        return ", ".join(parts) if parts else f"{len(self.alerts)} cảnh báo"


# Test
if __name__ == "__main__":
    bot = StormDetectorBot()
    alerts = bot.scan_south_china_sea()
    
    if alerts:
        print("\n📊 JSON OUTPUT:")
        print(json.dumps(bot.get_alerts_json(), indent=2, ensure_ascii=False))