import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import itertools

# 로그 파일 디렉토리
log_dir = "."
log_files = glob.glob(os.path.join(log_dir, "cpu_usage_log_*.csv"))
if not log_files:
    print("로그 파일이 없습니다.")
    exit(1)

latest_file = max(log_files, key=os.path.getmtime)
print(f"가장 최근 파일: {latest_file}")

# CSV 읽기
df = pd.read_csv(latest_file)
df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"])

# ----------------- PROCESS 전처리 -----------------
df_proc = df[df["TYPE"] == "PROCESS"].copy()
df_proc.rename(columns={
    "FIELD1": "PID", "FIELD2": "USER", "FIELD3": "%CPU",
    "FIELD4": "%MEM", "FIELD5": "COMMAND"
}, inplace=True)
df_proc["%CPU"] = pd.to_numeric(df_proc["%CPU"], errors="coerce")
df_proc.dropna(subset=["%CPU"], inplace=True)

# ✅ 상위 15개 COMMAND 기준
top_commands = df_proc.groupby("COMMAND")["%CPU"].mean().sort_values(ascending=False).head(10).index

# ----------------- 계정 변경 감지 출력 -----------------
print("\n[USER SWITCH DETECTED]")
for command in top_commands:
    df_cmd = df_proc[df_proc["COMMAND"] == command].sort_values("TIMESTAMP")
    prev_user = None
    for _, row in df_cmd.iterrows():
        curr_user = row["USER"]
        ts = row["TIMESTAMP"]
        if prev_user is None:
            prev_user = curr_user
            continue
        if curr_user != prev_user:
            print(f" - {command}: {prev_user} → {curr_user} at {ts}")
            prev_user = curr_user

# ----------------- CORE 전처리 -----------------
df_core = df[df["TYPE"] == "CORE"].copy()
df_core.rename(columns={
    "FIELD1": "CPU", "FIELD2": "%USER", "FIELD3": "%SYSTEM", "FIELD4": "%IDLE"
}, inplace=True)
df_core["%USER"] = pd.to_numeric(df_core["%USER"], errors="coerce")
df_core["%SYSTEM"] = pd.to_numeric(df_core["%SYSTEM"], errors="coerce")
df_core.dropna(subset=["%USER", "%SYSTEM"], inplace=True)
df_core["%USED"] = df_core["%USER"] + df_core["%SYSTEM"]

pivot_core = df_core.pivot_table(
    index="TIMESTAMP",
    columns="CPU",
    values="%USED",
    aggfunc="mean"
)

# ----------------- 시각화 -----------------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12), sharex=True)

# COMMAND + USER 구분을 위한 선 스타일
line_styles = ['-', '--', '-.', ':', (0, (3, 1, 1, 1)), (0, (1, 1))]
style_map = {}
color_cycle = itertools.cycle(plt.cm.tab10.colors)
command_colors = {}
plotted_labels = set()

for command in top_commands:
    df_cmd = df_proc[df_proc["COMMAND"] == command].sort_values("TIMESTAMP")
    command_colors[command] = next(color_cycle)

    prev_user = None
    segment_times = []
    segment_cpus = []

    for _, row in df_cmd.iterrows():
        curr_user = row["USER"]
        if prev_user is None:
            prev_user = curr_user

        if curr_user != prev_user:
            if segment_times:
                linestyle = style_map.setdefault(prev_user, line_styles[len(style_map) % len(line_styles)])
                label = command if command not in plotted_labels else None

                ax1.plot(segment_times, segment_cpus,
                         color=command_colors[command],
                         linestyle=linestyle,
                         label=label)
                plotted_labels.add(command)

            segment_times = []
            segment_cpus = []
            prev_user = curr_user

        segment_times.append(row["TIMESTAMP"])
        segment_cpus.append(row["%CPU"])

    if segment_times:
        linestyle = style_map.setdefault(prev_user, line_styles[len(style_map) % len(line_styles)])
        label = command if command not in plotted_labels else None

        ax1.plot(segment_times, segment_cpus,
                 color=command_colors[command],
                 linestyle=linestyle,
                 label=label)
        plotted_labels.add(command)

# PROCESS 그래프 제목 및 스타일
ax1.set_title("CPU Usage by Command (Color = Command, LineStyle = User)")
ax1.set_ylabel("CPU Usage (%)")
ax1.grid(True)
ax1.legend(title="Command", bbox_to_anchor=(1.05, 1), loc="upper left")

# ----------------- CORE 그래프 -----------------
pivot_core.plot(ax=ax2)
ax2.set_title("CPU Core Usage Over Time")
ax2.set_xlabel("Time")
ax2.set_ylabel("CPU Usage (%)")
ax2.grid(True)
ax2.legend(title="CPU Core", bbox_to_anchor=(1.05, 1), loc="upper left")

plt.tight_layout()
plt.show()
