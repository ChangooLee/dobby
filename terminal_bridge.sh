#!/bin/zsh
# DOBBY 터미널 브리지 — 프로젝트별 독립 파이프
# 사용: terminal_bridge.sh <project_name> <project_dir>
# DOBBY가 파이프로 명령을 보내면 claude -p [--continue]로 실행하고
# 결과를 화면에 스트리밍하면서 파일에 캡처.

PROJECT_NAME="${1:-unknown}"
PROJECT_DIR="${2:-$PWD}"
CMD_PIPE="/tmp/dobi_cmd_${PROJECT_NAME}_pipe"
MSG_COUNT_FILE="/tmp/dobi_msgcount_${PROJECT_NAME}"

# 이전 파이프 정리
rm -f "$CMD_PIPE"
mkfifo "$CMD_PIPE"

# 메시지 카운터 초기화 (--continue 결정용)
echo "0" > "$MSG_COUNT_FILE"

trap 'rm -f "$CMD_PIPE" "$MSG_COUNT_FILE"; exit 0' SIGINT SIGTERM

cd "$PROJECT_DIR" 2>/dev/null || cd "$HOME"

clear
echo "╔══════════════════════════════════════════════╗"
echo "║         DOBBY Claude Code 세션               ║"
printf "║  📁 %-40s║\n" "$PROJECT_NAME"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "⏳ DOBBY 명령 대기 중..."
echo ""

while true; do
    # 명령 파일 경로 수신
    read -r cmd_file < "$CMD_PIPE"

    [ -z "$cmd_file" ] && continue
    [ ! -f "$cmd_file" ] && continue

    # 명령 파일에서 프롬프트 읽기 (첫 번째 줄 이후가 프롬프트)
    prompt=$(cat "$cmd_file")
    out_file="${cmd_file%.cmd}.out"

    [ -z "$prompt" ] && continue

    # 메시지 카운터 증가 (첫 메시지는 --continue 없이, 이후는 --continue)
    msg_count=$(cat "$MSG_COUNT_FILE" 2>/dev/null || echo 0)
    msg_count=$((msg_count + 1))
    echo "$msg_count" > "$MSG_COUNT_FILE"

    if [ "$msg_count" -gt 1 ]; then
        CONTINUE_FLAG="--continue"
    else
        CONTINUE_FLAG=""
    fi

    echo ""
    echo "┌──────────────────────────────────────────────"
    printf "│ 💬 %s\n" "$prompt"
    echo "└──────────────────────────────────────────────"
    echo ""

    # claude -p 실행 — 화면 스트리밍 + 파일 캡처
    # shellcheck disable=SC2086
    claude -p --output-format text $CONTINUE_FLAG "$prompt" 2>&1 | tee "$out_file"

    # 완료 신호
    printf '\n===DOBI_DONE===\n' >> "$out_file"

    rm -f "$cmd_file"

    echo ""
    echo "✓ 완료 — 다음 명령 대기 중..."
    echo ""
done
