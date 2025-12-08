# backend_api/controllers/forecast_controller.py
# Xử lý các route cho trang Dự báo và API thời tiết.

from flask import Blueprint, render_template, request, jsonify
import sys
import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import glob
from services.storm_prediction_service.analysis_modules import TrajectoryAnalyzer

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend_api.models.weather_model import Provinces
from data_pipeline.data_storage import connect_to_db, get_last_timestamp
from services.forecast_ml.predictor import predict_storm

forecast_bp = Blueprint('forecast_bp', __name__)

@forecast_bp.route('/forecast')
def route_forecast():
    """Phục vụ trang dự báo."""
    return render_template('forecast.html', nav_active='forecast')

# --- CẤU HÌNH DATABASE CHO CONTROLLER ---
# Lưu ý: Thay 'password' bằng mật khẩu thực của bạn
# DB_URI = "postgresql://postgres:password@localhost:5432/weather_db"
# db_engine = create_engine(DB_URI)

@forecast_bp.route('/api/provinces')
def api_get_provinces():
    """API lấy danh sách 63 tỉnh (mocked data)."""
    # Dữ liệu tỉnh được hardcode vì không có DB
    provinces_data = [
        {'province_id': 1, 'name': 'Hà Nội', 'latitude': 21.0285, 'longitude': 105.8542},
        {'province_id': 2, 'name': 'TP. Hồ Chí Minh', 'latitude': 10.8231, 'longitude': 106.6297},
        {'province_id': 3, 'name': 'Đà Nẵng', 'latitude': 16.0544, 'longitude': 108.2022},
        {'province_id': 4, 'name': 'Hải Phòng', 'latitude': 20.8449, 'longitude': 106.6881},
        {'province_id': 5, 'name': 'Cần Thơ', 'latitude': 10.0452, 'longitude': 105.7468},
        {'province_id': 6, 'name': 'Huế', 'latitude': 16.4637, 'longitude': 107.5909},
        {'province_id': 7, 'name': 'Nha Trang', 'latitude': 12.2388, 'longitude': 109.1967},
        {'province_id': 8, 'name': 'Vũng Tàu', 'latitude': 10.3458, 'longitude': 107.0805},
        {'province_id': 9, 'name': 'Lào Cai', 'latitude': 22.4965, 'longitude': 103.9635},
        {'province_id': 10, 'name': 'Quảng Ninh', 'latitude': 21.0180, 'longitude': 107.2245},
    ]
    
    # Sắp xếp theo tên tỉnh
    provinces_data_sorted = sorted(provinces_data, key=lambda p: p['name'])
    
    return jsonify(provinces_data_sorted)

