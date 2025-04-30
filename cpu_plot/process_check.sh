#!/bin/bash

interval=1                 # 저장 주기 (초)
duration=120               # 총 실행 시간 (초)

start_time=$(date +"%Y%m%d_%H%M%S")
output="cpu_usage_log_${start_time}.csv"

# 헤더 작성
echo "TIMESTAMP,TYPE,FIELD1,FIELD2,FIELD3,FIELD4,FIELD5,FIELD6" > "$output"

echo "CPU 사용량 기록 시작 (1초 간격, 최대 2분)"
echo "저장 파일: $output"
echo "종료하려면 Ctrl+C"

start_epoch=$(date +%s)

while true; do
    current_epoch=$(date +%s)
    elapsed=$(( current_epoch - start_epoch ))

    if [ "$elapsed" -ge "$duration" ]; then
        echo "⏱️ 2분 경과, 자동 종료합니다."
        break
    fi

    timestamp=$(date +"%Y-%m-%d %H:%M:%S")

    # 프로세스별 CPU 사용량 기록
    ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | awk -v ts="$timestamp" '
        NR>1 {
            printf "%s,PROCESS,%s,%s,%s,%s,%s\n", ts, $1, $2, $3, $4, $5
        }
    ' >> "$output"

    # 코어별 CPU 사용량 기록
    mpstat -P ALL 1 1 | awk -v ts="$timestamp" '
        /^[0-9]/ && NF > 4 && $3 ~ /^CPU/ { next } # 헤더 제외
        /^[0-9]/ && NF > 4 {
            printf "%s,CORE,%s,%s,%s,%s\n", ts, $3, $4, $6, $13
        }
    ' >> "$output"

    sleep "$interval"
done
