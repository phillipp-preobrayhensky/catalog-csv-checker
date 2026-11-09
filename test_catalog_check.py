import tempfile
import unittest
from pathlib import Path
from catalog_check import price, run, safe_cell, validate

class CatalogTests(unittest.TestCase):
    def fixture(self, body):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        p = Path(t.name) / 'input.csv'
        p.write_text('id;name;price_rub;category\n' + body, encoding='utf-8-sig')
        return p

    def test_price_russian_and_zero(self):
        self.assertEqual(price('1 234,50'), '1234.50')
        self.assertEqual(price('0'), '0.00')

    def test_invalid_money(self):
        for v in ['-1','NaN','Infinity','1.234','','1e3','1,2,3']:
            with self.subTest(v=v), self.assertRaises(ValueError): price(v)

    def test_every_duplicate_rejected(self):
        p=self.fixture('a;One;10;Cat\na;Two;20;Cat\nb;Three;30;Cat\n')
        good,bad,r=validate(p)
        self.assertEqual([x['id'] for x in good],['b'])
        self.assertEqual(r,{'read':3,'accepted':1,'rejected':2})

    def test_no_silent_column_loss(self):
        p=self.fixture('a;One;10;Cat;extra\nb;Two;20\n')
        self.assertEqual(validate(p)[2]['rejected'],2)

    def test_required_fields(self):
        p=self.fixture('a;;10;Cat\nb;Two;20;\n')
        self.assertEqual(validate(p)[2]['rejected'],2)

    def test_neutralize_formula(self):
        for v in ['=1+1','  @SUM(1)','+2','-2']:
            self.assertTrue(safe_cell(v).startswith("'"))

    def test_source_unchanged_and_no_overwrite(self):
        p=self.fixture('001;  White   mug ;250,50; Cups \n');before=p.read_bytes()
        out=p.parent/'result';r=run(p,out)
        self.assertEqual(p.read_bytes(),before)
        self.assertEqual(r['accepted'],1)
        self.assertIn('001;White mug;250.50;Cups',(out/'clean.csv').read_text(encoding='utf-8-sig'))
        with self.assertRaises(FileExistsError): run(p,out)

    def test_header_rejected(self):
        p=self.fixture('');p.write_text('name;price\nA;1')
        with self.assertRaises(ValueError):validate(p)

    def test_empty_file_with_headers(self):
        self.assertEqual(validate(self.fixture(''))[2]['read'],0)

if __name__=='__main__':unittest.main()
