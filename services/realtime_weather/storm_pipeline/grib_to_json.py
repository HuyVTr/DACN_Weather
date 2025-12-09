import xarray as xr
import json
import numpy as np

def grib_to_json(grib_file_path):
    """
    Mở file GRIB2, trích xuất các biến và chuyển đổi thành JSON.
    FIX: 
    - Xử lý multiple stepType (instant → avg)
    - Xử lý file corrupted
    - Xử lý thiếu biến
    """
    try:
        # Thử mở với stepType = instant
        try:
            ds = xr.open_dataset(
                grib_file_path,
                engine="cfgrib",
                backend_kwargs={
                    'indexpath': '',
                    'filter_by_keys': {'stepType': 'instant'},
                    'errors': 'ignore'   # ← Bỏ qua lỗi corrupted
                }
            )
        except:
            # Nếu không có instant, thử avg
            ds = xr.open_dataset(
                grib_file_path,
                engine="cfgrib",
                backend_kwargs={
                    'indexpath': '',
                    'filter_by_keys': {'stepType': 'avg'},
                    'errors': 'ignore'
                }
            )

        # Danh sách biến bắt buộc
        required_vars = ['latitude', 'longitude', 'prmsl', 'u10', 't']
        missing_vars = [v for v in required_vars if v not in ds.variables and v not in ds.coords]

        if missing_vars:
            print(f"⚠️ File thiếu biến: {missing_vars}")
            return json.dumps({
                "lat": [],
                "lon": [],
                "prmsl": [],
                "u": [],
                "v": [],
                "temp": []
            })

        # Nếu thiếu v10 → thay bằng zeros cùng shape với u10
        v_wind = ds['v10'].data if 'v10' in ds.variables else np.zeros_like(ds['u10'].data)

        # Build output data
        data = {
            "lat": ds['latitude'].data.tolist(),
            "lon": ds['longitude'].data.tolist(),
            "prmsl": ds['prmsl'].data.tolist(),
            "u": ds['u10'].data.tolist(),
            "v": v_wind.tolist(),
            "temp": ds['t'].data.tolist()
        }

        ds.close()
        return json.dumps(data, indent=4)

    except Exception as e:
        print(f"Lỗi khi xử lý file GRIB: {e}")
        # Trả về rỗng thay vì crash
        return json.dumps({
            "lat": [],
            "lon": [],
            "prmsl": [],
            "u": [],
            "v": [],
            "temp": []
        })
