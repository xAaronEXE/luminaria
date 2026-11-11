import os,unittest
from backend import jobs

class Jobs(unittest.TestCase):
    def test_does_nothing_off_windows_and_is_safe_to_close_twice(self):
        job=jobs.Job()
        if os.name!='nt': self.assertIsNone(job.handle); self.assertFalse(job.add(os.getpid()))
        job.close(); job.close()
        with jobs.Job() as j: pass
    @unittest.skipUnless(os.name=='nt','Windows only')
    def test_closing_the_job_ends_child_processes(self):
        import subprocess,time
        p=subprocess.Popen(['powershell','-NoProfile','-Command','Start-Sleep 30'],creationflags=subprocess.CREATE_NO_WINDOW)
        job=jobs.Job(); self.assertTrue(job.add(p.pid)); job.close()
        for _ in range(50):
            if p.poll() is not None: break
            time.sleep(0.1)
        self.assertIsNotNone(p.poll())

if __name__=='__main__':unittest.main()
