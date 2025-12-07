# KHỞI ĐỘNG TOÀN BỘ HỆ THỐNG NOAA REALTIME - CHỈ 1 LỆNH

import subprocess
import time
import sys
import os
import signal
import requests  # dùng để ping /health

processes = []  # lưu danh sách process để dừng gọn gàng


def cleanup(signum=None, frame=None):
    """Dọn dẹp các process khi thoát (Ctrl+C hoặc lỗi)."""
    print("\n\n🛑 Đang dừng tất cả dịch vụ...")

    for p in processes:
        if p is None:
            continue
        try:
            p.terminate()
            p.wait(timeout=5)
            print(f"✅ Đã dừng process PID {p.pid}")
        except Exception as e:
            print(f"⚠️ Lỗi khi dừng process {p.pid if p else '?'}: {e}")
            try:
                p.kill()
            except Exception:
                pass

    print("👋 Tạm biệt!\n")
    sys.exit(0)


# Bắt tín hiệu Ctrl+C / kill
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def wait_for_api_ready(url="http://127.0.0.1:8000/health", timeout=30):
    """
    Chờ API server sẵn sàng bằng cách gọi /health.
    Trả về True nếu OK, False nếu hết thời gian.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                print("🟢 API Server đã sẵn sàng!")
                return True
        except Exception:
            pass
        print("⏳ Đợi API server khởi động...")
        time.sleep(1)

    print("⚠️ Hết thời gian chờ API server. Vẫn tiếp tục khởi động Worker.")
    return False


def main():
    print("=" * 80)
    print("🌀 HỆ THỐNG NOAA STORM TRACKER - REALTIME BIỂN ĐÔNG")
    print("=" * 80)
    print("📦 Hệ thống sẽ tự động:")
    print("   1. Tải dữ liệu GFS từ NOAA mỗi 6 giờ")
    print("   2. Phát hiện bão từ dữ liệu NOAA")
    print("   3. Quét liên tục mỗi 5 phút")
    print("   4. Cập nhật realtime qua WebSocket")
    print("=" * 80)
    print()

    # Kiểm tra file cần thiết
    if not os.path.exists("worker_v4_auto.py"):
        print("❌ Không tìm thấy worker_v4_auto.py")
        sys.exit(1)

    if not os.path.exists("app.py"):
        print("❌ Không tìm thấy app.py")
        sys.exit(1)

    # Tạo thư mục cần thiết
    os.makedirs("data", exist_ok=True)
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)

    # KHÔNG cần ghi đè storm_monitor.py nữa
    # (file storm_pipeline/storm_monitor.py hiện đã là bản NOAA chuẩn)

    api_process = None
    worker_process = None

    try:
        # === BƯỚC 1: KHỞI ĐỘNG API SERVER TRƯỚC ===
        print("\n🚀 [1/2] Khởi động API Server (FastAPI + WebSocket)...")
        api_process = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        processes.append(api_process)
        print(f"✅ API Server đã khởi động (PID: {api_process.pid})")

        # Chờ API server sẵn sàng /health
        wait_for_api_ready()

        # === BƯỚC 2: KHỞI ĐỘNG WORKER SAU KHI API SẴN SÀNG ===
        print("\n🚀 [2/2] Khởi động Worker (tự động tải GFS + phát hiện bão từ NOAA)...")
        worker_process = subprocess.Popen(
            [sys.executable, "worker_v4_auto.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        processes.append(worker_process)
        print(f"✅ Worker đã khởi động (PID: {worker_process.pid})")

        print("\n" + "=" * 80)
        print("✅ HỆ THỐNG NOAA REALTIME ĐÃ SẴN SÀNG!")
        print("=" * 80)
        print("🌐 Frontend:  http://127.0.0.1:8000")
        print("📊 API Docs:  http://127.0.0.1:8000/docs")
        print("🔌 WebSocket: ws://127.0.0.1:8000/ws")
        print()
        print("📍 Khu vực: BIỂN ĐÔNG (3°N-26°N, 100°E-121°E)")
        print("🔍 Nguồn phát hiện bão: NOAA GFS")
        print("⏱️  Quét bão: Mỗi 5 phút")
        print("📡 Tải GFS mới: Mỗi 6 giờ (theo chu kỳ NOAA)")
        print("🎨 Hiệu ứng gió: Windy-style animation")
        print("=" * 80)
        print("\n💡 Nhấn Ctrl+C để dừng toàn bộ hệ thống")
        print()

        # === LOOP GIÁM SÁT LOG CẢ HAI PROCESS ===
        while True:
            # Kiểm tra API
            if api_process and api_process.poll() is None:
                line = api_process.stdout.readline()
                if line:
                    print(f"[API] {line.strip()}")
            elif api_process and api_process.poll() is not None:
                print("⚠️ API Server đã dừng!")
                api_process = None  # không còn theo dõi nữa

            # Kiểm tra Worker
            if worker_process and worker_process.poll() is None:
                line = worker_process.stdout.readline()
                if line:
                    print(f"[WORKER] {line.strip()}")
            elif worker_process and worker_process.poll() is not None:
                print("⚠️ Worker đã dừng!")
                worker_process = None  # không còn theo dõi nữa

            # Nếu cả hai đều dừng → thoát
            if api_process is None and worker_process is None:
                print("⚠️ Cả Worker và API Server đều đã dừng. Thoát chương trình.")
                break

            time.sleep(0.1)

    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        cleanup()


if __name__ == "__main__":
    main()
