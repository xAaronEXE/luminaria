import os,tempfile,unittest
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
from backend.engine import unsupported_links

class Sources(unittest.TestCase):
    def test_flags_links_never_read(self):
        tools=['{"results":[{"url":"https://www.example.com/guide/install","title":"Install"}]}','Fetched https://docs.python.org/3/library/re.html']
        reply='See [the guide](https://example.com/guide/install/) and https://docs.python.org/3/library/re.html. Also https://made-up.example.org/page.'
        self.assertEqual(unsupported_links(reply,tools),['https://made-up.example.org/page'])
    def test_a_section_link_of_a_page_read_is_fine(self):
        self.assertEqual(unsupported_links('https://docs.python.org/3/library/re.html#re.sub',['https://docs.python.org/3/library/re.html']),[])
    def test_nothing_read_means_nothing_flagged_here(self):
        self.assertEqual(unsupported_links('no links at all',['https://a.example']),[])

if __name__=='__main__':unittest.main()
