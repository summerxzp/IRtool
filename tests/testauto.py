import subprocess
import time
from pathlib import Path

AUTORUNS = r"./tools/autorunsc64.exe"
OUT_FILE = Path("autoruns_raw.csv")

cmd = [
    AUTORUNS,
    "-accepteula",
    "-a", "*",
    "-c",
    "-s",
    "-nobanner"
]


print("[*] Starting autorunsc...")
start = time.time()

proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

stdout, stderr = proc.communicate()

elapsed = time.time() - start
print(f"[*] Finished in {elapsed:.2f} seconds")
print(f"[*] Return code: {proc.returncode}")

# 保存原始输出（不要 decode）
OUT_FILE.write_bytes(stdout)

print(f"[*] Output saved to {OUT_FILE.resolve()}")
print(f"[*] Output size: {len(stdout) / 1024:.1f} KB")

if stderr:
    print("[!] STDERR:")
    print(stderr.decode(errors="ignore")[:500])
