@echo off
REM Build elastik Go native server. Output: ..\elastik-go.exe
setlocal
cd /d "%~dp0"
echo Building elastik-go.exe...
go build -o ..\elastik-go.exe .\native
if errorlevel 1 (
    echo.
    echo BUILD FAILED
    exit /b 1
)
echo.
echo OK  -^> elastik-go.exe
dir ..\elastik-go.exe | findstr elastik-go.exe
