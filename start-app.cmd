@echo off
REM Runs the whole product: builds the website and serves it together with the API at http://localhost:8000
REM Uses the portable Python in .python\ and the portable Node in .node\ when they exist, otherwise python/node from PATH.
setlocal
set "ROOT=%~dp0"
if exist "%ROOT%.node\node.exe" set "PATH=%ROOT%.node;%PATH%"
set "PY=python"
if exist "%ROOT%.python\python.exe" set "PY=%ROOT%.python\python.exe"
set PYTHONIOENCODING=utf-8

if not exist "%ROOT%frontend\node_modules" (
  echo Installing website dependencies...
  pushd "%ROOT%frontend" & call npm install & popd
)
if not exist "%ROOT%frontend\dist\index.html" (
  echo Building the website...
  pushd "%ROOT%frontend" & call npm run build & popd
)
echo.
echo Discovery Engine is starting at http://localhost:8000  (API docs: http://localhost:8000/docs)
echo Press Ctrl+C to stop.
cd /d "%ROOT%"
"%PY%" -m uvicorn backend.api.main:app --port 8000
