#!/usr/bin/env bash
# DOBBY 전체 종료 스크립트

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}[DOBBY]${NC} $*"; }

log "Motion HUD 종료..."
pkill -f "DOBBY.app.*MacOS/DOBBY" 2>/dev/null
pkill -f "electron dist/main.js" 2>/dev/null
pgrep -f "DOBBY.app\|electron dist/main.js" &>/dev/null && log "  HUD 종료 실패" || log "  HUD 종료됨"

log "DOBBY 백엔드 종료..."
pkill -f "dobby/server.py" 2>/dev/null || pkill -f "python server.py" 2>/dev/null && log "  백엔드 종료됨" || log "  백엔드 실행 중 아님"

log "Qwen3 TTS 서버 종료..."
pkill -f "qwen3-tts-server/server.py" 2>/dev/null && log "  TTS 서버 종료됨" || log "  TTS 서버 실행 중 아님"

log "완료."
