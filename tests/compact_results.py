import unittest
from backend.compact import render

class CompactResults(unittest.TestCase):
    def test_bookkeeping_dropped_and_text_verbatim(self):
        out=render({'status':'ok','source':'https://x.dev','retrieved_at':1.5,'duration_ms':3,'attempts':1,'revision':'abc','truncated':False,
                    'trust':'untrusted','text':'line "one"\nline two'})
        self.assertNotIn('retrieved_at',out);self.assertNotIn('revision',out);self.assertNotIn('status',out)
        self.assertIn('line "one"\nline two',out);self.assertTrue(out.startswith('(Content from files'))
    def test_errors_and_lists_stay_readable(self):
        self.assertIn('status: error',render({'status':'error','message':'The site answered 404.'}))
        files=render([{'name':'src','path':'src','directory':True,'bytes':0},{'name':'a.py','path':'a.py','directory':False,'bytes':2048}])
        self.assertEqual(files,'- src/\n- a.py (2.0 KB)')
        self.assertEqual(render([]),'(none)')
        self.assertIn('exit_code: 1',render({'exit_code':1,'stdout':'','stderr':'Traceback\n  boom'}))
        self.assertIn('- title: A | url: https://a',render({'results':[{'title':'A','url':'https://a'}]}))

if __name__=='__main__': unittest.main()
