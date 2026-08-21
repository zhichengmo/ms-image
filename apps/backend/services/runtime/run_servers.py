from pathlib import Path
from multiprocessing import Process
import signal
import sys

import uvicorn


RUNTIME_ROOT = Path(__file__).resolve().parent
REPO_ROOT = RUNTIME_ROOT.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run_user_api():
    """运行用户端API"""
    uvicorn.run(
        "apps.backend.services.runtime.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


def run_admin_api():
    """运行管理员API"""
    uvicorn.run(
        "apps.backend.services.runtime.main:admin_app",
        host="0.0.0.0",
        port=8001,
        reload=False,
    )


if __name__ == "__main__":
    shutdown_signal: list[int | None] = [None]

    def request_shutdown(signum, _frame):
        shutdown_signal[0] = signum

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    processes = [
        Process(target=run_user_api, name="ms-image-user"),
        Process(target=run_admin_api, name="ms-image-admin"),
    ]
    for process in processes:
        process.start()

    exit_code = 0
    try:
        # A two-process launcher must not leave the other plane serving after
        # one plane has exited.  Polling also makes the failing exit code
        # observable to the container/orchestrator.
        while True:
            if shutdown_signal[0] is not None:
                exit_code = 128 + shutdown_signal[0]
                break
            finished = next(
                (process for process in processes if not process.is_alive()),
                None,
            )
            if finished is not None:
                exit_code = finished.exitcode or 1
                break
            for process in processes:
                process.join(timeout=0.2)
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(timeout=5)
        for process in processes:
            if process.is_alive():
                process.kill()
                process.join(timeout=1)

    raise SystemExit(exit_code)
