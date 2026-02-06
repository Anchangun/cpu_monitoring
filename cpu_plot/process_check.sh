#!/bin/bash
set -euo pipefail
export LC_ALL=C

duration=7200
start_time=$(date +"%Y%m%d_%H%M%S")
output="cpu_usage_log_${start_time}.csv"

echo "TIMESTAMP,TYPE,FIELD1,FIELD2,FIELD3,FIELD4,FIELD5,FIELD6" > "$output"

echo "CPU 사용량 기록 시작 (pidstat/mpstat 1초 구간 샘플, 최대 ${duration}초)"
echo "저장 파일: $output"
echo "종료하려면 Ctrl+C"

start_epoch=$(date +%s)

while true; do
  elapsed=$(( $(date +%s) - start_epoch ))
  if [ "$elapsed" -ge "$duration" ]; then
    echo "${duration}초 경과, 자동 종료합니다."
    break
  fi

  tmp_pid="$(mktemp)"
  tmp_core="$(mktemp)"

  # 둘 다 1초 기다리므로 병렬 실행
  pidstat -u -h -p ALL 1 1 > "$tmp_pid" &
  mpstat  -P ALL 1 1 > "$tmp_core" &
  wait

  day="$(date +%Y-%m-%d)"

  # ---------------- PROCESS (pidstat) ----------------
  # pidstat 출력은 환경에 따라 AM/PM이 있을 수도/없을 수도 있고, 컬럼 수가 살짝 바뀔 수 있음.
  # 아래는 "시간 형식 + 숫자 PID"를 기준으로 UID/PID/%CPU/Command 위치를 안전하게 잡는 방식.
  awk -v day="$day" '
    function emit(ts, pid, uid, cpu, cmd) {
      if (pid ~ /^[0-9]+$/ && uid ~ /^[0-9]+$/ && cpu != "" && cmd != "") {
        # CSV: TIMESTAMP,PROCESS,PID,UID,%CPU,%MEM(empty),COMMAND,FIELD6(empty)
        printf "%s,PROCESS,%s,%s,%s,,%s,\n", ts, pid, uid, cpu, cmd
      }
    }

    $1 ~ /^[0-9]{2}:[0-9]{2}:[0-9]{2}$/ {
      # case A) AM/PM 있는 경우: time AM uid pid ... %CPU ... command
      if ($2 ~ /^(AM|PM)$/) {
        ts  = day " " $1 " " $2
        uid = $3
        pid = $4
        cpu = $9
        cmd = $11
        emit(ts, pid, uid, cpu, cmd)
        next
      }

      # case B) AM/PM 없는 경우: time uid pid ... %CPU ... command
      # pidstat -u -h -p ALL 1 1에서 흔히 이 형태가 나옴
      ts  = day " " $1
      uid = $2
      pid = $3
      cpu = $8
      cmd = $10
      emit(ts, pid, uid, cpu, cmd)
    }
  ' "$tmp_pid" >> "$output"

  # ---------------- CORE (mpstat) ----------------
  # 헤더 기반 파싱: CPU/%usr/%sys/%idle 위치를 찾아서 포맷 변화에 안전
  awk -v day="$day" '
    BEGIN { cpu_i=0; usr_i=0; sys_i=0; idle_i=0; }

    $0 ~ /%usr/ && $0 ~ /%sys/ && $0 ~ /%idle/ {
      for (i=1; i<=NF; i++) {
        if ($i == "CPU")   cpu_i=i;
        if ($i == "%usr")  usr_i=i;
        if ($i == "%sys")  sys_i=i;
        if ($i == "%idle") idle_i=i;
      }
      next
    }

    $1 ~ /^[0-9]{2}:[0-9]{2}:[0-9]{2}$/ && cpu_i>0 && usr_i>0 && sys_i>0 && idle_i>0 {
      ts = ($2 ~ /^(AM|PM)$/) ? (day " " $1 " " $2) : (day " " $1)
      cpu = $(cpu_i)
      if (cpu == "CPU") next
      # CSV: TIMESTAMP,CORE,CPU,%usr,%sys,%idle,FIELD5(empty),FIELD6(empty)
      printf "%s,CORE,%s,%s,%s,%s,,\n", ts, cpu, $(usr_i), $(sys_i), $(idle_i)
    }
  ' "$tmp_core" >> "$output"

  rm -f "$tmp_pid" "$tmp_core"
done

