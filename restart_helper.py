#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import signal

script_dir = "/Users/imac/Data/TRAE_IDE/web_management_mysql20260511/app"
script_name = "app.py"
script_path = os.path.join(script_dir, script_name)
python_exec = sys.executable

if len(sys.argv) > 1:
    old_pid = int(sys.argv[1])
    
    try:
        os.kill(old_pid, signal.SIGTERM)
        time.sleep(1)
        try:
            os.kill(old_pid, 0)
            os.kill(old_pid, signal.SIGKILL)
            time.sleep(0.5)
        except ProcessLookupError:
            pass
    except ProcessLookupError:
        pass
    
    time.sleep(1)
    
    proc = subprocess.Popen(
        [python_exec, script_path],
        cwd=script_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
