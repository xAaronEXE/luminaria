import unittest
from backend import admin_helper as A

class AdminHelper(unittest.TestCase):
    def test_builds_only_listed_jobs_with_safe_arguments(self):
        d,c=A.build('install_program',{'package':'Git.Git'}); self.assertIn("winget install --id 'Git.Git' --exact",c)
        d,c=A.build('firewall_allow_port',{'port':8080,'name':'dev server'}); self.assertIn('-Profile Private',c); self.assertIn("'Luminaria - dev server'",c)
        d,c=A.build('service_startup',{'service':'Spooler','startup':'manual'}); self.assertIn('-StartupType Manual',c)
    def test_refuses_everything_else(self):
        bad=[('run_shell',{}),('install_program',{'package':'Git.Git; Remove-Item C:\\Windows'}),('install_program',{'package':"x' ; calc '"}),
             ('enable_windows_feature',{'feature':'a b'}),('service_stop',{'service':'WinDefend'}),('service_stop',{'service':'mpssvc'}),
             ('firewall_allow_port',{'port':22}),('firewall_allow_port',{'port':'80; calc'}),('firewall_allow_port',{'port':8080,'protocol':'ICMP'}),
             ('service_startup',{'service':'Spooler','startup':'boot'}),('firewall_remove_rule',{'name':'x;y'})]
        for op,args in bad:
            with self.subTest(op=op,args=args):
                with self.assertRaises(ValueError): A.build(op,args)
    def test_model_text_never_reaches_the_command_unquoted(self):
        d,c=A.build('install_program',{'package':'Python.Python.3.12'})
        self.assertNotIn('Python.Python.3.12 ',c.replace("'Python.Python.3.12'",''))

if __name__=='__main__':unittest.main()
