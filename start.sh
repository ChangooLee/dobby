#!/usr/bin/env bash
# DOBBY 전체 시작 스크립트
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DOBBY]${NC} $*"; }
warn() { echo -e "${YELLOW}[DOBBY]${NC} $*"; }
err()  { echo -e "${RED}[DOBBY]${NC} $*"; }

# ── 0. yabai (Space 전환) ─────────────────────────────────────
YABAI_BIN="$(which yabai 2>/dev/null || echo /opt/homebrew/bin/yabai)"
if [ -x "$YABAI_BIN" ]; then
  if ! pgrep -x yabai &>/dev/null; then
    log "yabai 시작..."
    nohup "$YABAI_BIN" > /tmp/yabai.log 2>&1 &
    sleep 1
    if pgrep -x yabai &>/dev/null; then
      log "yabai 기동 완료"
    else
      warn "yabai 기동 실패 — Space 전환이 제한될 수 있습니다. 로그: tail -f /tmp/yabai.log"
    fi
  else
    warn "yabai 이미 실행 중"
  fi
else
  warn "yabai 없음 — brew install koekeishiya/formulae/yabai 로 설치하세요"
fi

# ── 1. Qwen3 TTS 서버 ────────────────────────────────────────
if lsof -i :8000 -sTCP:LISTEN -t &>/dev/null; then
  warn "TTS 서버 이미 실행 중 (port 8000)"
else
  log "Qwen3 TTS 서버 시작..."
  cd ~/Workspace/qwen3-tts-server
  nohup ./bin/python server.py > /tmp/qwen3_tts.log 2>&1 &
  cd "$SCRIPT_DIR"
  sleep 2
  if lsof -i :8000 -sTCP:LISTEN -t &>/dev/null; then
    log "TTS 서버 기동 완료 → localhost:8000"
  else
    err "TTS 서버 기동 실패. 로그: tail -f /tmp/qwen3_tts.log"
    err "macOS say 폴백으로 계속 진행합니다."
  fi
fi

# ── 2. DOBBY 백엔드 ───────────────────────────────────────────
if lsof -i :8340 -sTCP:LISTEN -t &>/dev/null; then
  warn "백엔드 이미 실행 중 (port 8340)"
else
  log "DOBBY 백엔드 시작..."
  nohup .venv/bin/python server.py > /tmp/dobby_server.log 2>&1 &
  sleep 3
  if lsof -i :8340 -sTCP:LISTEN -t &>/dev/null; then
    log "백엔드 기동 완료 → localhost:8340"
  else
    err "백엔드 기동 실패. 로그: tail -f /tmp/dobby_server.log"
    exit 1
  fi
fi

# ── 3. Motion HUD ─────────────────────────────────────────────
if pgrep -f "electron dist/main.js" &>/dev/null; then
  warn "Motion HUD 이미 실행 중"
else
  log "Motion HUD 시작..."
  cd motion-hud
  npm start &>/tmp/hud.log &
  cd "$SCRIPT_DIR"
  log "Motion HUD 기동 중..."
fi

echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "DOBBY 실행 완료"
log "  TTS 로그   : tail -f /tmp/qwen3_tts.log"
log "  백엔드 로그: tail -f /tmp/dobby_server.log"
log "  HUD 로그   : tail -f /tmp/hud.log"
log "  종료       : ./stop.sh"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
