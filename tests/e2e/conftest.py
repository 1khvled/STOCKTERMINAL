import os
import sys
import time
import subprocess
import requests
import pytest

@pytest.fixture(scope="session", autouse=True)
def test_server():
    os.environ["STOCKER_TEST_MODE"] = "1"
    os.environ["STOCKER_PORT"] = "5005"
    
    python_exec = sys.executable
    if "venv" not in python_exec.lower():
        # Fallback if pytest runs outside venv, but we should use the venv's python
        python_exec = os.path.join("venv", "Scripts", "python.exe")
        if not os.path.exists(python_exec):
            python_exec = "python"
    
    # Start the server - log to FILE, never PIPE (an undrained PIPE deadlock
    # hangs the server mid-suite once the OS buffer fills).
    import tempfile
    _logf = open(os.path.join(tempfile.gettempdir(), "stocker_e2e_server.log"), "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [python_exec, "-m", "app.server"],
        stdout=_logf,
        stderr=subprocess.STDOUT,
        text=True,
    )
    
    # Wait for it to be ready
    url = "http://127.0.0.1:5005/"
    for _ in range(30):
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(0.5)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        try:
            _logf.close()
            tail = open(os.path.join(tempfile.gettempdir(), "stocker_e2e_server.log"), encoding="utf-8", errors="replace").read()[-2000:]
        except Exception:
            tail = "<no log>"
        raise Exception(f"Test server did not start in time. Tail: {tail}")
    
    yield url
    
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    try:
        _logf.close()
    except Exception:
        pass

@pytest.fixture(scope="session")
def base_url():
    return "http://127.0.0.1:5005"
