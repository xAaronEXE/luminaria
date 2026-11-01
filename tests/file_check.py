import json,tempfile,unittest,zipfile
from pathlib import Path
from backend.file_check import inspect

def office(path,parts):
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        for name,xml in parts.items(): z.writestr(name,xml)

class FileCheck(unittest.TestCase):
    def setUp(self): self.d=Path(tempfile.mkdtemp())
    def test_text_saved_as_docx_is_caught(self):
        p=self.d/'coffee_history.docx';p.write_text('## History of Coffee\nThe history of coffee spans...')
        r=inspect(p);self.assertFalse(r['ok']);self.assertIn('wrong extension',r['problem'])
    def test_real_docx_xlsx_pptx(self):
        p=self.d/'a.docx';office(p,{'word/document.xml':'<w:document><w:body><w:p><w:r><w:t>History of coffee</w:t></w:r></w:p><w:p><w:r><w:t>Ethiopia</w:t></w:r></w:p></w:body></w:document>'})
        r=inspect(p);self.assertTrue(r['ok']);self.assertEqual(r['paragraphs'],2);self.assertIn('History of coffee',r['preview'])
        p=self.d/'b.xlsx';office(p,{'xl/workbook.xml':'<w/>','xl/worksheets/sheet1.xml':'<sheetData><row><c r="A1"/><c r="B1"/></row></sheetData>'})
        self.assertEqual(inspect(p)['cells'],2)
        p=self.d/'c.pptx';office(p,{'ppt/presentation.xml':'<p/>','ppt/slides/slide1.xml':'<p:sld><a:t>Title slide</a:t></p:sld>'})
        r=inspect(p);self.assertEqual(r['slides'],1);self.assertIn('Title slide',r['preview'])
        p=self.d/'empty.docx';office(p,{'word/document.xml':'<w:document/>'})
        self.assertIn('no text',inspect(p)['problem'])
    def test_pdf_json_html_image_and_missing(self):
        p=self.d/'x.pdf';p.write_bytes(b'not a pdf');self.assertIn('not a PDF',inspect(p)['problem'])
        p=self.d/'y.pdf';p.write_bytes(b'%PDF-1.4\n1 0 obj<</Type /Page /Parent 2 0 R>>endobj\n%%EOF');self.assertTrue(inspect(p)['ok'])
        p=self.d/'t.pdf';p.write_bytes(b'%PDF-1.4\n1 0 obj<</Type /Page >>');self.assertIn('cut off',inspect(p)['problem'])
        p=self.d/'d.json';p.write_text('{"a":');self.assertIn('Invalid JSON',inspect(p)['problem'])
        p=self.d/'timeline.html';p.write_text('<html><head><title>Project Timeline</title></head><body><div>x</div></body></html>')
        r=inspect(p);self.assertTrue(r['ok']);self.assertEqual(r['title'],'Project Timeline')
        p=self.d/'i.png';p.write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0\0\0\rIHDR'+(640).to_bytes(4,'big')+(480).to_bytes(4,'big')+b'\0'*8)
        r=inspect(p);self.assertEqual((r['width'],r['height']),(640,480))
        p=self.d/'fake.png';p.write_text('hello');self.assertFalse(inspect(p)['ok'])
        self.assertIn('no file',inspect(self.d/'nope.txt')['problem']);(self.d/'e.txt').write_text('');self.assertIn('empty',inspect(self.d/'e.txt')['problem'])
if __name__=='__main__':unittest.main()
