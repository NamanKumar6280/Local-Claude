@echo off
setlocal

:: Unity Horror Game Setup Runner
:: Usage: Drag this file into your Unity project's root folder and double-click.

echo Setting up Unity horror game...

:: Check if Unity is installed
where unity >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Unity not found. Install Unity Hub and try again.
    pause
    exit /b 1
)

:: Open the project in Unity (replace "2022.3" with your Unity version)
start "" "unity" -projectPath "%~dp0" -executeMethod SetupHorrorGame.ImportAssets

echo Setup complete! Open the project in Unity to play.
pause