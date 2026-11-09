import importlib.util
import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

ROOT = Path(__file__).resolve().parents[1]

def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

module = load_module('extract_paper_assets')

class CaptionCompatibilityTests(unittest.TestCase):
    def test_legacy_caption_formats(self):
        # All legacy identifier families, punctuation, case and whitespace remain accepted.
        for kind, identifier, separator, space in itertools.product(
            ['Figure', 'Table', 'figure', 'TABLE'], ['1','01','12','A1','b12','1a','A12b'], [':','.'], [' ', '\t', '  ']
        ):
            text = f'{kind}{space}{identifier}{separator} Caption'
            with self.subTest(text=text):
                match = module.CAPTION_RE.match(text)
                self.assertIsNotNone(match)
                self.assertEqual(match[2].upper().replace('.', ''), identifier.upper())

    def test_new_caption_formats(self):
        for text, number in [('Figure 1 | Overview','1'),('Table B.1 | Sources','B1'),('Figure C.2: Caption','C2'),('Table D.11. Caption','D11'),('Table B1 | Caption','B1')]:
            with self.subTest(text=text):
                self.assertEqual(module.CAPTION_RE.match(text)[2].upper().replace('.', ''), number)

    def test_prose_is_not_a_caption(self):
        for text in ['See Figure 1.', 'Table 2 reports results.', 'Figure 2 shows the result.', 'Table B.2 lists the sources.', 'Figure I.1 presents the trajectory.']:
            with self.subTest(text=text):
                self.assertIsNone(module.CAPTION_RE.match(text))

    def test_existing_filenames_do_not_change(self):
        self.assertEqual(module.stem_for('figures', '1'), 'Figure_01')
        self.assertEqual(module.stem_for('tables', '12'), 'Table_12')
        self.assertEqual(module.stem_for('tables', 'A1'), 'Table_A1')
        self.assertEqual(module.stem_for('tables', 'B1'), 'Table_B1')

    def make_pdf(self, path):
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((30,30), 'Figure 1: Legacy caption')
        page.draw_rect(fitz.Rect(30,50,200,140),color=(0,0,0))
        page.insert_text((40,90),'Legacy content')
        page = pdf.new_page()
        page.insert_text((30,30), 'Table B.1 | New caption')
        page.draw_rect(fitz.Rect(30,50,200,140),color=(0,0,0))
        page.insert_text((40,90),'New content')
        pdf.save(path)
        pdf.close()

    def config(self):
        return {'slug':'compat-test','title':'Compatibility test','source_urls':['https://example.org/paper.pdf'], 'expected_pages':2,'output_dir':'Papers/Compatibility-Test','render_scale':2,'figures':[{'id':1,'page':1,'rect':[25,45,205,145]}],'tables':[{'id':'B1','page':2,'rect':[25,45,205,145]}]}

    def test_pdf_to_png_and_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.make_pdf(root/'source.pdf')
            with patch.object(module,'BASE_DIR',root):
                output, figures, tables = module.extract_one(self.config(),root/'source.pdf')
            self.assertEqual((figures,tables),(1,1))
            for relative in ['figures/Figure_01.png','tables/Table_B1.png']:
                pix = fitz.Pixmap(output/relative)
                self.assertEqual((pix.width,pix.height),(360,200))
                self.assertTrue((output/relative).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
            index = (output/'README.md').read_text()
            self.assertIn('/Papers/Compatibility-Test/figures/Figure_01.png',index)
            self.assertIn('/Papers/Compatibility-Test/tables/Table_B1.png',index)
            self.assertFalse(list(output.rglob('*.pdf')))

    def test_validation_still_rejects_missing_captions(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.pdf';self.make_pdf(path)
            with fitz.open(path) as pdf:
                config=self.config();config['tables']=[]
                with self.assertRaisesRegex(ValueError,'Coverage mismatch'):
                    module.validate_manifest(config,pdf)

    def test_validation_still_rejects_wrong_pages_and_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.pdf';self.make_pdf(path)
            with fitz.open(path) as pdf:
                config=self.config();config['expected_pages']=3
                with self.assertRaisesRegex(ValueError,'Source PDF mismatch'):module.validate_manifest(config,pdf)
                config=self.config();config['tables'][0]['page']=1
                with self.assertRaisesRegex(ValueError,'Caption mismatch'):module.validate_manifest(config,pdf)
                config=self.config();config['figures'][0]['rect']=[-1,0,200,145]
                with self.assertRaisesRegex(ValueError,'Invalid rectangle'):module.validate_manifest(config,pdf)

if __name__ == '__main__':
    unittest.main()
