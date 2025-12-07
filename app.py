"""
WEATHER_PROJECT - Flask Application
File chính duy nhất để khởi động hệ thống dự báo thời tiết
Đặt tại: WEATHER_PROJECT/app.py
"""
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# ============================================================================
# THIẾT LẬP ĐƯỜNG DẪN
# ============================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_API_DIR = os.path.join(CURRENT_DIR, "backend_api")
SERVICES_DIR = os.path.join(CURRENT_DIR, "services")

# Thêm các thư mục vào Python path
sys.path.insert(0, BACKEND_API_DIR)
sys.path.append(os.path.join(SERVICES_DIR, "forecast_ml"))

print(f"📂 Project Root: {CURRENT_DIR}")
print(f"📂 Backend API: {BACKEND_API_DIR}")
print(f"📂 Services: {SERVICES_DIR}")

# ============================================================================
# IMPORT MODULES
# ============================================================================
try:
    from backend_api.models import db
    from backend_api.controllers import register_blueprints
    print("✅ Import models và controllers thành công")
except ImportError as e:
    print(f"❌ Lỗi import: {e}")
    print("⚠️  Kiểm tra cấu trúc thư mục backend_api/")
    sys.exit(1)

# ============================================================================
# CẤU HÌNH DATABASE
# ============================================================================
DB_USERNAME = "postgres"
# Mật khẩu bạn dùng để đăng nhập vào pgAdmin (nếu là 123456 thì giữ nguyên)
DB_PASSWORD = os.environ.get('DB_PASSWORD', '123456') 

DB_HOST = "localhost"       # Host mặc định
DB_PORT = "5432"            # Cổng mặc định của PostgreSQL
DB_NAME = "weather_project" # Tên database

DATABASE_URI = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Cảnh báo bảo mật
if DB_PASSWORD == '123456':
    print("⚠️" * 30)
    print("⚠️  CẢNH BÁO BẢO MẬT: Đang dùng mật khẩu mặc định!")
    print("⚠️  Đặt biến môi trường: set DB_PASSWORD=your_password")
    print("⚠️" * 30)

# ============================================================================
# TẠO FLASK APP
# ============================================================================
def create_app():
    """
    Factory function tạo và cấu hình Flask application
    
    Returns:
        Flask: Configured Flask app instance
    """
    
    # Khởi tạo Flask với đường dẫn templates và static
    app = Flask(
        __name__,
        template_folder=os.path.join(BACKEND_API_DIR, 'templates'),
        static_folder=os.path.join(BACKEND_API_DIR, 'static')
    )
    
    # Cấu hình Flask
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JSON_AS_ASCII'] = False  # Hỗ trợ tiếng Việt
    
    # Khởi tạo database
    db.init_app(app)
    
    # Đăng ký các Blueprints (routes/controllers)
    register_blueprints(app)
    
    # Log thông tin
    print("=" * 80)
    print("✅ Flask Application đã được khởi tạo thành công!")
    print("=" * 80)
    print(f"📁 Templates: {app.template_folder}")
    print(f"📁 Static: {app.static_folder}")
    print(f"🗄️  Database: {DB_HOST}/{DB_NAME}")
    print("=" * 80)
    
    return app

# ============================================================================
# KHỞI ĐỘNG SERVER (CHỈ KHI CHẠY TRỰC TIẾP)
# ============================================================================
if __name__ == "__main__":
    app = create_app()
    
    print("\n🚀 Khởi động Flask Development Server...")
    print("🌐 Địa chỉ: http://127.0.0.1:5000")
    print("💡 Nhấn Ctrl+C để dừng server\n")
    
    # Chạy Flask server
    app.run(
        debug=True,
        host='0.0.0.0',
        port=8000,
        use_reloader=False  # Tắt reloader khi chạy với start_system.py
    )