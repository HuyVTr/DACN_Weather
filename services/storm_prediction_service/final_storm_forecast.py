# ============================================================ 
# FINAL STORM FORECAST - FINAL BOT-INTEGRATED VERSION 
# ============================================================ 

import torch
from torch.cuda.amp import autocast
import numpy as np # Re-import numpy
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
import threading
import json
import xarray as xr
import cfgrib # Needed for xarray to read grib2 files
from scipy import interpolate

# --- PATH DEFINITIONS & REAL-TIME INTEGRATION ---
# This block defines all necessary paths dynamically and handles module imports.
SERVICE_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVICES_DIR = os.path.dirname(SERVICE_ROOT)
PROJECT_ROOT = os.path.dirname(SERVICES_DIR)
REALTIME_SERVICE_DIR = os.path.join(SERVICES_DIR, "realtime_weather")

if SERVICES_DIR not in sys.path:
    sys.path.append(SERVICES_DIR)
if REALTIME_SERVICE_DIR not in sys.path:
    sys.path.append(REALTIME_SERVICE_DIR)

# Central data store paths
DATA_STORE_DIR = os.path.join(PROJECT_ROOT, "project_data")
RAW_GRIB_DIR = os.path.join(DATA_STORE_DIR, "data")
PROCESSED_OUTPUT_DIR = os.path.join(DATA_STORE_DIR, "grib2_output")
SIMULATION_DATA_DIR = os.path.join(SERVICE_ROOT, "simulation_data")

from .model import FinalTFT
from .data_processor import FinalDataProcessor
from .trainer import FinalTrainer
from .exporter import FinalExporter, NumpyEncoder
from .analysis_modules import StormOriginDetector, TrajectoryAnalyzer

try:
    from ..realtime_weather.storm_pipeline.data_collector import download_gfs_72h_sequence
    from ..realtime_weather.storm_pipeline.storm_detector_bot import StormDetectorBot
    REALTIME_ENABLED = True
    print("✅ Tải thành công module Real-time (StormDetectorBot, DataCollector).")
except ImportError as e:
    print(f"⚠️ Không thể tải module Real-time: {e}")
    print("   -> Chạy ở chế độ dự báo từ dữ liệu lịch sử.")
    REALTIME_ENABLED = False
# -------------------------

