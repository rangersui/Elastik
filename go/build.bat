@echo off
REM Build elastik Go native server. Output: ..\elastik.exe
setlocal
cd /d "%~dp0"
echo Building elastik.exe...
go build -o ..\elastik.exe .\native
if errorlevel 1 (
    echo.
    echo BUILD FAILED
    exit /b 1
)
echo.
echo OK  -^> elastik.exe
dir ..\elastik.exe | findstr elastik.exe
