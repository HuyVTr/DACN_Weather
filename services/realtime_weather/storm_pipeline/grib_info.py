# File: storm_pipeline/grib_info.py
# Module để lấy metadata và summary từ file GRIB2

import xarray as xr
import json
import os
from datetime import datetime

def get_grib_info(grib_file_path):
    """
    Lấy thông tin metadata đầy đủ.
    """
    try:
        ds = xr.open_dataset(
            grib_file_path,
            engine="cfgrib",
            backend_kwargs={'indexpath': ''}
        )

        file_stat = os.stat(grib_file_path)
        file_size_mb = file_stat.st_size / (1024 * 1024)
        file_modified = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

        # === FIX FutureWarning: dùng ds.sizes thay vì ds.dims ===
        variables_info = {}
        for var_name in ds.data_vars:
            var = ds[var_name]
            variables_info[var_name] = {
                "dims": list(var.dims),
                "shape": list(var.shape),
                "dtype": str(var.dtype),
                "attrs": dict(var.attrs) if var.attrs else {}
            }

        coords_info = {}
        for coord_name in ds.coords:
            coord = ds[coord_name]
            coords_info[coord_name] = {
                "shape": list(coord.shape),
                "dtype": str(coord.dtype),
                "min": float(coord.min().values) if hasattr(coord.min(), 'values') else None,
                "max": float(coord.max().values) if hasattr(coord.max(), 'values') else None,
                "attrs": dict(coord.attrs) if coord.attrs else {}
            }

        info = {
            "file_name": os.path.basename(grib_file_path),
            "file_size_mb": round(file_size_mb, 2),
            "file_modified": file_modified,
            "variables": variables_info,
            "coordinates": coords_info,

            # === FIX FutureWarning ===
            "dimensions": dict(ds.sizes),

            "attributes": dict(ds.attrs),
            "variable_count": len(ds.data_vars),
            "coordinate_count": len(ds.coords)
        }

        ds.close()
        return info

    except Exception as e:
        print(f"Lỗi khi đọc metadata file GRIB: {e}")
        return None


def get_grib_summary(grib_file_path):
    """
    Lấy tóm tắt nhanh về file GRIB.
    """
    try:
        ds = xr.open_dataset(
            grib_file_path,
            engine="cfgrib",
            backend_kwargs={'indexpath': ''}
        )

        file_stat = os.stat(grib_file_path)
        file_size_mb = file_stat.st_size / (1024 * 1024)
        file_size_kb = file_stat.st_size / 1024

        # === FIX FutureWarning: dùng ds.sizes ===
        total_points = 1
        for dim_size in ds.sizes.values():
            total_points *= dim_size

        # Lấy lat/lon resolution
        lat_resolution = None
        lon_resolution = None
        if "latitude" in ds.coords and "longitude" in ds.coords:
            lat = ds["latitude"]
            lon = ds["longitude"]
            if len(lat) > 1:
                lat_resolution = float((lat.max() - lat.min()) / (len(lat) - 1))
            if len(lon) > 1:
                lon_resolution = float((lon.max() - lon.min()) / (len(lon) - 1))

        # Chi tiết biến
        variables_detail = {}
        for var_name in ds.data_vars:
            var = ds[var_name]
            v = {
                "name": var_name,
                "shape": list(var.shape),
                "dtype": str(var.dtype),
                "dimensions": list(var.dims),
                "attrs": {}
            }
            # Giữ các attrs quan trọng
            for key in ['long_name', 'standard_name', 'units', 'GRIB_name', 'GRIB_units']:
                if key in var.attrs:
                    v["attrs"][key] = str(var.attrs[key])

            try:
                var_data = var.values
                v["min"] = float(var_data.min())
                v["max"] = float(var_data.max())
                v["mean"] = float(var_data.mean())
            except:
                pass

            variables_detail[var_name] = v

        summary = {
            "file_name": os.path.basename(grib_file_path),
            "file_size_mb": round(file_size_mb, 2),
            "file_size_kb": round(file_size_kb, 2),
            "file_size_bytes": file_stat.st_size,
            "variables": list(ds.data_vars.keys()),
            "variables_detail": variables_detail,

            # === FIX ===
            "dimensions": dict(ds.sizes),

            "total_data_points": int(total_points),
            "lat_resolution": lat_resolution,
            "lon_resolution": lon_resolution,
            "lat_range": None,
            "lon_range": None,
            "lat_count": None,
            "lon_count": None,
            "time_info": None,
            "attributes": {}
        }

        # Latitude
        if "latitude" in ds.coords:
            lat = ds["latitude"]
            summary["lat_range"] = [float(lat.min()), float(lat.max())]
            summary["lat_count"] = len(lat)

        # Longitude
        if "longitude" in ds.coords:
            lon = ds["longitude"]
            summary["lon_range"] = [float(lon.min()), float(lon.max())]
            summary["lon_count"] = len(lon)

        # === FIX LỖI 'numpy.datetime64' object is not iterable ===
        if "time" in ds.coords:
            t = ds["time"]

            if hasattr(t.values, "__len__") and t.values.ndim > 0:
                # nhiều time steps
                values = [str(v) for v in t.values]
            else:
                # chỉ 1 timestamp → convert trực tiếp
                values = [str(t.values)]

            time_info = {
                "values": values,
                "count": len(values)
            }

            summary["time_info"] = time_info

        # Dataset attributes
        if ds.attrs:
            summary["attributes"] = {k: str(v) for k, v in ds.attrs.items()}

        ds.close()
        return summary

    except Exception as e:
        print(f"Lỗi khi đọc summary file GRIB: {e}")
        return None
