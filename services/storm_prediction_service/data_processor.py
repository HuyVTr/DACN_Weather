import pandas as pd
import numpy as np
import os

# Xác định đường dẫn gốc của dự án và đường dẫn mặc định đến dữ liệu huấn luyện
# File hiện tại nằm trong: weather_project/services/storm_prediction_service/
# Chúng ta cần đi lên 3 cấp để tới gốc weather_project/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_TRAIN_DATA_PATH = os.path.join(PROJECT_ROOT, "project_data", "data_train", "FINAL_TRAINING_DATASET_ENHANCED.xlsx")

class FinalDataProcessor:
    def __init__(self, excel_path=DEFAULT_TRAIN_DATA_PATH, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15):
        self.excel_path = excel_path
        self.scaler_params = {}
        # Define the exact feature names that the model expects and will be used in CSVs
        self.FEATURES = [
            'LAT', 'LON', 'WMO_WIND', 'WMO_PRES', 'u_850', 'v_850', 'r_850', 't_850', 'u_200', 'SST'
        ]
        # Mapping from raw Excel column names to our consistent FEATURES names
        self.COL_MAP = {
            'LAT': 'LAT', 'LON': 'LON',
            'WMO_WIND': 'WMO_WIND', 'WMO_PRES': 'WMO_PRES',
            'u_850': 'u_850', 'v_850': 'v_850', 'r_850': 'r_850', 't_850': 't_850',
            'u_200': 'u_200', 'SST': 'SST'
        }
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        
    def load_and_process(self):
        print(f"\n📂 Đang đọc {self.excel_path}...")
        df_raw = pd.read_excel(self.excel_path, engine='openpyxl')

        
        self.df = pd.DataFrame()
        for excel_col, feature_name in self.COL_MAP.items():
            if excel_col in df_raw.columns:
                self.df[feature_name] = pd.to_numeric(df_raw[excel_col], errors='coerce')
            else:
                self.df[feature_name] = 0.0 # Default value if column not found

        if self.df['WMO_PRES'].mean() > 10000: self.df['WMO_PRES'] /= 100
        if self.df['t_850'].mean() > 100: self.df['t_850'] -= 273.15
        if self.df['r_850'].max() <= 2.0: self.df['r_850'] *= 100
        
        for col in self.FEATURES:
            if self.df[col].isnull().any():
                if col == 'SST':
                    print("   -> Xử lý SST: ô trống = đất liền -> gán giá trị 0.")
                    self.df[col].fillna(0, inplace=True)
                    continue

                defaults = {'WMO_WIND': 25.0, 'WMO_PRES': 1000.0} # Using consistent names
                fill_val = defaults.get(col, self.df[col].mean())
                self.df[col].fillna(fill_val, inplace=True)
        
        # Chuẩn hóa Min-Max sau khi đã điền hết dữ liệu
        print("\n📏 Chuẩn hóa Min-Max...")
        
        for col in self.FEATURES:
            mn, mx = self.df[col].min(), self.df[col].max()
            if mx - mn < 1e-6: mx = mn + 1.0
            self.scaler_params[col] = {'min': float(mn), 'max': float(mx)}
            self.df[col] = (self.df[col] - mn) / (mx - mn)
        
        print(f"✅ Chuẩn hóa hoàn tất: {len(self.df)} dòng.")
        return self.df
    
    def create_sequences(self, seq_len=72, forecast_horizon=168):
        data = self.df[self.FEATURES].values.astype(np.float32)
        total_len = seq_len + forecast_horizon
        if len(data) < total_len: return None, None
        
        # Split data into train, val, test
        total_samples = len(data) - total_len + 1
        train_size = int(total_samples * self.train_ratio)
        val_size = int(total_samples * self.val_ratio)
        test_size = total_samples - train_size - val_size

        if train_size <= 0 or val_size <= 0 or test_size <= 0:
            raise ValueError("Not enough data to create train, validation, and test sets with specified ratios.")

        windows = np.lib.stride_tricks.as_strided(data, shape=(total_samples, total_len, len(self.FEATURES)), strides=(data.strides[0], data.strides[0], data.strides[1]))

        X_all = windows[:, :seq_len, :]
        y_all = windows[:, seq_len:, :]

        X_train, y_train = X_all[:train_size], y_all[:train_size]
        X_val, y_val = X_all[train_size:train_size + val_size], y_all[train_size:train_size + val_size]
        X_test, y_test = X_all[train_size + val_size:], y_all[train_size + val_size:]

        print(f"✅ Tạo {len(X_train)} sequences cho training, {len(X_val)} cho validation, {len(X_test)} cho testing.")
        return X_train, y_train, X_val, y_val, X_test, y_test