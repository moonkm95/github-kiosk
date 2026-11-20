#!/bin/bash
# Claude 원격 연결 — Mac 설치 파일 (더블클릭, 처음 한 번만)
#
# 이 Mac에서 `claude remote-control` 을 "항상 켜진 상태"로 등록합니다.
#  - 로그인할 때 자동 시작, 꺼지면 자동 재시작 (macOS LaunchAgent)
#  - 실행 중에는 Mac이 잠자기에 들어가지 않도록 유지 (caffeinate)
# 그러면 밖에서도 iPhone의 Claude 앱 / claude.ai/code 에서 이 Mac 세션을 열어
# Mac 앱과 똑같이 이 Mac의 파일·도구·로그인 정보를 그대로 쓸 수 있습니다.

LABEL="com.claude.remote-control"
SUPPORT_DIR="$HOME/Library/Application Support/ClaudeRemote"
RUN_SH="$SUPPORT_DIR/run.sh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/ClaudeRemote.log"

clear
echo "=================================================="
echo "   📡  Claude 원격 연결 설치 (이 Mac을 항상 대기 상태로)"
echo "=================================================="
echo ""

pause_exit() { echo ""; read -r -p "엔터를 누르면 이 창이 닫힙니다..."; exit "${1:-1}"; }
xml_escape() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' <<<"$1"; }

# 로그인 셸의 PATH를 그대로 가져옵니다 (Homebrew, ~/.local/bin 등 포함)
LOGIN_PATH="$("$SHELL" -lic 'printf %s "$PATH"' 2>/dev/null | tail -n 1)"
[ -n "$LOGIN_PATH" ] && export PATH="$LOGIN_PATH:$PATH"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# 1) Claude Code CLI
if ! command -v claude >/dev/null 2>&1; then
  echo "⚙️  Claude Code(claude) 가 설치되어 있지 않습니다."
  read -r -p "   지금 공식 설치 스크립트로 설치할까요? [Y/n] " ans
  if [[ "$ans" =~ ^[Nn] ]]; then
    echo "   → https://code.claude.com 에서 설치한 뒤 이 파일을 다시 더블클릭하세요."
    pause_exit
  fi
  curl -fsSL https://claude.ai/install.sh | bash || { echo "❌ 설치 실패"; pause_exit; }
  export PATH="$HOME/.local/bin:$PATH"
  command -v claude >/dev/null 2>&1 || { echo "❌ 설치 후에도 claude 를 찾지 못했습니다. 터미널을 새로 열고 다시 실행하세요."; pause_exit; }
fi
CLAUDE_BIN="$(command -v claude)"
echo "✅ Claude Code: $CLAUDE_BIN ($("$CLAUDE_BIN" --version 2>/dev/null | head -n 1))"

# 2) Claude 로그인 (구독 계정 필요)
if ! "$CLAUDE_BIN" auth status >/dev/null 2>&1; then
  echo ""
  echo "🔑 Claude 로그인이 필요합니다. 브라우저가 열리면 iPhone 앱과 같은 계정으로 로그인하세요."
  "$CLAUDE_BIN" auth login || { echo "❌ 로그인이 완료되지 않았습니다."; pause_exit; }
fi
echo "✅ Claude 로그인 확인"

# 3) 원격으로 작업할 폴더 선택
DEFAULT_DIR="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
echo ""
echo "📁 밖에서 작업할 폴더를 고르세요. (여러 프로젝트를 담은 상위 폴더도 좋습니다)"
echo "   ※ 데스크탑·문서·다운로드 폴더 안은 macOS 보안 때문에 막힐 수 있어,"
echo "     ~/Developer 같은 폴더를 권장합니다."
WORK_DIR="$(osascript -e "POSIX path of (choose folder with prompt \"Claude 원격 작업 폴더 선택\" default location (POSIX file \"$DEFAULT_DIR\"))" 2>/dev/null)"
WORK_DIR="${WORK_DIR%/}"
[ -z "$WORK_DIR" ] && { echo "취소했습니다."; pause_exit; }
if [ "$WORK_DIR" = "$HOME" ]; then
  echo "❌ 홈 폴더 전체는 선택할 수 없습니다. 그 안의 작업 폴더를 골라 주세요."
  pause_exit
