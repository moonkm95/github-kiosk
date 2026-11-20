#!/bin/bash
# Claude 원격 연결 — 해제 (더블클릭). 설치 파일이 등록한 자동 실행을 끄고 지웁니다.

LABEL="com.claude.remote-control"
SUPPORT_DIR="$HOME/Library/Application Support/ClaudeRemote"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

clear
echo "📡  Claude 원격 연결 해제"
echo ""
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && echo "✅ 실행 중인 원격 연결을 껐습니다." || echo "ℹ️  실행 중인 원격 연결이 없습니다."
rm -f "$PLIST" && echo "✅ 자동 실행 등록을 지웠습니다."
rm -rf "$SUPPORT_DIR"
echo ""
echo "기록 파일(~/Library/Logs/ClaudeRemote.log)은 남겨 두었습니다."
read -r -p "엔터를 누르면 이 창이 닫힙니다..."
