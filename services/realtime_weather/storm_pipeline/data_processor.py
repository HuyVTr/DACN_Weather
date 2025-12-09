# File: storm_pipeline/data_processor.py
# Module 3: AI Inference Service (Phần tiền xử lý)
# *** PHIÊN BẢN ĐÃ SỬA LỖI ĐỌC GRIB ***
# File: storm_pipeline/data_processor.py
# Module 3: AI Inference Service (Phần tiền xử lý)
# *** PHIÊN BẢN SỬA LỖI LẦN 2 (DỰA TRÊN DEBUG LOG) ***

import xarray as xr
import numpy as np

def process_gfs_data(grib_file_path):
    """
    Mở file GRIB2, trích xuất các biến quan trọng và
    xếp chồng chúng thành một ma trận (tensor) 3D cho AI.
    """
    print(f"--> [Bước 3] Đang mở file: {grib_file_path}")
    
    try:
        # Dựa trên log gỡ lỗi của bạn, chúng ta có thể mở file MỘT LẦN
        # và tất cả các biến đều ở đó.
        # 'indexpath=''' là một mẹo để bỏ qua việc tạo file index .idx
        ds = xr.open_dataset(grib_file_path, 
                             engine="cfgrib",
                             backend_kwargs={'indexpath': ''})
        
        # Trích xuất các biến (tên biến lấy từ log gỡ lỗi của bạn)
        u_wind = ds['u10'].data    # Gió U
        v_wind = ds['v10'].data    # Gió V
        temp = ds['t'].data        # Nhiệt độ (tên là 't', không phải 't2m')
        msl = ds['prmsl'].data     # Áp suất

        # Xếp chồng các ma trận 2D thành một ma trận 3D (Channels, Lat, Lon)
        # (Số kênh = 4, Cao, Rộng)
        data_matrix = np.stack([u_wind, v_wind, temp, msl], axis=0)
        
        return data_matrix

    except Exception as e:
        print(f"Lỗi khi xử lý file GRIB: {e}")
        # In lại log nếu vẫn lỗi
        print("--- Thông tin gỡ lỗi file GRIB (thử đọc tất cả) ---")
        try:
            full_ds = xr.open_dataset(grib_file_path, engine="cfgrib", backend_kwargs={'indexpath': ''})
            print(full_ds)
        except Exception as de:
            print(f"Không thể in thông tin gỡ lỗi: {de}")
        return None