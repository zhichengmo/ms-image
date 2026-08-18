import uvicorn
import asyncio
from multiprocessing import Process


def run_user_api():
    """运行用户端API"""
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


def run_admin_api():
    """运行管理员API"""
    uvicorn.run("main:admin_app", host="0.0.0.0", port=8001, reload=False)


if __name__ == "__main__":
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
            finished = next(
                (process for process in processes if not process.is_alive()),
                None,
            )
            if finished is not None:
                exit_code = finished.exitcode or 0
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

    raise SystemExit(exit_code)
