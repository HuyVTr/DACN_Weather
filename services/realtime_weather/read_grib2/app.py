from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import xarray as xr
import os

app = FastAPI()

# ======== TEMPLATES & STATIC ========
# Vì app.py nằm trong folder read_grib2 -> templates cũng nằm cùng cấp
templates = Jinja2Templates(directory="templates")

# Static (css/js) cũng nằm trong read_grib2/templates
app.mount("/static", StaticFiles(directory="templates"), name="static")

# ======== THƯ MỤC DATA (nằm chung với thư mục read_grib2) ========
# reltime/
#   data/
#   read_grib2/
#       app.py
#       templates/
DATA_DIR = "../data"   # trở ra thư mục cha rồi vào data

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/list")
def list_files():
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".grib2")]
    return {"files": sorted(files)}


@app.get("/read")
def read_file(name: str):
    file_path = os.path.join(DATA_DIR, name)

    if not os.path.exists(file_path):
        raise HTTPException(404, "Không tìm thấy file")

    # Thử stepType=instant
    try:
        ds = xr.open_dataset(
            file_path,
            engine="cfgrib",
            backend_kwargs={"filter_by_keys": {"stepType": "instant"}}
        )
    except Exception:
        # fallback sang avg
        ds = xr.open_dataset(
            file_path,
            engine="cfgrib",
            backend_kwargs={"filter_by_keys": {"stepType": "avg"}}
        )

    df = ds.to_dataframe().reset_index()

    # Fix JSON lỗi Timestamp và Timedelta
    for col in df.columns:
        col_type = str(df[col].dtype)
        if col_type.startswith("datetime64"):
            df[col] = df[col].astype(str)
        if col_type.startswith("timedelta64"):
            df[col] = df[col].astype(str)

    sample = df.head(200).to_dict(orient="records")

    return JSONResponse({"file": name, "rows": sample})


# ======== CHẠY UVICORN TRỰC TIẾP ========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=5000,
        reload=True
    )
