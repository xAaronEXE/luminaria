import threading

shutdown=threading.Event()

def request_shutdown():
    shutdown.set()
