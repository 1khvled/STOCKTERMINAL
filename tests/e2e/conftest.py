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
    
    # Start the server
    proc = subprocess.Popen(
        [python_exec, "-m", "app.server"],
        stdout=subprocess.PIPE,
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
        out, _ = proc.communicate(timeout=2)
        proc.terminate()
        proc.wait()
        raise Exception(f"Test server did not start in time. Output: {out}")
    
    yield url
    
    proc.terminate()
    proc.wait()

@pytest.fixture(scope="session")
def base_url():
    return "http://127.0.0.1:5005"
