@echo off
REM Starts the Discovery Engine frontend (Vite dev server) at http://localhost:5173
REM Uses the portable Node in .node\ if present, otherwise the Node already on your PATH.
setlocal
if exist "%~dp0.node\node.exe" set "PATH=%~dp0.node;%PATH%"
cd /d "%~dp0frontend"
if not exist node_modules call npm install
call npm run dev
