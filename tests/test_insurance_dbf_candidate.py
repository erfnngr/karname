import struct,tempfile,unittest
from pathlib import Path
from insurance_dbf_candidate import build_candidate
from insurance_dbf_reference import inspect_schema,compare_schemas

class CandidateTests(unittest.TestCase):
    def test_explicit_encoding_roundtrip_and_overflow(self):
        header=bytearray(32);header[0]=3;struct.pack_into('<IHH',header,4,0,65,11)
        field=bytearray(32);field[:4]=b'CODE';field[11]=ord('C');field[16]=10
        with tempfile.TemporaryDirectory() as folder:
            ref=Path(folder)/'ref.dbf';ref.write_bytes(header+field+b'\r'+b'\x1a')
            data=build_candidate(ref,[{'CODE':'00123'}],'ascii');out=Path(folder)/'out.dbf';out.write_bytes(data)
            self.assertEqual(compare_schemas(inspect_schema(ref),inspect_schema(out)),[])
            self.assertEqual(data[65:76],b' 00123     ');self.assertEqual(data,build_candidate(ref,[{'CODE':'00123'}],'ascii'))
            with self.assertRaises(ValueError):build_candidate(ref,[{'CODE':'X'*11}],'ascii')
            with self.assertRaises(ValueError):build_candidate(ref,[{'CODE':'فارسی'}],'ascii')
            with self.assertRaises(ValueError):build_candidate(ref,[{'CODE':'test'}],'explicit',text_encoder=lambda _:b'?',text_decoder=lambda _: '?')
            custom=build_candidate(ref,[{'CODE':'abc'}],'ascii',field_codecs={'CODE':(lambda s:s.encode('ascii')[::-1],lambda b:b[::-1].decode('ascii'))})
            self.assertEqual(custom[66:69],b'cba')
            with self.assertRaises(ValueError):build_candidate(ref,[{'CODE':'abc'}],'ascii',field_codecs={'UNKNOWN':(lambda s:b'',lambda b:'')})
            with self.assertRaises(ValueError):build_candidate(ref,[{'OTHER':'x'}],'ascii')
