@echo off
cls

echo =============================================================
echo. 
echo           CHU TRINH DU BAO BAO TU DONG
echo.
echo =============================================================
pause

:RUN_MODEL
cls
echo.
echo =============================================================
echo.
echo      BUOC 1: CHAY MO HINH DU BAO
echo.
echo      (Chon tuy chon 3 hoac 4 trong buoc tiep theo)
echo.
echo =============================================================
echo.

:: Activate venv and run the model script
call D:\venvs\storm_env\Scripts\activate
cd /d "%~dp0"
python -m services.storm_prediction_service.final_storm_forecast

echo.
echo =============================================================
echo.
echo      BUOC 1 HOAN TAT.
echo.
echo =============================================================
echo.
pause

:VIEW_RESULTS
cls
echo.
echo =============================================================
echo.
echo      BUOC 2: KHOI DONG SERVER XEM KET QUA
echo.
echo      Server se chay tai: http://127.0.0.1:8000
echo.
echo =============================================================
echo.

:: Run the viewer server in a new window
start "Ket Qua (Port 8000)" cmd /k "call D:\venvs\storm_env\Scripts\activate && cd /d "%~dp0" && python app.py"

echo.
echo Da mo cua so moi cho server xem ket qua.
echo Vui long mo trinh duyet den dia chi http://127.0.0.1:8000
echo.
pause
exit
