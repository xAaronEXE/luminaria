import io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from docx import Document
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from backend import attachments

def pdf(*pages):
 buffer=io.BytesIO();page=canvas.Canvas(buffer)
 for text in pages:page.drawString(72,720,text);page.showPage()
 page.save();return buffer.getvalue()

def docx(paragraphs,table=None):
 document=Document()
 for text in paragraphs:document.add_paragraph(text)
 if table:
  grid=document.add_table(rows=len(table),cols=len(table[0]))
  for r,row in enumerate(table):
   for c,value in enumerate(row):grid.cell(r,c).text=value
 buffer=io.BytesIO();document.save(buffer);return buffer.getvalue()

class DocumentAttachmentTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();root=Path(self.folder.name);self.workspace=root/'Files';self.workspace.mkdir()
  def bounded(path):
   p=(self.workspace/path).resolve()
   if not p.is_relative_to(self.workspace):raise ValueError('outside')
   return p
  self.patches=[patch.object(attachments,'DATA',root),patch.object(attachments,'workspace_path',bounded)]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  self.folder.cleanup()

 def test_pdf_keeps_original_and_gives_model_page_marked_text(self):
  raw=pdf('Quarterly revenue rose','Appendix PAGE_TWO_SENTINEL')
  item=attachments.save('report.pdf',raw)
  self.assertEqual((self.workspace/item['original']).read_bytes(),raw)
  text=(self.workspace/item['path']).read_text('utf-8')
  self.assertIn('--- Page 1 ---\nQuarterly revenue rose',text);self.assertIn('--- Page 2 ---',text);self.assertIn('PAGE_TWO_SENTINEL',text)
  part=attachments.text_part(item['id'])['text']
  self.assertIn('report.pdf',part);self.assertIn('original saved at '+item['original'],part);self.assertIn('Quarterly revenue rose',part)

 def test_docx_includes_paragraphs_and_tables(self):
  item=attachments.save('plan.docx',docx(['Launch checklist','Ship on Friday'],[['Owner','Task'],['Aaron','Build installer']]))
  text=(self.workspace/item['path']).read_text('utf-8')
  self.assertIn('Launch checklist',text);self.assertIn('--- Table 1 ---',text);self.assertIn('Aaron | Build installer',text)
  self.assertTrue((self.workspace/item['original']).is_file())

 def test_long_documents_are_previewed_but_kept_whole(self):
  body=['Paragraph %d %s'%(i,'x'*200) for i in range(200)]+['END_SENTINEL']
  item=attachments.save('long.docx',docx(body))
  self.assertIn('END_SENTINEL',(self.workspace/item['path']).read_text('utf-8'))
  part=attachments.text_part(item['id'])['text']
  self.assertIn('Preview limited',part);self.assertNotIn('END_SENTINEL',part)

 def test_unreadable_documents_explain_what_to_do(self):
  locked=PdfWriter();locked.add_blank_page(612,792);locked.encrypt('secret');buffer=io.BytesIO();locked.write(buffer)
  blank=PdfWriter();blank.add_blank_page(612,792);scan=io.BytesIO();blank.write(scan)
  cases=[('locked.pdf',buffer.getvalue(),'password'),('scan.pdf',scan.getvalue(),'Scanned'),('fake.pdf',b'hello','not a PDF'),
         ('broken.pdf',b'%PDF-1.7 garbage','damaged'),('old.docx',b'\xd0\xcf\x11\xe0legacy','.docx'),('empty.docx',docx([]),'no text'),
         ('big.pdf',b'%PDF-'+b'0'*attachments.DOCUMENT_LIMIT,'25 MB')]
  for name,raw,message in cases:
   with self.subTest(name=name),self.assertRaises(ValueError) as caught:attachments.save(name,raw)
   self.assertIn(message,str(caught.exception))
  self.assertEqual(list((self.workspace).glob('Attachments/*')),[])

 def test_page_and_expansion_limits(self):
  with patch.object(attachments,'PAGE_LIMIT',1),self.assertRaises(ValueError) as caught:attachments.save('two.pdf',pdf('one','two'))
  self.assertIn('limited to 1 pages',str(caught.exception))
  with patch.object(attachments,'UNPACKED_LIMIT',1000),self.assertRaises(ValueError) as caught:attachments.save('bomb.docx',docx(['x'*5000]))
  self.assertIn('expands',str(caught.exception))

if __name__=='__main__':unittest.main()