def merge_api_and_ml_data(api_data, ml_data, province_name):
    """
    Merge dữ liệu từ Open-Meteo API và ML predictions
    Ưu tiên API cho giờ hiện tại và các giờ có sẵn,
    dùng ML để bổ sung các giờ còn thiếu
    """
    merged_data = {
        "location": province_name,
        "current": api_data.get("current", {}),
        "daily": {},
        "hourly": {},
        "ml_prediction": ml_data
    }
    
    # Merge hourly data
    api_hourly = api_data.get("hourly", {})
    api_times = api_hourly.get('time', [])
    
    if ml_data and 'hourly_predictions' in ml_data:
        ml_hourly = ml_data['hourly_predictions']
        
        # Tạo dict để dễ merge
        hourly_dict = {
            'time': [],
            'temperature_2m': [],
            'relative_humidity_2m': [],
            'precipitation': [],
            'rain': [],
            'showers': [],
            'weather_code': [],
            'pressure_msl': [],
            'wind_speed_10m': [],
            'wind_direction_10m': [],
            'visibility': [],
            'uv_index': []
        }
        
        # Lấy tất cả thời gian cần thiết (API + ML)
        all_times = []
        now = datetime.now()
        
        # Thêm từ API (nếu có)
        for i, time_str in enumerate(api_times):
            # Xử lý format thời gian đôi khi có 'Z'
            clean_time_str = time_str.replace('Z', '+00:00')
            try:
                time_obj = datetime.fromisoformat(clean_time_str)
            except ValueError:
                # Fallback nếu format lạ
                continue
                
            if time_obj >= now - timedelta(hours=1): # Lấy cả giờ hiện tại
                all_times.append({
                    'time': time_str,
                    'source': 'api',
                    'index': i
                })
        
        # Thêm từ ML cho các giờ còn thiếu
        for ml_hour in ml_hourly:
            ml_time = ml_hour['time']
            # Kiểm tra xem thời gian này đã có trong API chưa
            if ml_time not in [t['time'] for t in all_times]:
                all_times.append({
                    'time': ml_time,
                    'source': 'ml',
                    'data': ml_hour
                })
        
        # Sort theo thời gian
        all_times.sort(key=lambda x: x['time'])
        
        # Merge data (Lấy tối đa 48h)
        for time_info in all_times[:48]:
            hourly_dict['time'].append(time_info['time'])
            
            if time_info['source'] == 'api':
                idx = time_info['index']
                # Helper function để lấy safe value
                def get_val(key, default=0):
                    arr = api_hourly.get(key, [])
                    return arr[idx] if idx < len(arr) else default

                hourly_dict['temperature_2m'].append(get_val('temperature_2m'))
                hourly_dict['relative_humidity_2m'].append(get_val('relative_humidity_2m'))
                hourly_dict['precipitation'].append(get_val('precipitation'))
                hourly_dict['rain'].append(get_val('rain'))
                hourly_dict['showers'].append(get_val('showers'))
                hourly_dict['weather_code'].append(get_val('weather_code'))
                hourly_dict['pressure_msl'].append(get_val('pressure_msl'))
                hourly_dict['wind_speed_10m'].append(get_val('wind_speed_10m'))
                hourly_dict['wind_direction_10m'].append(get_val('wind_direction_10m'))
                hourly_dict['visibility'].append(get_val('visibility'))
                hourly_dict['uv_index'].append(get_val('uv_index'))
            else:  # ML data
                ml_hour = time_info['data']
                hourly_dict['temperature_2m'].append(ml_hour.get('temperature_2m', 0))
                hourly_dict['relative_humidity_2m'].append(ml_hour.get('relative_humidity_2m', 0))
                hourly_dict['precipitation'].append(ml_hour.get('precipitation', 0))
                hourly_dict['rain'].append(ml_hour.get('precipitation', 0)) # ML gộp rain
                hourly_dict['showers'].append(0)
                hourly_dict['weather_code'].append(ml_hour.get('weather_code', 0))
                hourly_dict['pressure_msl'].append(ml_hour.get('pressure_msl', 0))
                hourly_dict['wind_speed_10m'].append(ml_hour.get('wind_speed_10m', 0))
                hourly_dict['wind_direction_10m'].append(0)
                hourly_dict['visibility'].append(ml_hour.get('visibility', 0))
                hourly_dict['uv_index'].append(ml_hour.get('uv_index', 0))
        
        merged_data['hourly'] = hourly_dict
    else:
        merged_data['hourly'] = api_hourly
    
    # Merge daily data
    api_daily = api_data.get("daily", {})
    
    if ml_data and 'daily_forecast' in ml_data:
        ml_daily = ml_data['daily_forecast']
        api_daily_times = api_daily.get('time', [])
        
        # Nếu API có ít hơn 7 ngày, bổ sung từ ML
        if len(api_daily_times) < 7:
            daily_dict = {
                'time': list(api_daily.get('time', [])),
                'weather_code': list(api_daily.get('weather_code', [])),
                'temperature_2m_max': list(api_daily.get('temperature_2m_max', [])),
                'temperature_2m_min': list(api_daily.get('temperature_2m_min', [])),
                'precipitation_sum': list(api_daily.get('precipitation_sum', [])),
                'wind_speed_10m_max': list(api_daily.get('wind_speed_10m_max', [])),
                'sunrise': list(api_daily.get('sunrise', [])),
                'sunset': list(api_daily.get('sunset', []))
            }
            
            for ml_day in ml_daily:
                if ml_day['time'] not in daily_dict['time']:
                    daily_dict['time'].append(ml_day['time'])
                    daily_dict['weather_code'].append(ml_day['weather_code'])
                    daily_dict['temperature_2m_max'].append(ml_day['temperature_2m_max'])
                    daily_dict['temperature_2m_min'].append(ml_day['temperature_2m_min'])
                    daily_dict['precipitation_sum'].append(ml_day['precipitation_sum'])
                    daily_dict['wind_speed_10m_max'].append(ml_day['wind_speed_10m_max'])
                    daily_dict['sunrise'].append(ml_day['sunrise'])
                    daily_dict['sunset'].append(ml_day['sunset'])
                    
                    if len(daily_dict['time']) >= 7:
                        break
            
            merged_data['daily'] = daily_dict
        else:
            merged_data['daily'] = api_daily
    else:
        merged_data['daily'] = api_daily
    
    return merged_data

