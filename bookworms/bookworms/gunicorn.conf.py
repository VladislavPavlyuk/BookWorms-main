"""
Gunicorn hooks — гарантований старт purge у кожному worker.
"""


def post_worker_init(worker):
    try:
        from mainApp.registration_service import start_purge_thread

        start_purge_thread()
        print(f"gunicorn post_worker_init: purge armed (pid={worker.pid})", flush=True)
    except Exception as e:
        print(f"gunicorn post_worker_init purge failed: {e}", flush=True)
