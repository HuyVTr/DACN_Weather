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
call "%~dp0venv\Scripts\activate"
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
echo      BUOC 2: CHON CACH KHOI DONG SERVER
echo.
echo =============================================================
echo.
echo   1. Xem log truc tiep (Cua so server se mo ra va hien thi log)
echo   2. Luu log vao file   (De gui cho toi debug - Cua so se tu dong tat)
echo.

CHOICE /C 12 /M "Ban chon cach nao?"

IF ERRORLEVEL 2 GOTO LOG_TO_FILE
IF ERRORLEVEL 1 GOTO LIVE_LOG

:LIVE_LOG
echo ">> KHOI DONG SERVER - CHE DO XEM LOG TRUC TIEP..."
start "Ket Qua (Port 8000)" cmd /k "call "%~dp0venv\Scripts\activate" && cd /d "%~dp0" && python -u app.py"
GOTO END_SCRIPT

:LOG_TO_FILE
echo ">> KHOI DONG SERVER - CHE DO LUU LOG VAO FILE..."
start "Ket Qua (Port 8000) - LOGGING" /B /D "%~dp0" cmd /c "set PYTHONIOENCODING=UTF-8 && "%~dp0venv\Scripts\python.exe" app.py > server.log 2>&1"
echo ">> Server da khoi dong trong nen. Kiem tra 'server.log' de xem trang thai."
GOTO END_SCRIPT

:END_SCRIPT
echo.
echo      -------------------------------------------------------
echo.
echo      >> Lenh khoi dong da duoc thuc thi.
echo.
echo      >> Vui long mo trinh duyet va truy cap dia chi:
echo.
echo         http://127.0.0.1:8000
echo.
echo      -------------------------------------------------------
echo.
pause
exit
