"""User-initiated native folder selection; never changes the working folder."""
from pathlib import Path
import threading

_picker_lock=threading.Lock()

def pick(initial):
    if not _picker_lock.acquire(blocking=False):
        raise ValueError('A folder picker is already open. Finish or cancel it first.')
    root=None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root=tk.Tk();root.withdraw();root.attributes('-topmost',True)
        initial=Path(initial)
        selected=filedialog.askdirectory(parent=root,title='Choose Luminaria working folder',
            initialdir=str(initial) if initial.is_dir() else str(Path.home()),mustexist=True)
        if not selected:return {'cancelled':True}
        path=Path(selected).resolve()
        if not path.is_dir():raise ValueError('The selected folder is no longer available')
        return {'cancelled':False,'path':str(path)}
    except ImportError as error:
        raise ValueError('The native folder picker is unavailable in this build. Enter a folder path instead.') from error
    finally:
        try:
            if root is not None:root.destroy()
        finally:_picker_lock.release()
