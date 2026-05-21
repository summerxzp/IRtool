#!/usr/bin/env python3
"""Create 7z self-extracting archive"""

import os
from pathlib import Path

dist_dir = Path(__file__).parent / "dist"
sfx_module = Path("C:/Program Files/7-Zip/7z.sfx")
archive = dist_dir / "IRtool-v1.0.0.7z"
output = dist_dir / "IRtool-v1.0.0-7z.exe"

config_content = """;!@Install@!UTF-8!
Title="IRtool v1.0.0"
ExtractPath="%TEMP%\\IRtool-1.0.0-%PID%"
GUIRunOnce="%TEMP%\\IRtool-1.0.0-%PID%\\IRtool-v1.0.0.exe"
;!@InstallEnd@!
"""

with open(sfx_module, "rb") as f:
    sfx_bytes = f.read()

with open(archive, "rb") as f:
    archive_bytes = f.read()

config_bytes = config_content.encode("utf-8")

output_bytes = sfx_bytes + config_bytes + archive_bytes

with open(output, "wb") as f:
    f.write(output_bytes)

print(f"Created: {output}")
print(f"Size: {output.stat().st_size / 1024 / 1024:.2f} MB")
