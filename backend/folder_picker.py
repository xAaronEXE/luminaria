"""File and folder selection the user starts. Uses the Windows dialogs of Luminaria's own window, so they open in
front of the app and can reach any folder on the PC. Choosing something here never changes the default folder."""
from pathlib import Path
import threading

_picker_lock=threading.Lock()

def _window():
    try:
        import webview
        return webview.windows[0] if webview.windows else None
    except Exception: return None

def _native(kind,initial,multiple=False):
    """Paths from the app window's own dialog, [] if cancelled, or None when no app window is available."""
    window=_window()
    if window is None: return None
    import webview
    types=getattr(webview,'FileDialog',None)
    mode=getattr(types,'FOLDER' if kind=='folder' else 'OPEN',None) if types else None
    if mode is None: mode=getattr(webview,'FOLDER_DIALOG' if kind=='folder' else 'OPEN_DIALOG')
    initial=Path(initial) if initial else Path.home()
    chosen=window.create_file_dialog(mode,directory=str(initial if initial.is_dir() else Path.home()),allow_multiple=multiple)
    return [str(p) for p in ([chosen] if isinstance(chosen,str) else (chosen or []))]

def _tk(kind,initial,multiple):
    root=None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root=tk.Tk();root.withdraw();root.attributes('-topmost',True);root.lift();root.focus_force()
        start=str(initial) if initial and Path(initial).is_dir() else str(Path.home())
        if kind=='folder':
            one=filedialog.askdirectory(parent=root,title='Choose a folder',initialdir=start,mustexist=True)
            return [one] if one else []
        many=filedialog.askopenfilenames(parent=root,title='Choose files',initialdir=start) if multiple else filedialog.askopenfilename(parent=root,title='Choose a file',initialdir=start)
        return list(many) if multiple else ([many] if many else [])
    except ImportError as error:
        raise ValueError('The Windows file dialog is unavailable in this build. Type or paste the full path instead.') from error
    finally:
        if root is not None:root.destroy()

def choose(kind='folder',initial=None,multiple=False):
    """Full paths the user picked ([] when cancelled)."""
    if not _picker_lock.acquire(blocking=False):
        raise ValueError('A file dialog is already open. Finish or cancel it first.')
    try:
        try: chosen=_native(kind,initial,multiple)
        except Exception: chosen=None
        if chosen is None: chosen=_tk(kind,initial,multiple)
        return [str(Path(p).resolve()) for p in chosen if p]
    finally:_picker_lock.release()

def pick(initial):
    chosen=choose('folder',initial)
    if not chosen:return {'cancelled':True}
    path=Path(chosen[0])
    if not path.is_dir():raise ValueError('The selected folder is no longer available')
    return {'cancelled':False,'path':str(path)}
