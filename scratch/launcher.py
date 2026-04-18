#!/usr/bin/env python
import subprocess
import sys
import os

os.chdir(r"H:\2026\SelfAi\dev\chaitya\unigate")
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

print("Starting server...")
proc = subprocess.Popen(
    [sys.executable, "run.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

print(f"Server started with PID: {proc.pid}")

# Read output line by line for 10 seconds
import time
start = time.time()
while time.time() - start < 10:
    line = proc.stdout.readline()
    if line:
        print(line.strip())
    if proc.poll() is not None:
        print(f"Server exited with code: {proc.returncode}")
        break
    time.sleep(0.1)
else:
    print("Server still running after 10 seconds")

# Check if still running
if proc.poll() is None:
    print("Server is running!")
    print("Web UI: http://localhost:8080/unigate/web/web")
