import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

# 로그 파일들이 있는 폴더 경로 (현재 디렉토리 기준)
log_dir = "."

# 패턴에 맞는 파일 리스트 가져오기
log_files = glob.glob(os.path.join(log_dir, "cpu_usage_log_*.csv"))

# 파일이 없을 경우 종료
if not log_files:
    print("로그 파일이 없습니다.")
    exit(1)

# 가장 최근 수정된 파일 찾기
latest_file = max(log_files, key=os.path.getmtime)
print(f"가장 최근 파일: {latest_file}")

# CSV 불러오기
df = pd.read_csv(latest_file)

# 시간 열을 datetime 형식으로 변환
df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"])

# -----------------------------------------------
# PROCESS 타입 시각화 (Top 15 COMMAND CPU 사용량)
df_proc = df[df["TYPE"] == "PROCESS"].copy()

# 컬럼 이름 정리
df_proc.rename(columns={
    "FIELD1": "PID",
    "FIELD2": "USER",
    "FIELD3": "%CPU",
    "FIELD4": "%MEM",
    "FIELD5": "COMMAND"
}, inplace=True)

# 숫자형 변환
df_proc["%CPU"] = pd.to_numeric(df_proc["%CPU"], errors="coerce")

# NaN 제거
df_proc.dropna(subset=["%CPU"], inplace=True)

# 상위 CPU 소비 COMMAND 추출
top_commands = df_proc.groupby("COMMAND")["%CPU"].mean().sort_values(ascending=False).head(15).index

# 시간별 COMMAND CPU 사용량 합산 (피벗)
pivot_proc = df_proc[df_proc["COMMAND"].isin(top_commands)].pivot_table(
    index="TIMESTAMP",
    columns="COMMAND",
    values="%CPU",
    aggfunc="sum"
)

# -----------------------------------------------
# CORE 타입 시각화 (각 코어별 CPU 사용량)
df_core = df[df["TYPE"] == "CORE"].copy()

# 컬럼 이름 정리
df_core.rename(columns={
    "FIELD1": "CPU",
    "FIELD2": "%USER",
    "FIELD3": "%SYSTEM",
    "FIELD4": "%IDLE"
}, inplace=True)

# 숫자형 변환
df_core["%USER"] = pd.to_numeric(df_core["%USER"], errors="coerce")
df_core["%SYSTEM"] = pd.to_numeric(df_core["%SYSTEM"], errors="coerce")

# NaN 제거
df_core.dropna(subset=["%USER", "%SYSTEM"], inplace=True)

# 전체 사용량 계산 (user + system)
df_core["%USED"] = df_core["%USER"] + df_core["%SYSTEM"]

# 시간별 코어별 CPU 사용량 피벗
pivot_core = df_core.pivot_table(
    index="TIMESTAMP",
    columns="CPU",
    values="%USED",
    aggfunc="mean"
)

# -----------------------------------------------
# Figure 1: 두 개의 그래프를 서브플롯으로 표시
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12), sharex=True)

# PROCESS 그래프 (Top 15 COMMAND)
pivot_proc.plot(ax=ax1)
ax1.set_xlabel("Time")
ax1.set_ylabel("CPU Usage (%)")
ax1.set_title("Top 15 CPU Usage Over Time by Command (PROCESS)")
ax1.grid(True)
ax1.legend(title="Command", bbox_to_anchor=(1.05, 1), loc='upper left')

# CORE 그래프 (각 코어별 사용량)
pivot_core.plot(ax=ax2)
ax2.set_xlabel("Time")
ax2.set_ylabel("CPU Usage per Core (%)")
ax2.set_title("CPU Core Usage Over Time (user + system)")
ax2.grid(True)
ax2.legend(title="CPU Core", bbox_to_anchor=(1.05, 1), loc='upper left')

# 레이아웃 최적화
plt.tight_layout()

# 그래프 보여주기
plt.show()
