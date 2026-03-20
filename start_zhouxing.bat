@echo off
setlocal
cd /d %~dp0

set GOTELEMETRY=off
set PYTHONDONTWRITEBYTECODE=1
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
  echo [zhouxing] creating root .venv with Python 3.12
  uv venv .venv --python 3.12
  if errorlevel 1 exit /b %errorlevel%
)

if not exist "sandbox\.venv\Scripts\python.exe" (
  echo [zhouxing] creating sandbox .venv with Python 3.12
  uv venv sandbox\.venv --python 3.12
  if errorlevel 1 exit /b %errorlevel%
)

if not exist ".venv\Lib\site-packages\psutil" (
  echo [zhouxing] syncing backend dependencies with uv
  uv sync --python .venv\Scripts\python.exe
  if errorlevel 1 (
    echo [zhouxing] dependency sync failed, continuing with basic monitoring fallback
  )
)

echo [zhouxing] starting TUI
go run ./cmd/zhouxing
exit /b %errorlevel%