fi
echo "✅ 작업 폴더: $WORK_DIR"

# 4) 폴더 신뢰 (원격에서는 질문에 답할 화면이 없으므로 여기서 한 번)
echo ""
echo "🤝 이 폴더를 Claude가 신뢰하도록 한 번 열어 둡니다."
echo "   Claude가 열리고 '이 폴더를 신뢰하나요?' 를 물으면 [예]를 고른 뒤,"
echo "   /exit 를 입력해 닫아 주세요. (이미 신뢰한 폴더면 바로 /exit)"
read -r -p "   준비되면 엔터… "
(cd "$WORK_DIR" && "$CLAUDE_BIN")

# 5) 실행 스크립트 + LaunchAgent 등록
COMPUTER_NAME="$(scutil --get ComputerName 2>/dev/null || hostname -s)"
mkdir -p "$SUPPORT_DIR" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

{
  echo '#!/bin/bash'
  echo '# 자동 생성됨 — 원격연결-설치.command 가 만든 파일입니다.'
  printf 'export PATH=%q\n' "$PATH"
  printf 'cd %q || exit 1\n' "$WORK_DIR"
  echo 'echo "[$(date "+%F %T")] Remote Control 시작"'
  # caffeinate: -i 유휴 잠자기 방지, -s 전원 연결 시 시스템 잠자기 방지 (이 프로세스가 도는 동안만)
  printf 'exec /usr/bin/caffeinate -i -s %q remote-control --name %q\n' "$CLAUDE_BIN" "$COMPUTER_NAME"
} > "$RUN_SH"
chmod +x "$RUN_SH"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$(xml_escape "$RUN_SH")</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$(xml_escape "$LOG")</string>
  <key>StandardErrorPath</key><string>$(xml_escape "$LOG")</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST" >/dev/null || { echo "❌ 설정 파일 생성 오류: $PLIST"; pause_exit; }

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" || { echo "❌ 자동 실행 등록 실패"; pause_exit; }

echo ""
echo "⏳ 시작 확인 중…"
sleep 8
if launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -q "state = running"; then
  echo "✅ 원격 연결이 켜졌습니다! 이 Mac 이름: \"$COMPUTER_NAME\""
else
  echo "⚠️  아직 실행 상태가 확인되지 않습니다. 아래 기록을 확인하세요."
fi
echo ""
echo "----- 최근 기록 ($LOG) -----"
tail -n 15 "$LOG" 2>/dev/null
echo "----------------------------------------------"
cat <<EOF

📱 이제 밖에서는: iPhone Claude 앱(또는 claude.ai/code) → Code → 세션 목록에서
   "$COMPUTER_NAME" 세션을 열면 이 Mac에서 직접 작업합니다.

🔋 꼭 확인하세요 (Mac이 잠들면 연결이 끊깁니다):
   • 전원 어댑터 연결 상태로 두기 (배터리만으로는 잠자기를 막지 못합니다)
   • MacBook 덮개를 닫으면 잠듭니다 (외부 모니터 연결 시 제외)
   • 시스템 설정 → 에너지(또는 배터리 → 옵션)
       - "디스플레이가 꺼져 있을 때 자동으로 잠자기 방지" 켜기
       - "네트워크 접근 시 깨우기" 켜기
   • 재부팅 후에는 로그인해야 자동으로 시작됩니다
     (시스템 설정 → 사용자 및 그룹 → 자동 로그인 을 켜 두면 편합니다)

해제하려면 같은 폴더의 '원격연결-해제.command' 를 더블클릭하세요.
EOF
pause_exit 0
