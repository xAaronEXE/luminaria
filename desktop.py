"""Luminaria Windows desktop host. WebView2 + loopback-only Python API."""
import os,sys,time,threading,urllib.request,json,logging
from pathlib import Path

def main():
    import argparse
    parser=argparse.ArgumentParser(description='Luminaria local AI desktop. Agent tools are enabled by default; the saved permission mode controls execution.')
    parser.add_argument('--agent',action='store_true',default=True,help='Enable agent tools (already enabled by default)')
    parser.add_argument('--server',action='store_true',help='Run the local backend without the desktop window')
    parser.add_argument('--version',action='version',version='Luminaria 0.2.2')
    options=parser.parse_args()
    from backend.config import DATA,ROOT
    logging.basicConfig(filename=DATA/'desktop.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    # Webview/uvicorn may write diagnostics even from a windowed executable.
    if sys.stdout is None: sys.stdout=open(DATA/'stdout.log','a',encoding='utf-8')
    if sys.stderr is None: sys.stderr=open(DATA/'stderr.log','a',encoding='utf-8')
    url='http://127.0.0.1:3210'
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
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=3210,log_level='warning',access_log=False,log_config=None))
        thread=threading.Thread(target=server.run,daemon=True);thread.start()
        for _ in range(200):
            if server.started:break
            if not thread.is_alive():raise RuntimeError('Backend failed. See desktop.log')
            time.sleep(.1)
    if options.server:
        try:
            while True:time.sleep(1)
        except KeyboardInterrupt:pass
    else:
        import webview
        webview.create_window('Luminaria',url,width=1440,height=940,min_size=(780,620),background_color='#141A17',text_select=True)
        webview.start(gui='edgechromium',debug=False,private_mode=False,storage_path=str(DATA/'webview'))
    if server:
        server.should_exit=True;thread.join(timeout=12)
        from backend.runtime import stop_owned
        stop_owned()

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

