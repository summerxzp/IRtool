import subprocess
import time
from pathlib import Path

AUTORUNS = r"./tools/autorunsc64.exe"
OUT_FILE = Path("autoruns_raw.csv")

# 优化方案1: 只扫描关键类别（推荐）
# 包含最常用的持久化位置：Logon + Services + Tasks + Boot + Winlogon
# 排除耗时的：Codecs, WMI, Winsock, Known DLLs, Office addins等
cmd_optimized = [
    AUTORUNS,
    "-accepteula",
    "-a", "blstw",  # b=Boot, l=Logon, s=Services, t=Tasks, w=Winlogon
    "-c",
    "-s",
    "-nobanner"
]

# 优化方案2: 仅Logon（最快，与GUI默认一致）
cmd_logon_only = [
    AUTORUNS,
    "-accepteula",
    "-a", "l",  # 仅Logon
    "-c",
    "-s",
    "-nobanner"
]

# 优化方案3: 完整扫描但排除最慢的几个类别
cmd_balanced = [
    AUTORUNS,
    "-accepteula",
    "-a", "bdeghlprstw",  # 排除 m(WMI), n(Winsock), k(Known DLLs), i(IE), o(Office), c(Codecs)
    "-c",
    "-s",
    "-nobanner"
]

print("=" * 60)
print("测试方案1: 关键类别 (blstw)")
print("=" * 60)
start = time.time()
proc = subprocess.Popen(cmd_optimized, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()
elapsed = time.time() - start
print(f"[*] Finished in {elapsed:.2f} seconds")
print(f"[*] Output size: {len(stdout) / 1024:.1f} KB")

print("\n" + "=" * 60)
print("测试方案2: 仅Logon (l)")
print("=" * 60)
start = time.time()
proc = subprocess.Popen(cmd_logon_only, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()
elapsed = time.time() - start
print(f"[*] Finished in {elapsed:.2f} seconds")
print(f"[*] Output size: {len(stdout) / 1024:.1f} KB")

print("\n" + "=" * 60)
print("测试方案3: 平衡模式 (bdeghlprstw)")
print("=" * 60)
start = time.time()
proc = subprocess.Popen(cmd_balanced, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()
elapsed = time.time() - start
print(f"[*] Finished in {elapsed:.2f} seconds")
print(f"[*] Output size: {len(stdout) / 1024:.1f} KB")

print("\n" + "=" * 60)
print("测试方案4: 原始全扫描 (*)")
print("=" * 60)
cmd_all = [
    AUTORUNS,
    "-accepteula",
    "-a", "*",
    "-c",
    "-s",
    "-nobanner"
]
start = time.time()
proc = subprocess.Popen(cmd_all, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()
elapsed = time.time() - start
print(f"[*] Finished in {elapsed:.2f} seconds")
print(f"[*] Output size: {len(stdout) / 1024:.1f} KB")
