"""External OAuth browser with placement scoped to Luminaria-owned windows."""
import os,subprocess,threading,time
from pathlib import Path

def visible_browser_windows(gui):
    result=[]
    def collect(hwnd,_):
        if gui.IsWindowVisible(hwnd) and gui.GetClassName(hwnd)=='Chrome_WidgetWin_1':result.append(hwnd)
    gui.EnumWindows(collect,None)
    return set(result)

def place_browser(profile,before,geometry,timeout=8):
    # Only move a NEW window belonging to our own browser profile. Never move
    # the user's normal browser or an unrelated existing window.
    try:
        import win32gui,win32process,psutil
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            for hwnd in visible_browser_windows(win32gui)-before:
                try:
                    _,pid=win32process.GetWindowThreadProcessId(hwnd)
                    args=psutil.Process(pid).cmdline()
                    if '--user-data-dir='+str(profile) not in args:continue
                    win32gui.ShowWindow(hwnd,9) # restore before applying geometry
                    win32gui.SetWindowPos(hwnd,0,*geometry,0x0040) # HWND_TOP, SHOWWINDOW
                    try:win32gui.SetForegroundWindow(hwnd)
                    except Exception:pass # Windows may restrict foreground focus
                    return True
                except (OSError,psutil.Error):continue
            time.sleep(.1)
    except (ImportError,OSError):pass
    return False

def desktop_browser(url):
    if os.name!='nt':return False
    try:
        import webview,win32gui
        from .config import DATA
        if not webview.windows:return False
        owner=webview.windows[0]
        width=min(680,max(480,int(owner.width)-80));height=min(820,max(500,int(owner.height)-60))
        x=int(owner.x)+(int(owner.width)-width)//2;y=int(owner.y)+(int(owner.height)-height)//2
        for folder in ('PROGRAMFILES(X86)','PROGRAMFILES','LOCALAPPDATA'):
            base=os.environ.get(folder)
            if not base:continue
            exe=Path(base)/'Microsoft'/'Edge'/'Application'/'msedge.exe'
            if exe.is_file():
                profile=DATA/'sign-in-browser';profile.mkdir(parents=True,exist_ok=True)
                before=visible_browser_windows(win32gui)
                subprocess.Popen([str(exe),'--new-window','--no-first-run','--no-default-browser-check','--user-data-dir='+str(profile),url,f'--window-position={x},{y}',f'--window-size={width},{height}'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                threading.Thread(target=place_browser,args=(profile,before,(x,y,width,height)),daemon=True).start()
                return True
    except (ImportError,OSError,AttributeError,TypeError,ValueError):pass
    return False
