# WORKER TỰ ĐỘNG HOÀN TOÀN - REALTIME NOAA GFS
# Tự động tải dữ liệu mới + Quét bão liên tục (BIỂN ĐÔNG)

import time
import os
import json
import datetime
import traceback
import requests
import glob
import threading

from storm_pipeline.storm_monitor import check_for_storm
from storm_pipeline.data_collector import download_gfs_forecast, get_latest_gfs_run
from storm_pipeline.data_processor import process_gfs_data
from storm_pipeline.storm_detector_bot import StormDetectorBot

# ============================================
# CONFIG
# ============================================
STATUS_FILE = "status.json"          # File lưu trạng thái mới nhất
OUTPUT_DIR = "data"                  # Thư mục chứa GRIB2
STORM_CHECK_INTERVAL = 300          # 5 phút - Quét bão
GFS_UPDATE_INTERVAL = 21600         # 6 giờ - Tải GFS mới (theo chu kỳ NOAA)
API_URL = "http://127.0.0.1:8000/status"

# Danh sách forecast hours cần thiết (7 ngày, mỗi 3 giờ)
FORECAST_HOURS = [f"f{h:03d}" for h in range(0, 169, 3)]  # f000, f003... f168


# ============================================
# UPDATE STATUS
# ============================================
def update_status(status_message, data=None):
    """
    Ghi status ra file và POST sang API server (để WebSocket broadcast).
    KHÔNG để lỗi tại đây làm chết Worker.
    """
    timestamp = datetime.datetime.now().isoformat()
    status_data = {
        "last_update": timestamp,
        "status_message": status_message,
        "data": data or {}
    }

    # Ghi file cục bộ (fallback)
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ Lỗi ghi status.json: {e}")

    # Gửi sang API Server
    try:
        response = requests.post(API_URL, json=status_data, timeout=5)
        if response.status_code == 200:
            print(f"🚀 Đã gửi status: {status_message}")
        else:
            print(f"⚠️ Lỗi API server: HTTP {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        # Không chết Worker, chỉ cảnh báo
        print(f"⚠️ API server chưa sẵn sàng: {e}")


# ============================================
# KIỂM TRA & TẢI DỮ LIỆU GFS MỚI
# ============================================
def check_and_download_gfs():
    """
    Kiểm tra xem đã có dữ liệu GFS run mới nhất chưa.
    Nếu chưa -> Tải tất cả forecast hours cần thiết (f000..f168).
    """
    print("\n" + "=" * 60)
    print("📡 KIỂM TRA DỮ LIỆU GFS MỚI (NOAA GFS 0.25° - BIỂN ĐÔNG)")
    print("=" * 60)

    run_date, run_hour = get_latest_gfs_run()
    expected_pattern = f"biendong_gfs_{run_date}_{run_hour}z_*.grib2"

    existing_files = glob.glob(os.path.join(OUTPUT_DIR, expected_pattern))

    if len(existing_files) >= len(FORECAST_HOURS):
        print(f"✅ Đã có dữ liệu GFS run {run_date} {run_hour}Z ({len(existing_files)} files)")
        return True

    print(f"📥 Đang tải dữ liệu GFS run mới: {run_date} {run_hour}Z")
    update_status(f"📥 Đang tải dữ liệu GFS run {run_date} {run_hour}Z...")

    # Tải tất cả forecast hours
    success_count = 0
    total = len(FORECAST_HOURS)

    for i, fh in enumerate(FORECAST_HOURS, 1):
        print(f"[{i}/{total}] Tải {fh}...")
        file_path = download_gfs_forecast(fh, OUTPUT_DIR)
        if file_path:
            success_count += 1
            update_status(f"📥 Đang tải GFS: {i}/{total} files...")
        else:
            print(f"⚠️ Lỗi tải {fh}")

        # Nghỉ 2s để tránh rate limit
        if i < total:
            time.sleep(2)

    print(f"✅ Hoàn tất tải GFS: {success_count}/{total} files")
    update_status(f"✅ Đã tải xong dữ liệu GFS ({success_count}/{total} files)")

    return success_count > 0


# ============================================
# KIỂM TRA BÃO
# ============================================
def check_storm_routine():
    """
    Quét bão từ dữ liệu GRIB2 mới nhất trong thư mục data/.
    Dùng thuật toán NOAA GFS trong storm_monitor.py.
    """
    print("\n" + "=" * 60)
    print(f"🔍 QUÉT BÃO (NOAA GFS) - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        update_status("🔍 Đang quét NOAA GFS để phát hiện bão...")
        storm = check_for_storm()

        if storm:
            print(f"\n{'🚨' * 20}")
            print(f"⚠️  PHÁT HIỆN BÃO: {storm['name']}")
            print(f"📍 Vị trí: {storm['lat']}°N, {storm['lon']}°E")
            print(f"🌡️  Áp suất: {storm['pressure']} hPa")
            print(f"{'🚨' * 20}\n")

            update_status(
                f"⚠️ PHÁT HIỆN BÃO: {storm['name']} tại {storm['lat']}°N, {storm['lon']}°E",
                storm
            )
            return storm
        else:
            print("✅ Biển Đông yên bình - Không có hoạt động bão")
            update_status("✅ Biển Đông yên bình - Không có hoạt động bão")
            return None

    except Exception as e:
        print(f"❌ Lỗi khi quét bão: {e}")
        traceback.print_exc()
        update_status(f"❌ Lỗi quét bão: {e}")
        return None


# ============================================
# THREAD: TỰ ĐỘNG TẢI GFS MỖI 6 GIỜ
# ============================================
def gfs_auto_downloader():
    """
    Thread riêng để tự động tải GFS mỗi 6 giờ.
    """
    print("🔄 Khởi động GFS Auto Downloader Thread...")

    while True:
        try:
            check_and_download_gfs()
        except Exception as e:
            print(f"❌ Lỗi GFS downloader: {e}")
            traceback.print_exc()

        # Nghỉ 6 giờ
        print(f"\n💤 GFS downloader nghỉ {GFS_UPDATE_INTERVAL // 3600} giờ...")
        time.sleep(GFS_UPDATE_INTERVAL)


# ============================================
# MAIN SYSTEM
# ============================================
def main_system():
    """
    Hàm chính của Worker:
      - Kiểm tra & tải dữ liệu GFS ban đầu
      - Khởi động thread tải GFS định kỳ
      - Vòng lặp chính: quét bão mỗi 5 phút
    """
    print("=" * 80)
    print("🌀 KHỞI ĐỘNG HỆ THỐNG REALTIME BÃO (v4 - TỰ ĐỘNG HOÀN TOÀN)")
    print("=" * 80)
    print(f"📍 Khu vực: BIỂN ĐÔNG (3°N-26°N, 100°E-121°E)")
    print(f"⏱️  Quét bão: Mỗi {STORM_CHECK_INTERVAL // 60} phút")
    print(f"📡 Tải GFS: Mỗi {GFS_UPDATE_INTERVAL // 3600} giờ")
    print(f"🌐 Nguồn: NOAA GFS (dự báo + phát hiện bão)")
    print(f"🔗 API: {API_URL}")
    print("=" * 80)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # === BƯỚC 1: Tải dữ liệu GFS ban đầu ===
    print("\n🚀 BƯỚC 1: Kiểm tra & tải dữ liệu GFS ban đầu...")
    check_and_download_gfs()

    # === BƯỚC 2: Khởi động thread tự động tải GFS ===
    print("\n🚀 BƯỚC 2: Khởi động GFS Auto Downloader...")
    gfs_thread = threading.Thread(target=gfs_auto_downloader, daemon=True)
    gfs_thread.start()

    # Khởi tạo bot
    bot = StormDetectorBot()

    # === BƯỚC 3: Vòng lặp chính - Quét bão liên tục ===
    print("\n🚀 BƯỚC 3: Bắt đầu quét bão realtime...\n")

    loop_count = 0
    while True:
        loop_count += 1
        print(f"\n🔄 VÒNG QUÉT #{loop_count}")

        try:
            # 1. Quét bão cũ
            storm = check_storm_routine()
           
            # 2. BOT TỰ ĐỘNG QUÉT TOÀN BỘ BIỂN ĐÔNG
            alerts = bot.scan_south_china_sea()
           
            # 3. Gửi alerts qua WebSocket
            if alerts:
                alerts_data = bot.get_alerts_json()
                update_status(
                    f"⚠️ PHÁT HIỆN {len(alerts)} VÙNG NGUY HIỂM",
                    alerts_data
                )
            else:
                update_status("✅ Biển Đông yên bình - Không có nguy hiểm")
           
        except KeyboardInterrupt:
            print("\n\n⏹️  Dừng hệ thống theo yêu cầu người dùng")
            update_status("⏹️ Hệ thống đã dừng")
            break

        except Exception as e:
            print(f"\n❌ LỖI KHÔNG XÁC ĐỊNH: {e}")
            traceback.print_exc()
            update_status(f"❌ Lỗi hệ thống: {e}")

        # Nghỉ trước khi quét tiếp
        next_scan = datetime.datetime.now() + datetime.timedelta(seconds=STORM_CHECK_INTERVAL)
        print("\n" + "─" * 60)
        print(f"😴 Nghỉ {STORM_CHECK_INTERVAL // 60} phút...")
        print(f"⏰ Quét tiếp theo vào: {next_scan.strftime('%H:%M:%S')}")
        print("─" * 60)

        update_status(
            f"💤 Hệ thống chờ... Quét tiếp theo vào ~{next_scan.strftime('%H:%M:%S')}"
        )

        time.sleep(STORM_CHECK_INTERVAL)


# ============================================
# RUN
# ============================================
if __name__ == "__main__":
    try:
        main_system()
    except KeyboardInterrupt:
        print("\n\n👋 Tạm biệt!")
    except Exception as e:
        print(f"\n💥 Lỗi nghiêm trọng: {e}")
        traceback.print_exc()