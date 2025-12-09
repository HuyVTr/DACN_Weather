# File: storm_pipeline/data_collector.py
# Module 2: Data Collector - HỖ TRỢ DỰ BÁO 7 NGÀY

import time
import requests
import os
import datetime

def get_gfs_forecast_times():
    """
    Tạo danh sách các forecast hours cho 7 ngày (mỗi 3 giờ).
    GFS cung cấp dự báo từ f000 đến f384 (16 ngày), 
    nhưng ta chỉ lấy 7 ngày đầu (168 giờ).
    """
    forecast_hours = []
    for hour in range(0, 169, 3):  # 0, 3, 6, 9... đến 168
        forecast_hours.append(f"f{hour:03d}")
    return forecast_hours


def get_gfs_run_times(num_runs=4):
    """
    Xác định các GFS run gần nhất (00Z, 06Z, 12Z, 18Z).
    Trả về danh sách các cặp (run_date_str, run_hour_str), từ mới nhất đến cũ nhất.
    """
    run_times = []
    now_utc = datetime.datetime.utcnow()
    
    # Bắt đầu từ 6 giờ trước để đảm bảo dữ liệu đã có
    current_check_time = now_utc - datetime.timedelta(hours=6)

    # Các giờ chạy GFS chuẩn
    gfs_cycle_hours = [0, 6, 12, 18]

    for _ in range(num_runs):
        # Tìm GFS cycle gần nhất trong quá khứ hoặc hiện tại
        run_hour_candidate = (current_check_time.hour // 6) * 6 
        
        run_date_str = current_check_time.strftime('%Y%m%d')
        run_hour_str = f"{run_hour_candidate:02d}"
        
        run_times.append((run_date_str, run_hour_str))
        
        # Lùi thời gian về cycle trước đó
        current_check_time -= datetime.timedelta(hours=6)
        
    return run_times

def download_gfs_forecast(forecast_hour="f000", output_dir=".", gfs_run_date=None, gfs_run_hour=None):
    """
    Tải dữ liệu GFS cho TOÀN BỘ BIỂN ĐÔNG với forecast hour cụ thể.
    
    Args:
        forecast_hour: f000, f003, f006... f168
        output_dir: Thư mục lưu file
        gfs_run_date: Ngày của GFS run (YYYYMMDD). Nếu None, sẽ tự động xác định.
        gfs_run_hour: Giờ của GFS run (HH). Nếu None, sẽ tự động xác định.
    
    Returns:
        Path đến file đã tải hoặc None nếu lỗi
    """
    # Khu vực Biển Đông
    top_lat = 26
    bottom_lat = 3
    left_lon = 100
    right_lon = 121

    print(f"📥 Đang tải GFS {forecast_hour} cho Biển Đông...")

    if gfs_run_date is None or gfs_run_hour is None:
        # Nếu không được chỉ định, lấy lần chạy mới nhất (chỉ 1 lần)
        run_date, run_hour = get_gfs_run_times(num_runs=1)[0]
    else:
        run_date, run_hour = gfs_run_date, gfs_run_hour
    
    # GFS 0.25 degree resolution
    base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    
    # Tên file GFS
    gfs_file = f"gfs.t{run_hour}z.pgrb2.0p25.{forecast_hour}"
    
    params = {
        "file": gfs_file,
        
        # === Variables: Chọn tất cả các biến cần thiết ===
        "var_UGRD": "on",    # U-component of wind
        "var_VGRD": "on",    # V-component of wind
        "var_RH": "on",      # Relative Humidity (for 'r')
        "var_TMP": "on",     # Temperature (for 't' and 'sst')
        "var_PRMSL": "on",   # Pressure Reduced to MSL
        
        # === Levels: Chọn tất cả các tầng khí quyển cần thiết ===
        "lev_10_m_above_ground": "on",   # For u10, v10
        "lev_200_mb": "on",              # For u_200
        "lev_850_mb": "on",              # For u_850, v_850, r_850, t_850
        "lev_mean_sea_level": "on",      # For prmsl
        "lev_surface": "on",             # For SST (TMP at surface)
        
        # Giới hạn vùng Biển Đông
        "subregion": "",
        "toplat": top_lat,
        "leftlon": left_lon,
        "rightlon": right_lon,
        "bottomlat": bottom_lat,
        
        # Thư mục trên server NOAA
        "dir": f"/gfs.{run_date}/{run_hour}/atmos"
    }

    max_retries = 5
    initial_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get(base_url, params=params, stream=True, timeout=60)
            
            if response.status_code == 200:
                filename = f"biendong_gfs_{run_date}_{run_hour}z_{forecast_hour}.grib2"
                full_path = os.path.join(output_dir, filename)
                
                with open(full_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # --- Data Validation ---
                file_size = os.path.getsize(full_path)
                if file_size < 10 * 1024: # Less than 10KB, likely an error page or empty
                    print(f"❌ Kích thước tệp quá nhỏ ({file_size / 1024:.2f} KB) cho {filename}. Có thể là lỗi tải xuống. Đang thử lại (lần {attempt + 1}/{max_retries})...")
                    os.remove(full_path) # Clean up partial/corrupt file
                    time.sleep(initial_delay * (2 ** attempt))
                    continue
                
                with open(full_path, 'rb') as f:
                    header = f.read(4)
                    if header != b'GRIB':
                        print(f"❌ Header tệp không hợp lệ ({header}) cho {filename}. Không phải GRIB2. Đang thử lại (lần {attempt + 1}/{max_retries})...")
                        os.remove(full_path) # Clean up invalid file
                        time.sleep(initial_delay * (2 ** attempt))
                        continue

                file_size_mb = file_size / (1024 * 1024)
                print(f"✅ Đã tải và xác thực: {filename} ({file_size_mb:.2f} MB)")
                return full_path
            
            elif response.status_code == 404:
                print(f"❌ HTTP 404 Not Found for {forecast_hour}. Có thể file chưa sẵn sàng. Đang thử lại (lần {attempt + 1}/{max_retries})...")
                time.sleep(initial_delay * (2 ** attempt)) # Exponential backoff
                continue

            else:
                print(f"❌ HTTP {response.status_code} cho {forecast_hour}. Đang thử lại (lần {attempt + 1}/{max_retries})...")
                print(f"URL: {response.url}")
                time.sleep(initial_delay * (2 ** attempt)) # Exponential backoff
                continue
                
        except requests.exceptions.Timeout:
            print(f"⏱️  Timeout khi tải {forecast_hour}. Đang thử lại (lần {attempt + 1}/{max_retries})...")
            time.sleep(initial_delay * (2 ** attempt))
            continue
        except requests.exceptions.ConnectionError:
            print(f"🔌 Lỗi kết nối khi tải {forecast_hour}. Đang thử lại (lần {attempt + 1}/{max_retries})...")
            time.sleep(initial_delay * (2 ** attempt))
            continue
        except Exception as e:
            print(f"❌ Lỗi không xác định khi tải {forecast_hour}: {e}. Đang thử lại (lần {attempt + 1}/{max_retries})...")
            time.sleep(initial_delay * (2 ** attempt))
            continue
            
    print(f"⛔ Thất bại sau {max_retries} lần thử cho {forecast_hour}.")
    return None

def robust_download_gfs_forecast(forecast_hour="f000", output_dir="."):
    """
    Thử tải GFS forecast từ các nguồn khác nhau: NOAA là ưu tiên, sau đó là AWS S3.
    Lặp qua các lần chạy GFS gần nhất cho mỗi nguồn.
    """
    gfs_run_candidates = get_gfs_run_times(num_runs=4) # Thử 4 lần chạy gần nhất (24 giờ)
    
    # --- 1. Thử tải từ NOAA ---
    print(f"🔄 Đang thử tải GFS {forecast_hour} từ NOAA...")
    for run_date, run_hour in gfs_run_candidates:
        print(f"   -> Đang thử NOAA run: {run_date} {run_hour}z...")
        file_path = download_gfs_forecast(forecast_hour, output_dir, run_date, run_hour)
        if file_path:
            return file_path
    
    print(f"❌ Không thể tải GFS forecast {forecast_hour} từ NOAA sau nhiều lần thử. Đang chuyển sang AWS S3...")

    # --- 2. Thử tải từ AWS S3 nếu NOAA thất bại ---
    print(f"🔄 Đang thử tải GFS {forecast_hour} từ AWS S3...")
    for run_date, run_hour in gfs_run_candidates:
        print(f"   -> Đang thử AWS S3 run: {run_date} {run_hour}z...")
        file_path = download_gfs_from_aws(forecast_hour, output_dir, run_date, run_hour)
        if file_path:
            return file_path
            
    print(f"⛔ Thất bại sau nhiều lần thử từ cả NOAA và AWS S3 cho {forecast_hour}.")
    return None

def download_gfs_data(storm_lat=None, storm_lon=None, output_dir="."):
    """
    Wrapper để tương thích với code cũ.
    Tải dữ liệu hiện tại (f000) một cách mạnh mẽ.
    """
    return robust_download_gfs_forecast("f000", output_dir)


def download_all_forecasts(output_dir=".", max_forecasts=57):
    """
    Tải tất cả các forecast cho 7 ngày (mỗi 3 giờ = 57 forecasts).
    Sử dụng robust_download_gfs_forecast để có logic dự phòng.
    """
    forecast_hours = get_gfs_forecast_times()[:max_forecasts]
    downloaded_files = []
    
    print(f"\n{'='*60}")
    print(f"🌐 BẮT ĐẦU TẢI DỰ BÁO 7 NGÀY (tổng {len(forecast_hours)} files)")
    print(f"{'='*60}\n")
    
    for i, fh in enumerate(forecast_hours, 1):
        print(f"[{i}/{len(forecast_hours)}] ", end="")
        file_path = robust_download_gfs_forecast(fh, output_dir)
        
        if file_path:
            downloaded_files.append(file_path)
    
    print(f"\n{'='*60}")
    print(f"✅ HOÀN TẤT: Đã tải {len(downloaded_files)}/{len(forecast_hours)} files")
    print(f"{'='*60}\n")
    
    return downloaded_files



def download_gfs_72h_sequence(output_dir="."):
    """
    Tải chuỗi dự báo GFS 72 giờ (từ f000 đến f072, mỗi 3 giờ = 25 files).
    Sử dụng robust_download_gfs_forecast để có logic dự phòng.
    """
    forecast_hours_72h = []
    for hour in range(0, 73, 3): # 0, 3, ..., 72
        forecast_hours_72h.append(f"f{hour:03d}")
        
    downloaded_files = []
    
    print(f"\n{'='*60}")
    print(f"🌐 BẮT ĐẦU TẢI CHUỖI DỰ BÁO GFS 72 GIỜ (tổng {len(forecast_hours_72h)} files)")
    print(f"{'='*60}\n")
    
    for i, fh in enumerate(forecast_hours_72h, 1):
        print(f"[{i}/{len(forecast_hours_72h)}] ", end="")
        file_path = robust_download_gfs_forecast(fh, output_dir)
        
        if file_path:
            downloaded_files.append(file_path)
            
    print(f"\n{'='*60}")
    print(f"✅ HOÀN TẤT: Đã tải {len(downloaded_files)}/{len(forecast_hours_72h)} files cho chuỗi 72 giờ")
    print(f"{'='*60}\n")
    
    # Sắp xếp các file theo forecast hour để đảm bảo đúng thứ tự
    downloaded_files.sort()
    return downloaded_files

def download_gfs_from_aws(forecast_hour="f000", output_dir=".", gfs_run_date=None, gfs_run_hour=None):
    """
    Tải dữ liệu GFS từ AWS Public Dataset (s3://noaa-gfs-bdp-pds/).
    Sử dụng URL trực tiếp qua HTTPS.
    Bao gồm cơ chế thử lại và xác thực dữ liệu.
    """
    print(f"📥 Đang tải GFS {forecast_hour} cho Biển Đông từ AWS S3...")

    if gfs_run_date is None or gfs_run_hour is None:
        run_date, run_hour = get_gfs_run_times(num_runs=1)[0]
    else:
        run_date, run_hour = gfs_run_date, gfs_run_hour

    # Cấu trúc URL AWS S3:
    # https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20230101/00/atmos/gfs.t00z.pgrb2.0p25.f000
    base_url_aws = f"https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{run_date}/{run_hour}/atmos"
    gfs_file = f"gfs.t{run_hour}z.pgrb2.0p25.{forecast_hour}"
    full_url = f"{base_url_aws}/{gfs_file}"

    max_retries = 5
    initial_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.get(full_url, stream=True, timeout=60)

            if response.status_code == 200:
                filename = f"biendong_gfs_{run_date}_{run_hour}z_{forecast_hour}_aws.grib2" # Đổi tên để phân biệt
                full_path = os.path.join(output_dir, filename)

                with open(full_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # --- Data Validation ---
                file_size = os.path.getsize(full_path)
                if file_size < 10 * 1024:  # Less than 10KB, likely an error page or empty
                    print(f"❌ Kích thước tệp quá nhỏ ({file_size / 1024:.2f} KB) từ AWS S3 cho {filename}. Có thể là lỗi tải xuống. Đang thử lại (lần {attempt + 1}/{max_retries})...")
                    os.remove(full_path)  # Clean up partial/corrupt file
                    time.sleep(initial_delay * (2 ** attempt))
                    continue

                with open(full_path, 'rb') as f:
                    header = f.read(4)
                    if header != b'GRIB':
                        print(f"❌ Header tệp không hợp lệ ({header}) từ AWS S3 cho {filename}. Không phải GRIB2. Đang thử lại (lần {attempt + 1}/{max_retries})...")
                        os.remove(full_path)  # Clean up invalid file
                        time.sleep(initial_delay * (2 ** attempt))
                        continue

                file_size_mb = file_size / (1024 * 1024)
                print(f"✅ Đã tải và xác thực từ AWS S3: {filename} ({file_size_mb:.2f} MB)")
                return full_path

            elif response.status_code == 404:
                print(f"❌ HTTP 404 Not Found từ AWS S3 cho {forecast_hour}. File có thể chưa sẵn sàng hoặc không tồn tại. Đang thử lại (lần {attempt + 1}/{max_retries})...")
                time.sleep(initial_delay * (2 ** attempt))  # Exponential backoff
                continue

            else:
                print(f"❌ HTTP {response.status_code} từ AWS S3 cho {forecast_hour}. Đang thử lại (lần {attempt + 1}/{max_retries})...")
                print(f"URL: {full_url}")
                time.sleep(initial_delay * (2 ** attempt))  # Exponential backoff
                continue

        except requests.exceptions.Timeout:
            print(f"⏱️  Timeout khi tải {forecast_hour} từ AWS S3. Đang thử lại (lần {attempt + 1}/{max_retries})...")
            time.sleep(initial_delay * (2 ** attempt))
            continue
        except requests.exceptions.ConnectionError:
            print(f"🔌 Lỗi kết nối khi tải {forecast_hour} từ AWS S3. Đang thử lại (lần {attempt + 1}/{max_retries})...")
            time.sleep(initial_delay * (2 ** attempt))
            continue
        except Exception as e:
            print(f"❌ Lỗi không xác định khi tải {forecast_hour} từ AWS S3: {e}. Đang thử lại (lần {attempt + 1}/{max_retries})...")
            time.sleep(initial_delay * (2 ** attempt))
            continue

    print(f"⛔ Thất bại sau {max_retries} lần thử cho {forecast_hour} từ AWS S3.")
    return None


# Test
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # Tải tất cả forecasts
        download_all_forecasts("data", max_forecasts=10)  # Test với 10 files
    elif len(sys.argv) > 1 and sys.argv[1] == "--72h":
        # Tải chuỗi 72h
        download_gfs_72h_sequence("data")
    elif len(sys.argv) > 1 and sys.argv[1] == "--aws":
        # Tải 1 file từ AWS
        download_gfs_from_aws("f000", "data")
    else:
        # Tải 1 file (robust)
        robust_download_gfs_forecast("f000", "data")