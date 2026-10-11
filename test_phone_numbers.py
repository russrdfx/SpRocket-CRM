import unittest
import phone_numbers as p
import record_forms

class PhoneTests(unittest.TestCase):
    def test_international_and_extensions(self):
        cases=[('2025550123','US','+1 202-555-0123'),('4165550123','CA','+1 416-555-0123'),('02079460018','GB','+44 20 7946 0018'),('0412345678','AU','+61 412 345 678')]
        for raw,region,expected in cases:
            with self.subTest(region=region):
                result=p.format_phone(raw,region)
                self.assertEqual(result['value'],expected)
                self.assertEqual(p.format_phone(expected,region)['value'],expected)
        result=p.format_phone('2025550123 ext. 123','US')
        self.assertEqual(result['extension'],'123')
        self.assertEqual(result['e164'],'+12025550123')
        self.assertIn('123',result['value'])
        self.assertEqual(p.format_phone('+44 20 7946 0018','US')['country'],'GB')
    def test_preserve_ambiguous_and_incomplete(self):
        for value in ['555-0100','123','Call 2025550123','2025550123 / 4165550123','1-800-FLOWERS','']:
            self.assertEqual(p.format_phone(value)['value'],value)
    def test_validation_and_typing(self):
        for value in ['2025550123\n','x'*81]:
            with self.assertRaises(ValueError):p.format_phone(value)
        with self.assertRaises(ValueError):p.country('BAD')
        formatted=p.format_phone('202555','US',True)['value']
        self.assertEqual(''.join(c for c in formatted if c.isdigit()),'202555')
        self.assertTrue({'CA','GB','US'}.issubset({r['country'] for r in p.countries()}))
    def test_fields_and_additive_migration(self):
        body={'phone':'02079460018','phone_country':'GB','mobile_number':'123'}
        p.normalize_fields(body,['phone','mobile_number'],'CA')
        self.assertEqual(body['phone'],'+44 20 7946 0018')
        self.assertEqual(body['mobile_number'],'123')
        self.assertEqual(body['mobile_number_country'],'CA')
        settings={'creation_schema_version':2,'types':[{'id':'companies','fields':[{'key':'custom','label':'Custom','type':'text'}]}]}
        record_forms.upgrade(settings)
        self.assertTrue(any(f['key']=='phone' for f in settings['types'][0]['fields']))
        self.assertTrue(any(f['key']=='custom' for f in settings['types'][0]['fields']))