@forecast_bp.route('/api/forecast')
def api_get_forecast():
    """
    API lấy dữ liệu thời tiết (Open-Meteo + ML/Cache + AQI).
    Logic mới:
    1. Lấy API Open-Meteo (Realtime).
    2. Thử lấy dữ liệu ML từ Cache DB (weather_forecast_cache).
    3. Nếu không có Cache, chạy Fallback (tính toán trực tiếp).
    4. Merge dữ liệu và trả về.
    """
    province_name = request.args.get('province', '')
    days = int(request.args.get('days', 7))
    
    if not province_name:
        return jsonify({"error": "Thiếu province"}), 400

    try:
        # Tìm tỉnh từ danh sách hardcode
        provinces_data = [
            {'province_id': 1, 'name': 'Hà Nội', 'latitude': 21.0285, 'longitude': 105.8542},
            {'province_id': 2, 'name': 'TP. Hồ Chí Minh', 'latitude': 10.8231, 'longitude': 106.6297},
            {'province_id': 3, 'name': 'Đà Nẵng', 'latitude': 16.0544, 'longitude': 108.2022},
            {'province_id': 4, 'name': 'Hải Phòng', 'latitude': 20.8449, 'longitude': 106.6881},
            {'province_id': 5, 'name': 'Cần Thơ', 'latitude': 10.0452, 'longitude': 105.7468},
            {'province_id': 6, 'name': 'Huế', 'latitude': 16.4637, 'longitude': 107.5909},
            {'province_id': 7, 'name': 'Nha Trang', 'latitude': 12.2388, 'longitude': 109.1967},
            {'province_id': 8, 'name': 'Vũng Tàu', 'latitude': 10.3458, 'longitude': 107.0805},
            {'province_id': 9, 'name': 'Lào Cai', 'latitude': 22.4965, 'longitude': 103.9635},
            {'province_id': 10, 'name': 'Quảng Ninh', 'latitude': 21.0180, 'longitude': 107.2245},
        ]
        
        province = next((p for p in provinces_data if p['name'] == province_name), None)
        if not province:
            return jsonify({"error": "Không tìm thấy tỉnh"}), 404

        # 1. Gọi Open-Meteo API
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": province['latitude'],
            "longitude": province['longitude'],
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,rain,showers,weather_code,pressure_msl,wind_speed_10m,wind_direction_10m,visibility,uv_index",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,sunrise,sunset",
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m,pressure_msl,visibility,uv_index,weather_code",
            "timezone": "Asia/Bangkok",
            "forecast_days": min(days, 16)
        }
        
        response = requests.get(url, params=params, timeout=10)
        # Nếu lỗi Open-Meteo, có thể vẫn chạy tiếp nếu muốn, nhưng ở đây ta raise lỗi
        response.raise_for_status()
        api_data = response.json()

        # 2. LẤY DỮ LIỆU ML (Ưu tiên Cache)
        ml_data = None
        try:
            # Query bảng cache (Bỏ qua vì không có DB)
            # query = text("SELECT forecast_data FROM weather_forecast_cache WHERE province_id = :pid")
            # with db_engine.connect() as conn:
            #     result = conn.execute(query, {"pid": province.province_id}).fetchone()
            
            # Nếu có dữ liệu trong Cache (Bỏ qua vì không có DB)
            # if result and result[0]:
            #     raw_data = result[0]
            #     if isinstance(raw_data, str):
            #         ml_data = json.loads(raw_data)
            #     else:
            #         ml_data = raw_data
            # print(f"⚡ [CACHE HIT] Đã lấy dữ liệu dự báo cho {province_name}")

            # 3. FALLBACK: Nếu Cache trống (luôn luôn đúng), chạy tính toán ngay lập tức
            # if not ml_data: # Điều kiện này sẽ luôn đúng
            print(f"🐢 [CACHE MISS] Đang tính toán realtime cho {province_name}...")
            current_weather_data = {
                'temperature_2m': api_data.get("current", {}).get('temperature_2m', 25),
                'relative_humidity_2m': api_data.get("current", {}).get('relative_humidity_2m', 70),
                'pressure_msl': api_data.get("current", {}).get('pressure_msl', 1013),
                'wind_speed_10m': api_data.get("current", {}).get('wind_speed_10m', 5)
            }
            
            ml_data = predict_storm(province['province_id'], current_weather_data)
            
            if 'error' in ml_data:
                print(f"Lỗi ML prediction: {ml_data['error']}")
                ml_data = None

        except Exception as e:
            print(f"Lỗi khi xử lý Cache/ML: {e}")
            # Nếu lỗi DB cache, vẫn tiếp tục với ml_data = None (chỉ hiển thị API data)

        # 4. Merge API và ML data
        forecast_data = merge_api_and_ml_data(api_data, ml_data, province_name)

        # 5. Fetch AQI (Chỉ số không khí)
        try:
            aqi_url = f"https://api.waqi.info/feed/geo:{province['latitude']};{province['longitude']}/?token=demo"
            aqi_response = requests.get(aqi_url, timeout=5)
            if aqi_response.status_code == 200:
                aqi_json = aqi_response.json()
                if aqi_json.get('status') == 'ok':
                    aqi_data = aqi_json.get('data', {})
                    forecast_data['aqi'] = {
                        'index': aqi_data.get('aqi', 0),
                        'components': aqi_data.get('iaqi', {})
                    }
                else:
                    forecast_data['aqi'] = {'index': 0, 'components': {}}
            else:
                forecast_data['aqi'] = {'index': 0, 'components': {}}
        except Exception as e:
            print(f"Lỗi AQI: {e}")
            forecast_data['aqi'] = {'index': 0, 'components': {}}

        return jsonify(forecast_data)
        
    except requests.RequestException as e:
        print(f"Lỗi request API: {e}")
        return jsonify({"error": f"Lỗi kết nối API thời tiết: {str(e)}"}), 500
    except Exception as e:
        print(f"Lỗi tổng quát: {e}")
        # In traceback để debug
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Lỗi server: {str(e)}"}), 500

