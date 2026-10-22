"""Luminaria Windows desktop host. WebView2 + loopback-only Python API."""
import os,sys,time,threading,urllib.request,json,logging
from pathlib import Path

def main():
    import argparse
    from backend.config import VERSION
    parser=argparse.ArgumentParser(description='Luminaria local AI desktop. Agent tools are enabled by default; the saved permission mode controls execution.')
    parser.add_argument('--agent',action='store_true',default=True,help='Enable agent tools (already enabled by default)')
    parser.add_argument('--server',action='store_true',help='Run the local backend without the desktop window')
    parser.add_argument('--safe-graphics',action='store_true',help='Disable WebGL and use the static voice interface for this launch')
    parser.add_argument('--version',action='version',version='Luminaria '+VERSION)
    options=parser.parse_args()
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
        kernel.CreateMutexW.restype=wintypes.HANDLE
        guard=kernel.CreateMutexW(None,False,'Local\\LuminariaDesktop')
        if not guard:raise ctypes.WinError(ctypes.get_last_error())
    if options.safe_graphics:
        os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']=(os.environ.get('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS','')+' --disable-webgl').strip()
    from backend.config import DATA,ROOT
    logging.basicConfig(filename=DATA/'desktop.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    # Webview/uvicorn may write diagnostics even from a windowed executable.
    if sys.stdout is None: sys.stdout=open(DATA/'stdout.log','a',encoding='utf-8')
    if sys.stderr is None: sys.stderr=open(DATA/'stderr.log','a',encoding='utf-8')
    port=int(os.environ.get('STUDIO_PORT','3210'))
    if not 1024<=port<=65535:raise ValueError('STUDIO_PORT must be between 1024 and 65535')
    url=f'http://127.0.0.1:{port}'
    already=False
    try:
        with urllib.request.urlopen(url+'/api/bootstrap',timeout=2) as r: already='token' in json.load(r)
    except Exception: pass
    server=None
    if not already:
        from backend.runtime import start_swap
        try: start_swap()
        except Exception as e: logging.warning('Model manager: %s',e)
        import uvicorn
        from backend.app import app
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning',access_log=False,log_config=None))
        thread=threading.Thread(target=server.run,daemon=True);thread.start()
        for _ in range(200):
            if server.started:break
            if not thread.is_alive():raise RuntimeError('Backend failed. See desktop.log')
            time.sleep(.1)
    if options.server:
        from backend.lifecycle import shutdown
        try:
            shutdown.wait()
        except KeyboardInterrupt:pass
    else:
        import webview
        window=webview.create_window('Luminaria',url,width=1440,height=940,min_size=(780,620),background_color='#141A17',text_select=True)
        from backend.lifecycle import shutdown
        def close_for_update():
            shutdown.wait()
            window.destroy()
        threading.Thread(target=close_for_update,daemon=True).start()
        webview.start(gui='edgechromium',debug=False,private_mode=False,storage_path=str(DATA/'webview'))
    if server:
        server.should_exit=True;thread.join(timeout=12)
        from backend.runtime import stop_owned
        stop_owned()
    from backend.lifecycle import restart_requested
    if restart_requested.is_set() and not options.server:
        import subprocess
        command=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve())]
        working=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
        subprocess.Popen(command+sys.argv[1:],cwd=str(working))

if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        from backend.config import DATA
        (DATA/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,'Luminaria could not start. Details: '+str(DATA/'startup-error.log'),'Luminaria',0x10)
        else:raise

