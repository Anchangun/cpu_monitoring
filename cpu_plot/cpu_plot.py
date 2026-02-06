import os
import glob
import pwd
import pandas as pd
import matplotlib.pyplot as plt

LOG_DIR = "."
TOP_N = 10
WINDOW_SEC = 30   # 최근 N초 평균으로 Top PID 선정 (원하면 0으로 두고 전체 평균 사용)

# ----------------- 최신 로그 파일 -----------------
log_files = glob.glob(os.path.join(LOG_DIR, "cpu_usage_log_*.csv"))
if not log_files:
    print("로그 파일이 없습니다.")
    raise SystemExit(1)

latest_file = max(log_files, key=os.path.getmtime)
print(f"가장 최근 파일: {latest_file}")

df = pd.read_csv(latest_file)

# 빈 파일 방지
if df.shape[0] == 0:
    print("[ERROR] CSV에 데이터 행이 없습니다(헤더만 있음).")
    raise SystemExit(1)

# strip(공백/CRLF 대비)
for c in ["TIMESTAMP","TYPE","FIELD1","FIELD2","FIELD3","FIELD4","FIELD5","FIELD6"]:
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip().str.replace("\r", "", regex=False)

# TIMESTAMP: 12h(AM/PM) + 24h 지원
ts_raw = df["TIMESTAMP"]
ts_12h = pd.to_datetime(ts_raw, format="%Y-%m-%d %I:%M:%S %p", errors="coerce")
ts_24h = pd.to_datetime(ts_raw, format="%Y-%m-%d %H:%M:%S", errors="coerce")
df["TIMESTAMP"] = ts_12h.fillna(ts_24h)
df = df.dropna(subset=["TIMESTAMP"])

# ----------------- PROCESS 전처리 -----------------
df_proc = df[df["TYPE"] == "PROCESS"].copy()
df_proc.rename(columns={
    "FIELD1": "PID", "FIELD2": "UID", "FIELD3": "%CPU",
    "FIELD4": "%MEM", "FIELD5": "COMMAND"
}, inplace=True)

df_proc["PID"] = pd.to_numeric(df_proc["PID"], errors="coerce")
df_proc["UID"] = pd.to_numeric(df_proc["UID"], errors="coerce")
df_proc["%CPU"] = pd.to_numeric(df_proc["%CPU"], errors="coerce")
df_proc.dropna(subset=["PID","UID","%CPU","COMMAND"], inplace=True)

df_proc["PID"] = df_proc["PID"].astype(int)
df_proc["UID"] = df_proc["UID"].astype(int)

def uid_to_name(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except Exception:
        return str(uid)

df_proc["USER"] = df_proc["UID"].apply(uid_to_name)

# -----------------  Top PID 선정 (시간 변화 목적) -----------------
t_end = df_proc["TIMESTAMP"].max()

if WINDOW_SEC and WINDOW_SEC > 0:
    window = df_proc[df_proc["TIMESTAMP"] >= (t_end - pd.Timedelta(seconds=WINDOW_SEC))]
    if window.empty:
        window = df_proc
    score = window.groupby("PID")["%CPU"].mean()
    basis = f"last {WINDOW_SEC}s mean"
else:
    score = df_proc.groupby("PID")["%CPU"].mean()
    basis = "full-range mean"

top_pids = score.sort_values(ascending=False).head(TOP_N).index.tolist()
print(f"\n[Top {TOP_N} PIDs by {basis}]")
print(score.sort_values(ascending=False).head(TOP_N).to_string())

df_top = df_proc[df_proc["PID"].isin(top_pids)].sort_values(["PID","TIMESTAMP"])

# 라벨: PID | USER | COMMAND (가장 최근값 기준)
last_meta = (
    df_top.sort_values("TIMESTAMP")
          .groupby("PID")
          .tail(1)[["PID","USER","COMMAND"]]
          .set_index("PID")
)

def label_for(pid: int) -> str:
    if pid in last_meta.index:
        r = last_meta.loc[pid]
        return f"{pid} | {r['USER']} | {r['COMMAND']}"
    return str(pid)

# ----------------- CORE 전처리(옵션: 원하면 제거 가능) -----------------
df_core = df[df["TYPE"] == "CORE"].copy()
df_core.rename(columns={
    "FIELD1": "CPU", "FIELD2": "%USER", "FIELD3": "%SYSTEM", "FIELD4": "%IDLE"
}, inplace=True)

for col in ["%USER","%SYSTEM","%IDLE"]:
    df_core[col] = df_core[col].astype(str).str.strip().str.replace(",", ".", regex=False)
    df_core[col] = pd.to_numeric(df_core[col], errors="coerce")

df_core.dropna(subset=["%USER","%SYSTEM"], inplace=True)
df_core["%USED"] = df_core["%USER"] + df_core["%SYSTEM"]

pivot_core = df_core.pivot_table(
    index="TIMESTAMP",
    columns="CPU",
    values="%USED",
    aggfunc="mean"
)

pivot_core = pivot_core.drop(columns=["all"], errors="ignore")

# ----------------- Plot -----------------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12), sharex=True)

#  프로세스(PID)별 시간 변화
for pid in top_pids:
    x = df_top[df_top["PID"] == pid]
    if x.empty:
        continue

    if len(x) < 2:
        ax1.scatter(x["TIMESTAMP"], x["%CPU"], label=label_for(pid))
    else:
        ax1.plot(x["TIMESTAMP"], x["%CPU"], label=label_for(pid))

ax1.set_title(f"Process CPU Usage Over Time (Top {TOP_N} by {basis})")
ax1.set_ylabel("CPU Usage (%)")
ax1.grid(True)
ax1.legend(title="PID | USER | COMMAND", bbox_to_anchor=(1.05, 1), loc="upper left")

# 코어 그래프(옵션)
if pivot_core.empty or pivot_core.select_dtypes(include="number").shape[1] == 0:
    ax2.set_title("CPU Core Usage Over Time (no CORE numeric data parsed)")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("CPU Usage (%)")
    ax2.grid(True)
else:
    pivot_core.plot(ax=ax2)
    ax2.set_title("CPU Core Usage Over Time")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("CPU Usage (%)")
    ax2.grid(True)
    ax2.legend(title="CPU Core", bbox_to_anchor=(1.05, 1), loc="upper left")

plt.tight_layout()
plt.show()