# --- NEW STORM V2 API ENDPOINTS ---

def get_latest_analysis_file():
    """Finds the most recent '_analysis.json' file."""
    list_of_files = glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'project_data', 'processed_output', '*_analysis.json'))
    if not list_of_files:
        return None
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file

@forecast_bp.route('/api/forecast_storm')
def api_get_storm_forecast():
    """
    API để lấy dữ liệu dự báo bão V2 mới nhất.
    Đọc file JSON gần đây nhất từ thư mục processed_output.
    """
    latest_file = get_latest_analysis_file()
    
    if not latest_file:
        return jsonify({
            "status": "error",
            "message": "Không tìm thấy file dự báo. Hãy chạy kịch bản 'final_storm_forecast.py' để tạo dữ liệu."
        }), 404
        
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        predicted_path_raw = data.get('predicted_path', [])

        # Convert keys to lowercase for the analyzer, which expects 'lat', 'lon'
        predicted_path_for_analyzer = [
            {k.lower(): v for k, v in record.items()}
            for record in predicted_path_raw
        ]
        trajectory_analyzer = TrajectoryAnalyzer.analyze_trajectory(predicted_path_for_analyzer)
        
        # Perform stats calculation on the raw data with uppercase keys
        stats = {
            "max_wind": max(p.get('WMO_WIND', 0) for p in predicted_path_raw) if predicted_path_raw else 0,
            "min_pressure": min(p.get('WMO_PRES', 9999) for p in predicted_path_raw) if predicted_path_raw else 9999,
            "total_days": len(predicted_path_raw) / 24,
            "avg_temp": np.mean([p.get('t_850', 0) for p in predicted_path_raw]).item() if predicted_path_raw else 0,
            "avg_sst": np.mean([p.get('SST', 0) for p in predicted_path_raw]).item() if predicted_path_raw else 0,
            "avg_humidity": np.mean([p.get('r_850', 0) for p in predicted_path_raw]).item() if predicted_path_raw else 0,
            "has_weather_features": "SST" in (predicted_path_raw[0] if predicted_path_raw else {})
        }

        response_data = {
            "status": "success",
            "origin": data.get("origin_storm_details"),
            "trajectory": trajectory_analyzer,
            "stats": stats,
            "data": predicted_path_raw, # Send the original raw data to the frontend
            "analysis": data.get("trajectory_analysis", {})
        }
        
        return jsonify(response_data)

    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File dự báo không tồn tại."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@forecast_bp.route('/api/all_alerts')
def api_get_all_alerts():
    """API để lấy tất cả các cảnh báo từ file all_alerts.json."""
    alerts_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'project_data', 'grib2_output', 'all_alerts.json')
    try:
        with open(alerts_path, 'r', encoding='utf-8') as f:
            alerts = json.load(f)
        return jsonify(alerts)
    except FileNotFoundError:
        return jsonify([]) # Trả về mảng rỗng nếu không có file
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@forecast_bp.route('/api/weather')
def api_get_weather_analysis():
    """API lấy phân tích thời tiết từ file dự báo bão mới nhất."""
    latest_file = get_latest_analysis_file()
    if not latest_file:
        return jsonify({"weather_analysis": None}), 404
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Trả về phần phân tích tương tự như logic cũ
        analysis_data = data.get("trajectory_analysis", {}).get("weather_impact_analysis")
        
        return jsonify({"weather_analysis": analysis_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500