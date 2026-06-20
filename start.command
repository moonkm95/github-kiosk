#!/bin/bash
# GitHub 키오스크 — Mac 실행 파일 (더블클릭). 처음 한 번만 자동으로 점검·설치·로그인을 안내한 뒤 키오스크를 엽니다.
cd "$(dirname "$0")" || exit 1
clear
echo "=================================================="
echo "   🐙  GitHub 키오스크 시작"
echo "=================================================="
echo ""

pause_exit() { echo ""; read -r -p "엔터를 누르면 이 창이 닫힙니다..."; exit 1; }

# 1) Python3
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python 3 가 필요합니다."
  echo "   → https://www.python.org/downloads/ 에서 설치한 뒤 이 파일을 다시 더블클릭하세요."
  pause_exit
fi

# 2) git (Mac은 보통 Xcode Command Line Tools에 포함)
if ! command -v git >/dev/null 2>&1; then
  echo "⚙️  git 이 없어 설치를 시도합니다 (Xcode Command Line Tools)…"
  xcode-select --install 2>/dev/null
  echo "   설치 창이 뜨면 완료한 뒤, 이 파일을 다시 더블클릭하세요."
  pause_exit
fi

# 3) GitHub CLI (gh)
if ! command -v gh >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "⚙️  GitHub CLI(gh) 를 설치합니다 (brew install gh)…"
    brew install gh || { echo "설치 실패. https://cli.github.com 에서 직접 설치 후 다시 실행하세요."; pause_exit; }
  else
    echo "❌ GitHub CLI(gh) 가 필요합니다."
    echo "   → https://cli.github.com 에서 설치한 뒤 이 파일을 다시 더블클릭하세요."
    pause_exit
  fi
fi

# 4) GitHub 로그인 (한 번만) — 모든 앱의 '로그인'과 같은 단계
if ! gh auth status >/dev/null 2>&1; then
  echo "🔑  GitHub 로그인이 필요합니다. 잠시 후 브라우저가 열립니다 — 안내를 따라 한 번만 로그인하세요."
  echo ""
  gh auth login --web -h github.com || { echo "로그인이 완료되지 않았습니다. 다시 실행해 주세요."; pause_exit; }
fi

# 5) 키오스크 실행 (브라우저 자동으로 열림)
echo ""
echo "✅  준비 완료! 브라우저에서 키오스크가 열립니다."
echo "    (이 창은 닫지 마세요. 종료하려면 이 창에서 Control+C)"
echo ""
python3 server.py
