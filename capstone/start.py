"""Launch the dashboard + API together (non-Docker), with shared Prometheus
multiprocess metrics so a pipeline run from either process shows on /metrics.

    python start.py
        dashboard  http://localhost:8000
        webhook    http://localhost:8001/api/v1/pipeline/submit
        metrics    http://localhost:8001/metrics
"""
import os
import sys
import glob
import signal
import subprocess
from pathlib import Path

MP_DIR = os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR",
                               str(Path("data") / "pf_metrics"))
Path(MP_DIR).mkdir(parents=True, exist_ok=True)
for f in glob.glob(os.path.join(MP_DIR, "*")):  # clear stale metric files
    try:
        os.remove(f)
    except OSError:
        pass

env = os.environ.copy()
# Make 'src' importable for the spawned Streamlit/uvicorn processes regardless
# of each tool's default sys.path (run start.py from the repo root).
_root = str(Path(__file__).resolve().parent)
env["PYTHONPATH"] = _root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
procs = []
try:
    procs.append(subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "src/ui/app_prod.py",
         "--server.port=8000", "--server.address=0.0.0.0"], env=env))
    procs.append(subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.api_server:app",
         "--host", "0.0.0.0", "--port", "8001"], env=env))
    print("dashboard  http://localhost:8000")
    print("webhook    http://localhost:8001/api/v1/pipeline/submit")
    print("metrics    http://localhost:8001/metrics")
    for p in procs:
        p.wait()
except KeyboardInterrupt:
    pass
finally:
    for p in procs:
        try:
            p.send_signal(signal.SIGTERM)
        except Exception:
            pass
