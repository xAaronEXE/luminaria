import threading

shutdown=threading.Event()
restart_requested=threading.Event()

def request_shutdown():
    shutdown.set()

def request_restart():
    restart_requested.set()
    shutdown.set()
