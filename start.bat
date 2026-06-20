@echo off
REM GitHub 키오스크 — Windows 실행 파일 (더블클릭). 점검·로그인 안내 후 키오스크를 엽니다.
cd /d "%~dp0"
title GitHub 키오스크
cls
echo ==================================================
echo    GitHub 키오스크 시작
echo ==================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python 이 필요합니다. https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요.
  echo     설치 시 "Add Python to PATH" 를 꼭 체크하세요.
  pause & exit /b
)

where git >nul 2>nul
if errorlevel 1 (
  echo [X] Git 이 필요합니다. https://git-scm.com/download/win 에서 설치 후 다시 실행하세요.
  pause & exit /b
)

where gh >nul 2>nul
if errorlevel 1 (
  echo [X] GitHub CLI 가 필요합니다. https://cli.github.com 에서 설치 후 다시 실행하세요.
  pause & exit /b
)

gh auth status >nul 2>nul
if errorlevel 1 (
  echo [!] GitHub 로그인이 필요합니다. 브라우저가 열리면 한 번만 로그인하세요.
  gh auth login --web -h github.com
)

echo.
echo [OK] 준비 완료! 브라우저에서 키오스크가 열립니다. 이 창은 닫지 마세요. (종료: Ctrl+C)
echo.
python server.py
