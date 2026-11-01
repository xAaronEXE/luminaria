import os,tempfile,unittest
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
from pathlib import Path
from backend import memory_file as mf, config
from backend.store import Store

class MemoryFile(unittest.TestCase):
    def setUp(self):
        self.dir=Path(tempfile.mkdtemp()); mf.PATH=self.dir/'MEMORY.md'
        self.store=Store(self.dir/'s.sqlite3')
    def test_old_entries_migrate_into_markdown_and_are_retired(self):
        self.store.save_memory('Editor','Prefers VS Code with tabs')
        self.store.save_memory('Name','Aaron')
        text=mf.read(self.store)
        self.assertIn('- **Editor:** Prefers VS Code with tabs',text);self.assertIn('## Preferences',text)
        self.assertEqual([m['id'] for m in self.store.memory()],[mf.ROW],'only the sync mirror remains')
        self.assertEqual(mf.PATH.read_text(),text)
    def test_remember_goes_under_notes_before_the_next_heading(self):
        mf.write(self.store,'# Memory\n\n## Notes\n- old\n\n## Later\n- keep\n')
        mf.remember(self.store,'Color','likes teal')
        text=mf.PATH.read_text()
        self.assertLess(text.index('likes teal'),text.index('## Later'));self.assertIn('- old\n- **Color:** likes teal',text)
        self.assertIn('## Later\n- keep',text)
        mf.write(self.store,'# Memory\n');mf.remember(self.store,'','plain note')
        self.assertTrue(mf.PATH.read_text().rstrip().endswith(mf.PATH.read_text().strip().splitlines()[-1]))
        self.assertIn('## Notes\n- plain note',mf.PATH.read_text())
    def test_sync_mirror_matches_file_and_creates_it_on_a_new_device(self):
        mf.write(self.store,'# Memory\n- synced\n')
        mirror=[m for m in self.store.memory() if m['id']==mf.ROW][0]['content']
        self.assertEqual(mirror,'# Memory\n- synced\n')
        mf.PATH.unlink(); self.assertEqual(mf.read(self.store),'# Memory\n- synced\n'); self.assertTrue(mf.PATH.is_file())
    def test_prompt_is_budgeted_and_includes_project_notes(self):
        mf.write(self.store,'# Memory\n## Notes\n'+''.join(f'- note {i} '+'x'*60+'\n' for i in range(300)))
        work=Path(tempfile.mkdtemp());(work/'LUMINARIA.md').write_text('# Project\nUse pnpm, not npm.');config.CONFIG['workspace']=str(work)
        out=mf.prompt(self.store)
        self.assertIn('MEMORY.md continues',out);self.assertIn('Use pnpm, not npm.',out);self.assertLess(len(out),mf.PROMPT_BUDGET+mf.PROJECT_BUDGET+800)
        self.assertEqual(mf.search(self.store,'note 299')[0][:12],'- note 299 x')
    def test_empty_template_adds_nothing_to_the_prompt(self):
        config.CONFIG['workspace']=tempfile.mkdtemp(); mf.write(self.store,mf.TEMPLATE)
        self.assertEqual(mf.prompt(self.store),'')
    def test_limits(self):
        with self.assertRaises(ValueError): mf.write(self.store,'x'*(mf.MAX_FILE+1))
        with self.assertRaises(ValueError): mf.remember(self.store,'t','')
if __name__=='__main__':unittest.main()
