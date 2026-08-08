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
    # 启动用户端API进程
    user_process = Process(target=run_user_api)
    user_process.start()

    # 启动管理员API进程
    admin_process = Process(target=run_admin_api)
    admin_process.start()

    try:
        user_process.join()
        admin_process.join()
    except KeyboardInterrupt:
        user_process.terminate()
        admin_process.terminate()