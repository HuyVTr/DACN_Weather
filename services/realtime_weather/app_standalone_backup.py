# File: app.py
# Web Server với hỗ trợ DỰ BÁO 7 NGÀY và REAL-TIME WEBSOCKETS

import uvicorn
import json
import glob
import os
from typing import List
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from storm_pipeline.grib_to_json import grib_to_json
from storm_pipeline.grib_info import get_grib_info, get_grib_summary

STATUS_FILE = "status.json"
DATA_DIR = "data"

app = FastAPI()

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- Static Files ---
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- HTML Homepage ---
@app.get("/", response_class=HTMLResponse)
async def get_homepage(request: Request):
    """Serve trang chủ."""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy index.html")

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Giữ kết nối mở để nhận tin nhắn (nếu cần)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")

# --- API Endpoints ---

@app.post("/status")
async def update_status_and_notify(request: Request):
    """
    Worker gọi endpoint này để cập nhật status và thông báo cho clients.
    """
    try:
        status_data = await request.json()
        
        # Ghi vào file status.json
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4)
            
        # Broadcast cho tất cả client đang kết nối
        await manager.broadcast(json.dumps(status_data))
        
        return JSONResponse(content={"message": "Status updated and broadcasted successfully."})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi cập nhật status: {e}")


@app.get("/status")
async def get_status():
    """Trả về trạng thái hệ thống (đọc từ file)."""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Chưa có status. Hãy chạy worker.py.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc status: {e}")


@app.get("/grib-latest")
async def get_grib_latest():
    """Trả về dữ liệu GRIB2 mới nhất (f000)."""
    try:
        pattern = os.path.join(DATA_DIR, "*_f000.grib2")
        files = glob.glob(pattern)
        
        if not files:
            pattern = os.path.join(DATA_DIR, "*.grib2")
            files = glob.glob(pattern)
        
        if not files:
            raise HTTPException(status_code=404, detail="Chưa có dữ liệu GRIB2")

        latest = max(files, key=lambda p: os.path.getmtime(p))
        json_data = await run_in_threadpool(grib_to_json, latest)
        
        if json_data is None:
            raise HTTPException(status_code=500, detail="Không thể xử lý GRIB")

        return JSONResponse(content=json.loads(json_data))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {e}")


@app.get("/forecast")
async def get_forecast(hours: int = 0):
    """
    Trả về dữ liệu dự báo theo giờ.
    """
    try:
        hours = (hours // 3) * 3
        forecast_hour = f"f{hours:03d}"
        
        pattern = os.path.join(DATA_DIR, f"*_{forecast_hour}.grib2")
        files = glob.glob(pattern)
        
        if not files:
            raise HTTPException(
                status_code=404, 
                detail=f"Không tìm thấy dự báo cho {hours}h"
            )
        
        latest = max(files, key=lambda p: os.path.getmtime(p))
        json_data = await run_in_threadpool(grib_to_json, latest)
        
        if json_data is None:
            raise HTTPException(status_code=500, detail="Không thể xử lý GRIB")
        
        return JSONResponse(content=json.loads(json_data))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {e}")


@app.get("/forecast/available")
async def get_available_forecasts():
    """Trả về danh sách các forecast có sẵn."""
    try:
        pattern = os.path.join(DATA_DIR, "*_f???.grib2")
        files = glob.glob(pattern)
        
        forecasts = []
        for file in files:
            filename = os.path.basename(file)
            parts = filename.split('_')
            for part in parts:
                if part.startswith('f') and part.endswith('.grib2'):
                    fh = part.replace('.grib2', '')
                    hour = int(fh[1:])
                    forecasts.append({
                        "hour": hour,
                        "forecast_code": fh,
                        "file": filename,
                        "timestamp": os.path.getmtime(file)
                    })
                    break
        
        forecasts.sort(key=lambda x: x['hour'])
        
        return JSONResponse(content={
            "count": len(forecasts),
            "forecasts": forecasts
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {e}")


@app.get("/grib-files")
async def list_grib_files():
    """Liệt kê tất cả file GRIB2."""
    try:
        pattern = os.path.join(DATA_DIR, "*.grib2")
        file_paths = glob.glob(pattern)

        grib_files_data = []
        for path in file_paths:
            summary = await run_in_threadpool(get_grib_summary, path)
            if summary:
                grib_files_data.append(summary)
        
        grib_files_data.sort(key=lambda x: x["file_name"])
        
        return JSONResponse(content={
            "files": grib_files_data, 
            "count": len(grib_files_data)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {e}")


@app.get("/latest-grib")
def latest_grib():
    files = glob.glob("data/*.grib2")
    if not files:
        return {"file": None}
    latest = max(files, key=os.path.getmtime)
    return {"file": os.path.basename(latest)}


@app.get("/grib-json")
async def get_grib_json(file: str):
    """Trả về nội dung JSON của một file GRIB cụ thể."""
    file_path = os.path.join(DATA_DIR, file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    json_data = await run_in_threadpool(grib_to_json, file_path)
    if json_data is None:
        raise HTTPException(status_code=500, detail="Could not process GRIB file")
        
    return JSONResponse(content=json.loads(json_data))


@app.get("/grib-info")
async def get_grib_info_endpoint(file_name: str):
    file_path = os.path.join(DATA_DIR, file_name)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    info = await run_in_threadpool(get_grib_info, file_path)
    
    if info is None:
        raise HTTPException(status_code=500, detail="Không thể đọc file")
    
    return JSONResponse(content=info)


@app.get("/grib-data")
async def get_grib_data(file_name: str):
    file_path = os.path.join(DATA_DIR, file_name)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    json_data = await run_in_threadpool(grib_to_json, file_path)
    
    if json_data is None:
        raise HTTPException(status_code=500, detail="Không thể xử lý file")
    
    return JSONResponse(content=json.loads(json_data))


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Storm Tracker API"}


if __name__ == "__main__":
    print("=" * 60)
    print("🌀 STORM TRACKER API - REAL-TIME MODE (WEBSOCKETS)")
    print("=" * 60)
    print("🌐 Server: http://127.0.0.1:8000")
    print("🔌 WebSocket: ws://127.0.0.1:8000/ws")
    print("📊 API Docs: http://127.0.0.1:8000/docs")
    print("=" * 60)

    # Trong chế độ chạy qua start_system.py → KHÔNG dùng reload
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
