#!/bin/zsh
# 도비일번 터미널 브리지
# DOBBY(브라우저)가 이 터미널을 통해 claude에 명령하고 결과를 받습니다.
# 명령은 /tmp/dobi_cmd_pipe 로 수신, 결과는 /tmp/dobi_out_<id>.txt 로 저장.

CMD_PIPE=/tmp/dobi_cmd_pipe

rm -f "$CMD_PIPE"
mkfifo "$CMD_PIPE"

trap 'rm -f "$CMD_PIPE"; exit 0' SIGINT SIGTERM

clear
echo "╔══════════════════════════════════════════════╗"
echo "║          도비일번 터미널 브리지               ║"
echo "║  DOBBY가 이 터미널로 claude를 제어합니다    ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "⏳ 음성 명령 대기 중..."
echo ""

while true; do
    # 명령 파일 경로를 먼저 읽는다 (한 줄에 파일 경로만)
    read -r cmd_file < "$CMD_PIPE"

    [ -z "$cmd_file" ] && continue
    [ ! -f "$cmd_file" ] && continue

    # 명령 파일에서 프로젝트 경로와 프롬프트 읽기
    project_dir=$(sed -n '1p' "$cmd_file")
    prompt=$(sed -n '2,$p' "$cmd_file")
    out_file="${cmd_file%.cmd}.out"

    [ -z "$project_dir" ] || [ -z "$prompt" ] && continue

    cd "$project_dir" 2>/dev/null || {
        err="오류: 디렉토리를 찾을 수 없습니다 — $project_dir"
        echo "$err"
        printf '%s\n===DOBI_DONE===\n' "$err" > "$out_file"
        rm -f "$cmd_file"
        continue
    }

    echo ""
    echo "┌──────────────────────────────────────────────"
    echo "│ 📁 $(basename "$project_dir")"
    echo "│ 💬 $prompt"
    echo "└──────────────────────────────────────────────"
    echo ""

    # claude -p 실행 — 화면에 스트리밍하면서 동시에 파일로 캡처
    claude -p "$prompt" 2>&1 | tee "$out_file"

    # 완료 신호 추가
    printf '\n===DOBI_DONE===\n' >> "$out_file"

    rm -f "$cmd_file"

    echo ""
    echo "✓ 완료 — 다음 명령 대기 중..."
    echo ""
done
