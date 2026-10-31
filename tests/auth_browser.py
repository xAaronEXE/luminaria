import os,sys,unittest
from types import SimpleNamespace
from unittest.mock import patch
from backend import auth_browser
@unittest.skipUnless(os.name=='nt','Windows browser placement')
class BrowserPlacementTests(unittest.TestCase):
 def test_external_window_uses_owner_monitor_including_negative_coordinates(self):
  owner=SimpleNamespace(x=-1600,y=100,width=1400,height=900)
  with patch.dict(sys.modules,{'webview':SimpleNamespace(windows=[owner])}),patch.object(auth_browser.Path,'is_file',return_value=True),patch.object(auth_browser,'visible_browser_windows',return_value={10}),patch.object(auth_browser.threading,'Thread') as thread,patch.object(auth_browser.subprocess,'Popen') as launch:
   self.assertTrue(auth_browser.desktop_browser('https://identity.example/authorize'))
  args=launch.call_args.args[0];self.assertIn('--new-window',args);self.assertIn('--window-position=-1240,140',args);self.assertIn('--window-size=680,820',args);self.assertTrue(any(a.startswith('--user-data-dir=') for a in args));thread.return_value.start.assert_called_once()
 def test_no_desktop_window_uses_default_browser_fallback(self):
  with patch.dict(sys.modules,{'webview':SimpleNamespace(windows=[])}),patch.object(auth_browser.subprocess,'Popen') as launch:
   self.assertFalse(auth_browser.desktop_browser('https://identity.example/authorize'));launch.assert_not_called()
 def test_moves_only_new_window_with_our_browser_profile(self):
  from unittest.mock import Mock
  gui=Mock();process=SimpleNamespace(GetWindowThreadProcessId=lambda hwnd:(0,hwnd))
  psutil=SimpleNamespace(Process=lambda pid:SimpleNamespace(cmdline=lambda:['edge','--user-data-dir=/owned' if pid==30 else '--user-data-dir=/personal']),Error=OSError)
  with patch.dict(sys.modules,{'win32gui':gui,'win32process':process,'psutil':psutil}),patch.object(auth_browser,'visible_browser_windows',return_value={10,20,30}):
   self.assertTrue(auth_browser.place_browser('/owned',{10},(-1240,140,680,820),timeout=1))
  gui.SetWindowPos.assert_called_once_with(30,0,-1240,140,680,820,0x0040)
  gui.SetForegroundWindow.assert_called_once_with(30)
 def test_does_not_move_existing_or_unrelated_browser_window(self):
  from unittest.mock import Mock
  gui=Mock();process=SimpleNamespace(GetWindowThreadProcessId=lambda hwnd:(0,hwnd))
  psutil=SimpleNamespace(Process=lambda pid:SimpleNamespace(cmdline=lambda:['edge','--user-data-dir=/personal']),Error=OSError)
  with patch.dict(sys.modules,{'win32gui':gui,'win32process':process,'psutil':psutil}),patch.object(auth_browser,'visible_browser_windows',return_value={10,20}):
   self.assertFalse(auth_browser.place_browser('/owned',{10},(0,0,680,820),timeout=.01))
  gui.SetWindowPos.assert_not_called()
if __name__=='__main__':unittest.main()
