import json
import pandas as pd
import os
from datetime import datetime
import numpy as np

# Giả định analysis_modules.py nằm cùng thư mục
from .analysis_modules import TrajectoryAnalyzer

# Bộ mã hóa JSON để xử lý các kiểu dữ liệu của NumPy
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

class FinalExporter:
    def __init__(self, output_dir=None):
        if output_dir is None:
            # Thiết lập đường dẫn động để trỏ đến thư mục processed_output
            SERVICE_ROOT = os.path.dirname(os.path.abspath(__file__))
            SERVICES_DIR = os.path.dirname(SERVICE_ROOT)
            PROJECT_ROOT = os.path.dirname(SERVICES_DIR)
            self.output_dir = os.path.join(PROJECT_ROOT, "project_data", "processed_output")
        else:
            self.output_dir = output_dir
            
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"📦 Dữ liệu xuất sẽ được lưu tại: {self.output_dir}")

    def export(self, predictions, scaler_params, timestamp, feature_names, origin_details=None, is_simulation=False, source_name='Unknown'):
        """
        Xuất dữ liệu dự báo ra file CSV và JSON, đồng thời chạy phân tích.
        """
        base_filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}"
        csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")
        json_path = os.path.join(self.output_dir, f"{base_filename}_analysis.json")

        # 1. Tạo DataFrame và lưu file CSV
        df = pd.DataFrame(predictions, columns=feature_names)
        df['hour'] = range(1, len(df) + 1)
        df.to_csv(csv_path, index=False)
        print(f"   -> ✅ Đã lưu quỹ đạo dự báo vào file: {os.path.basename(csv_path)}")

        # 2. Chạy phân tích quỹ đạo
        analysis_input = df[['LAT', 'LON', 'hour']].rename(columns={'LAT': 'lat', 'LON': 'lon'}).to_dict('records')
        analysis_results = TrajectoryAnalyzer.analyze_trajectory(analysis_input)
        print("   -> ✅ Đã chạy phân tích quỹ đạo.")

        # 3. Chuẩn bị và lưu file JSON tổng hợp
        full_export_data = {
            "metadata": {
                "export_time": timestamp.isoformat(),
                "source": source_name,
                "is_simulation": is_simulation,
                "prediction_horizon_hours": len(df),
                "model_info": "FinalTFT"
            },
            "origin_storm_details": origin_details,
            "trajectory_analysis": analysis_results,
            "predicted_path": df.to_dict('records') # Thêm toàn bộ đường đi vào JSON
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(full_export_data, f, ensure_ascii=False, indent=4, cls=NumpyEncoder)
        print(f"   -> ✅ Đã lưu phân tích và kết quả vào file: {os.path.basename(json_path)}")
        
        return df, analysis_results
