import struct
import tempfile
import unittest
from pathlib import Path
from insurance_dbf_reference import inspect_schema, compare_schemas
from dataclasses import replace


class DBFReferenceTests(unittest.TestCase):
    def test_schema_is_read_without_returning_record_data(self):
        header=bytearray(32);header[0]=3;header[29]=0x7e
        struct.pack_into('<IHH',header,4,1,65,11)
        field=bytearray(32);field[:4]=b'CODE';field[11]=ord('C');field[16]=10
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.dbf';path.write_bytes(header+field+b'\r'+b' '+b'0123456789'+b'\x1a')
            schema=inspect_schema(path)
            self.assertEqual((schema.version,schema.code_page,schema.record_count),(3,0x7e,1))
            self.assertEqual((schema.fields[0].name,schema.fields[0].kind,schema.fields[0].length),('CODE','C',10))
            self.assertNotIn('0123456789',repr(schema))
            self.assertEqual(compare_schemas(schema,replace(schema,record_count=9)),[])
            changed=replace(schema,fields=(replace(schema.fields[0],length=9),))
            self.assertIn('ستون 1',compare_schemas(schema,changed)[0])
            path.write_bytes((header+field+b'\r')[:-1])
            with self.assertRaises(ValueError):inspect_schema(path)
