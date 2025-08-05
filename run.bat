@echo off
title SQL Optimizer AI - Launcher

REM Check for existing virtual environment
IF NOT EXIST "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

echo Installing dependencies...
pip install --upgrade pip >nul
pip install -r requirements.txt

echo Launching SQL Optimizer AI...
streamlit run main.py

pause