class FinalStormSystem:
    def __init__(self):
        print("\n" + "="*60)
        print("🌀 FINAL STORM FORECAST SYSTEM (AMP, SIMULATION, ANALYSIS)")
        print(f"🛰️ Real-time Active: {REALTIME_ENABLED}")
        print("="*60)
        
        self.processor = FinalDataProcessor()
        self.model = FinalTFT()
        self.trainer = FinalTrainer(self.model)
        self.exporter = FinalExporter()
        # Sử dụng đường dẫn tuyệt đối đến model
        self.model_path = os.path.join(SERVICE_ROOT, 'final_storm_10f.pth')

    # --- Giữ nguyên hàm train() đã được tối ưu ---
    def train(self, epochs=20, fast_mode=False):
        print("\n🔥 TRAINING...")
        
        self.processor.load_and_process()
        X_train, y_train, X_val, y_val, X_test, y_test = self.processor.create_sequences(seq_len=72, forecast_horizon=168)
        
        if X_train is None:
            print("❌ Không đủ dữ liệu để tạo sequence cho training.")
            return

        if fast_mode:
            sample_size = min(1000, len(X_train))
            idx = np.random.choice(len(X_train), sample_size, replace=False)
            X_train, y_train = X_train[idx], y_train[idx]
            print(f"⚡ Fast mode: {sample_size} samples for training")
        
        best_val_loss = float('inf')
        patience = 5
        epochs_no_improve = 0

        for epoch in range(epochs):
            train_loss = self.trainer.train_epoch(X_train, y_train)
            
            self.model.eval()
            val_loss = 0
            val_batch_size = 32
            with torch.no_grad():
                with autocast(enabled=self.trainer.scaler.is_enabled()):
                    val_indices = np.arange(len(X_val))
                    for i in range(0, len(X_val), val_batch_size):
                        batch_idx = val_indices[i:i+val_batch_size]
                        bx_val, by_val = torch.from_numpy(X_val[batch_idx]).to(self.trainer.device), torch.from_numpy(y_val[batch_idx]).to(self.trainer.device)
                        val_predictions_batch = self.model(bx_val)['full']
                        val_loss += self.trainer.loss_fn(val_predictions_batch, by_val).item()
                    val_loss /= max(1, (len(X_val) // val_batch_size))
            
            status = ""
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(self.model.state_dict(), self.model_path)
                status = "⭐ BEST"
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1
            
            print(f"💾 Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.6f} | Val Loss: {val_loss:.6f} {status}")

            if epochs_no_improve == patience:
                print(f"⚠️ Early stopping! No improvement in validation loss for {patience} epochs.")
                break
        
        print(f"\n✅ Training complete! Best Validation Loss: {best_val_loss:.6f}")
        self.model.load_state_dict(torch.load(self.model_path, map_location=self.trainer.device))
        self.model.eval()
        test_loss = 0
        test_batch_size = 32
        with torch.no_grad():
            with autocast(enabled=self.trainer.scaler.is_enabled()):
                test_indices = np.arange(len(X_test))
                for i in range(0, len(X_test), test_batch_size):
                    batch_idx = test_indices[i:i+test_batch_size]
                    bx_test, by_test = torch.from_numpy(X_test[batch_idx]).to(self.trainer.device), torch.from_numpy(y_test[batch_idx]).to(self.trainer.device)
                    test_predictions_batch = self.model(bx_test)['full']
                    test_loss += self.trainer.loss_fn(test_predictions_batch, by_test).item()
                test_loss /= max(1, (len(X_test) // test_batch_size))
        print(f"📊 Test Loss: {test_loss:.6f}")

    # --- Bắt đầu tích hợp các phương thức mới ---

    def extract_features_from_grib(self, grib_path, lat, lon):
        try:
            # Strategy: Open the GRIB file multiple times with specific filters for each data type.
            
            # --- Get data at isobaric levels (850mb, 200mb) ---
            with xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'isobaricInhPa'}}, drop_variables=['valid_time']) as ds_isobaric:
                u850 = ds_isobaric['u'].sel(isobaricInhPa=850, latitude=lat, longitude=lon, method='nearest').item()
                v850 = ds_isobaric['v'].sel(isobaricInhPa=850, latitude=lat, longitude=lon, method='nearest').item()
                r850 = ds_isobaric['r'].sel(isobaricInhPa=850, latitude=lat, longitude=lon, method='nearest').item()
                t850 = ds_isobaric['t'].sel(isobaricInhPa=850, latitude=lat, longitude=lon, method='nearest').item()
                u200 = ds_isobaric['u'].sel(isobaricInhPa=200, latitude=lat, longitude=lon, method='nearest').item()

            # --- Get data at surface level ---
            with xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'surface'}}, drop_variables=['valid_time']) as ds_surface:
                # GFS often provides TMP on surface level which can be used for SST over water.
                sst = ds_surface['t'].sel(latitude=lat, longitude=lon, method='nearest').item()
                
            # --- Get data at mean sea level ---
            with xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'meanSea'}}, drop_variables=['valid_time']) as ds_msl:
                pressure = ds_msl['prmsl'].sel(latitude=lat, longitude=lon, method='nearest').item()

            # --- Get data at 10m above ground ---
            with xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'heightAboveGround', 'level': 10}}, drop_variables=['valid_time']) as ds_10m:
                u10 = ds_10m['u10'].sel(latitude=lat, longitude=lon, method='nearest').item()
                v10 = ds_10m['v10'].sel(latitude=lat, longitude=lon, method='nearest').item()

            # --- Process and combine data ---
            t850_c = t850 - 273.15 if not np.isnan(t850) else np.nan
            sst_c = sst - 273.15 if not np.isnan(sst) else np.nan # Convert SST to Celsius
            pressure_hpa = pressure / 100 if not np.isnan(pressure) else np.nan
            wind_speed = np.sqrt(u10**2 + v10**2) if not (np.isnan(u10) or np.isnan(v10)) else np.nan

            if np.isnan(wind_speed) or np.isnan(pressure_hpa): return None
            
            # Return dict with standard feature names
            return {
                'LAT': lat, 'LON': lon, 'WMO_WIND': wind_speed, 'WMO_PRES': pressure_hpa,
                'u_850': u850, 'v_850': v850, 'r_850': r850, 't_850': t850_c,
                'u_200': u200, 'SST': sst_c
            }
        except Exception as e:
            print(f"   -> ❌ Lỗi tổng quát khi trích xuất feature từ file {os.path.basename(grib_path)}: {e}")
            return None

    def get_input_sequence(self, mode='realtime'):
        if mode == 'realtime':
            if not REALTIME_ENABLED: return None, None, None
            print("\n🛰️  --- BẮT ĐẦU QUY TRÌNH DỰ BÁO REAL-TIME ---")
            gfs_data_dir = RAW_GRIB_DIR; os.makedirs(gfs_data_dir, exist_ok=True)
            
            # BƯỚC 1: Tải dữ liệu GRIB thời gian thực (f000) để phân tích
            print("\n[1/3] Đang tải dữ liệu thời tiết mới nhất (f000) để phân tích...")
            from ..realtime_weather.storm_pipeline.data_collector import robust_download_gfs_forecast
            latest_grib_file = robust_download_gfs_forecast("f000", gfs_data_dir)
            
            if not latest_grib_file:
                print("   -> ❌ Không thể tải dữ liệu thời gian thực. Không thể chạy BOT.")
                return None, None, None

            # BƯỚC 2: Chạy BOT trên dữ liệu vừa tải về
            print("\n[2/3] BOT đang phân tích dữ liệu...")
            bot = StormDetectorBot(data_dir=RAW_GRIB_DIR)
            alerts = bot.scan_south_china_sea()
            # Sử dụng đường dẫn tập trung và đảm bảo thư mục tồn tại
            os.makedirs(PROCESSED_OUTPUT_DIR, exist_ok=True)
            with open(os.path.join(PROCESSED_OUTPUT_DIR, 'all_alerts.json'), 'w', encoding='utf-8') as f: json.dump(alerts, f, ensure_ascii=False, indent=2)
            if not alerts: 
                print("   -> BOT không phát hiện hệ thống nào đáng chú ý trong Biển Đông.")
                return None, None, None
            
            strongest_alert = max(alerts, key=lambda x: x['wind_speed'])
            print(f"   -> ✅ BOT đã phát hiện '{strongest_alert['type_vi']}' mạnh nhất. Bắt đầu thu thập chuỗi lịch sử...")
            
            # Sử dụng hàm download_gfs_72h_sequence của project
            grib_files = download_gfs_72h_sequence(output_dir=gfs_data_dir) # Giả định step 3h
            if not grib_files or len(grib_files) < 24: # Cần 24 điểm dữ liệu cho 72h, step 3h
                print("   -> ❌ Không tải đủ file lịch sử để tạo chuỗi đầu vào.")
                return strongest_alert, None, None

            grib_files.sort()
            print("   -> 🔁 Đang trích xuất features từ chuỗi GRIB lịch sử...")
            historical_sequence_data = []
            target_lat, target_lon = strongest_alert['lat'], strongest_alert['lon']
            
            for grib_path in grib_files:
                features = self.extract_features_from_grib(grib_path, target_lat, target_lon)
                if features:
                    # Đảm bảo thứ tự feature đúng với processor.FEATURES
                    ordered_features = [features.get(f_name, np.nan) for f_name in self.processor.FEATURES]
                    historical_sequence_data.append(ordered_features)
            
            if len(historical_sequence_data) < 24:
                print(f"   -> ❌ Chỉ trích xuất được {len(historical_sequence_data)} điểm dữ liệu. Không đủ 24 điểm.")
                return strongest_alert, None, None

            print(f"   -> ✅ Đã tạo chuỗi lịch sử với {len(historical_sequence_data)} điểm dữ liệu (3-hour interval).")
            
            sequence_array = np.array(historical_sequence_data, dtype=np.float32)
            
            # Nội suy từ 3h -> 1h
            original_time_points = np.arange(0, 73, 3)
            target_time_points = np.arange(0, 72, 1)
            interpolated_sequence = np.zeros((len(target_time_points), sequence_array.shape[1]), dtype=np.float32)
            
            for i in range(sequence_array.shape[1]):
                f = interpolate.interp1d(original_time_points, sequence_array[:, i], kind='linear', fill_value="extrapolate")
                interpolated_sequence[:, i] = f(target_time_points)

            print(f"   -> ✅ Nội suy thành công chuỗi {len(interpolated_sequence)} điểm dữ liệu (1-hour interval).")
            return strongest_alert, interpolated_sequence, strongest_alert.get('type_vi', 'Unknown Storm')
        
        elif mode == 'simulation':
            print("\n🌀 --- BẮT ĐẦU QUY TRÌNH DỰ BÁO GIẢ ĐỊNH ---")
            # Sử dụng đường dẫn tuyệt đối
            sim_file = Path(os.path.join(SIMULATION_DATA_DIR, 'actual_path.csv'))
            if not sim_file.exists():
                print(f"   -> ❌ Không tìm thấy file '{sim_file}'")
                return None, None, None
            
            df_sim = pd.read_csv(sim_file)
            if len(df_sim) < 72:
                print(f"   -> ❌ File giả định không có đủ 72 dòng dữ liệu.")
                return None, None, None
            
            df_input = df_sim.head(72).copy()
            input_sequence = np.zeros((72, len(self.processor.FEATURES)), dtype=np.float32)
            
            # Tạo WMO_WIND từ U10, V10 nếu chưa có
            if 'WMO_WIND' not in df_input.columns and 'U10' in df_input.columns and 'V10' in df_input.columns:
                 df_input['WMO_WIND'] = np.sqrt(df_input['U10']**2 + df_input['V10']**2)

            for i, feature in enumerate(self.processor.FEATURES):
                # Ánh xạ từ tên cột trong CSV sang tên feature chuẩn
                csv_col_map = {
                    'LAT': 'LATITUDE', 'LON': 'LONGITUDE', 'WMO_WIND': 'WMO_WIND', 
                    'WMO_PRES': 'PRMSL', 't_850': 'T_CELSIUS', 'SST': 'SST', 
                    'r_850': 'HUMIDITY', 'u_200': 'WIND_SHEAR'
                    # u_850, v_850 không có trong file sim -> sẽ được fill sau
                }
                if feature in csv_col_map and csv_col_map[feature] in df_input.columns:
                    input_sequence[:, i] = df_input[csv_col_map[feature]].values
                else:
                    # Fill các feature không có trong file sim bằng giá trị trung bình từ scaler
                    if feature in self.processor.scaler_params:
                         mean_val = (self.processor.scaler_params[feature]['min'] + self.processor.scaler_params[feature]['max']) / 2
                         input_sequence[:, i] = mean_val
                    else: # Fallback nếu scaler chưa được tính
                        input_sequence[:, i] = 0
            
            print(f"   -> ✅ Đã tạo chuỗi đầu vào 72 giờ từ '{sim_file}'.")
            return {'classification': 'SIMULATED_TYPHOON', 'type_vi': 'Bão Giả Định'}, input_sequence, 'Simulated Storm (Typhoon Rai)'

        else: # historical_fallback
            print("\n   -> ⚠️  Sử dụng 72h cuối từ file Excel.")
            df_processed = self.processor.df
            if len(df_processed) < 72:
                print("   -> ❌ Dữ liệu Excel không đủ 72 dòng.")
                return None, None, None
            latest_input = df_processed[self.processor.FEATURES].values.astype(np.float32)[-72:]
            return None, latest_input, 'Historical Data'

    def predict_from_sequence(self, input_sequence, source_name, realtime_storm_details=None, is_simulation=False):
        # 1. Normalize the input sequence
        normalized_sequence = input_sequence.copy()
        for i, col in enumerate(self.processor.FEATURES):
            p = self.processor.scaler_params[col]
            # Handle cases where max and min are the same
            denom = p['max'] - p['min']
            if denom < 1e-8:
                normalized_sequence[:, i] = 0 # Or some other default normalized value
            else:
                normalized_sequence[:, i] = (normalized_sequence[:, i] - p['min']) / denom

        # 2. Run prediction
        with torch.no_grad():
            with autocast(enabled=self.trainer.scaler.is_enabled()):
                X = torch.from_numpy(normalized_sequence).unsqueeze(0).to(self.trainer.device)
                preds_normalized = self.model(X)['full'].cpu().numpy()[0]
        
        # 3. Descale predictions
        preds = preds_normalized.copy()
        for i, feat in enumerate(self.processor.FEATURES):
            p = self.processor.scaler_params[feat]
            denom = p['max'] - p['min']
            if denom < 1e-8:
                preds[:, i] = p['min']
            else:
                preds[:, i] = preds_normalized[:, i] * denom + p['min']
        
        # 4. FIX FOR SIMULATION STARTING POINT
        if is_simulation:
            print("   -> 🔧 Điều chỉnh điểm bắt đầu của dự báo giả định...")
            lat_idx = self.processor.FEATURES.index('LAT')
            lon_idx = self.processor.FEATURES.index('LON')
            last_actual_lat = input_sequence[-1, lat_idx]
            last_actual_lon = input_sequence[-1, lon_idx]
            
            first_pred_lat = preds[0, lat_idx]
            first_pred_lon = preds[0, lon_idx]
            
            lat_offset = last_actual_lat - first_pred_lat
            lon_offset = last_actual_lon - first_pred_lon
            
            preds[:, lat_idx] += lat_offset
            preds[:, lon_idx] += lon_offset
            print(f"   -> ✅ Đã điều chỉnh dự báo. Offset: Lat {lat_offset:.2f}, Lon {lon_offset:.2f}")

        # 5. Export results with analysis
        timestamp = datetime.now()
        # Ta sẽ sửa hàm export để nó tự chạy analysis
        df, analysis = self.exporter.export(
            preds, 
            self.processor.scaler_params, 
            timestamp, 
            self.processor.FEATURES,
            origin_details=realtime_storm_details, 
            is_simulation=is_simulation,
            source_name=source_name
        )
        
        print("\n✅ Prediction complete!")

    def run_prediction_flow(self, mode='realtime'):
        print("\n🔮 PREDICTION...")
        if not Path(self.model_path).exists():
            print(f"⚠️ Không tìm thấy model đã huấn luyện tại '{self.model_path}'. Dừng dự báo.")
            return
        
        self.model.load_state_dict(torch.load(self.model_path, map_location=self.trainer.device))
        self.model.eval()
        
        # Load scaler params from the full training data
        self.processor.load_and_process()
        
        # Get the appropriate input sequence
        storm_details, sequence, source_name = self.get_input_sequence(mode=mode)
        
        if sequence is None:
            print("   -> ⚠️ Không thể lấy được chuỗi đầu vào. Thử fallback...")
            storm_details, sequence, source_name = self.get_input_sequence(mode='historical_fallback')
            if sequence is None:
                print("   -> ❌ Fallback cũng thất bại. Dừng dự báo.")
                return

        # Run the prediction on the obtained sequence
        self.predict_from_sequence(sequence, source_name, storm_details, is_simulation=(mode=='simulation'))

# ============================================================ 
# CLI 
# ============================================================ 
if __name__ == '__main__':
    system = FinalStormSystem()
    print("\n" + "="*60)
    print("⚡ SELECT MODE")
    print("="*60)
    print("1. 🚀 Quick Train (1000 samples, 10 epochs)")
    print("2. 💪 Full Train (all data, 20 epochs)")
    print("3. 🔮 Predict & Export (Sử dụng BOT để tìm bão Real-time)")
    print("4. 🌀 Simulate Storm (Sử dụng mô hình để dự báo bão giả định)")
    choice = input("\nSelect (1-4): ").strip()
    
    if choice == '1':
        system.train(epochs=10, fast_mode=True)
    elif choice == '2':
        system.train(epochs=20)
    elif choice == '3':
        system.run_prediction_flow(mode='realtime')
    elif choice == '4':
        system.run_prediction_flow(mode='simulation')

    print("\n✅ DONE!")