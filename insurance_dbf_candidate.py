"""Experimental schema-driven DBF bytes; never an approved filing export.

The caller must supply a reference and an explicit encoding. No field mapping,
encoding, or acceptance status is inferred. This is not wired to production UI.
"""
from decimal import Decimal,InvalidOperation
from pathlib import Path
import struct
from insurance_dbf_reference import inspect_schema

def build_candidate(reference,rows,encoding,*,text_encoder=None,text_decoder=None,field_codecs=None):
    schema=inspect_schema(reference)
    if schema.version!=3:raise ValueError('این نوع DBF هنوز پشتیبانی آزمایشی ندارد.')
    if not isinstance(encoding,str) or not encoding.strip():raise ValueError('کدگذاری باید صریحاً تعیین شود.')
    if (text_encoder is None)!=(text_decoder is None) or (text_encoder is not None and (not callable(text_encoder) or not callable(text_decoder))):raise ValueError('تبدیل متن باید همراه رمزگشای قابل بررسی ارائه شود.')
    if field_codecs is None:field_codecs={}
    if not isinstance(field_codecs,dict):raise ValueError('کدگذاری ستون‌ها معتبر نیست.')
    char_names={f.name for f in schema.fields if f.kind=='C'}
    if set(field_codecs)-char_names:raise ValueError('کدگذاری برای ستون متنی ناشناخته تعیین شده است.')
    for pair in field_codecs.values():
        if not isinstance(pair,tuple) or len(pair)!=2 or not all(callable(fn) for fn in pair):raise ValueError('کدگذاری هر ستون به رمزگذار و رمزگشای قابل بررسی نیاز دارد.')
    if not isinstance(rows,list) or len(rows)>100000:raise ValueError('تعداد ردیف‌های آزمایشی معتبر نیست.')
    if any(f.kind not in ('C','N','D','L') for f in schema.fields):raise ValueError('نوع یکی از ستون‌ها نیازمند بررسی جداگانه است.')
    with Path(reference).open('rb') as stream:header=bytearray(stream.read(schema.header_length))
    if len(header)!=schema.header_length:raise ValueError('سرآیند مرجع ناقص است.')
    struct.pack_into('<I',header,4,len(rows));output=bytearray(header);names={f.name for f in schema.fields}
    for row in rows:
        if not isinstance(row,dict) or set(row)!=names:raise ValueError('نام و تعداد ستون‌های ردیف باید دقیقاً مطابق مرجع باشد.')
        record=bytearray(b' ')
        for f in schema.fields:
            value=row[f.name]
            if f.kind=='C':
                if not isinstance(value,str) or any(ord(ch)<32 for ch in value):raise ValueError('متن ستون '+f.name+' معتبر نیست.')
                try:
                    encoder,decoder=field_codecs.get(f.name,(text_encoder,text_decoder))
                    raw=encoder(value) if encoder else value.encode(encoding,'strict')
                    if not isinstance(raw,bytes):raise ValueError('خروجی کدگذاری معتبر نیست.')
                    decoded=decoder(raw) if decoder else raw.decode(encoding,'strict')
                    if decoded!=value:raise ValueError('متن ستون '+f.name+' بدون اتلاف قابل تبدیل نیست.')
                except (LookupError,UnicodeError) as exc:raise ValueError('کدگذاری ستون '+f.name+' معتبر نیست.') from exc
                if len(raw)>f.length:raise ValueError('طول متن ستون '+f.name+' بیشتر از ظرفیت است.')
                record.extend(raw.ljust(f.length,b' '))
            elif f.kind=='N':
                if isinstance(value,(float,bool)) or not isinstance(value,(str,int,Decimal)):raise ValueError('مقدار عددی ستون '+f.name+' معتبر نیست.')
                try:number=Decimal(value)
                except (InvalidOperation,ValueError):raise ValueError('مقدار عددی ستون '+f.name+' معتبر نیست.')
                if not number.is_finite() or number.as_tuple().exponent < -f.decimals:raise ValueError('دقت ستون '+f.name+' بیش از ظرفیت است.')
                raw=format(number,f'.{f.decimals}f').encode('ascii')
                if len(raw)>f.length:raise ValueError('عدد ستون '+f.name+' بیش از ظرفیت است.')
                record.extend(raw.rjust(f.length,b' '))
            elif f.kind=='D':
                if f.length!=8 or not isinstance(value,str) or (value and (len(value)!=8 or not value.isascii() or not value.isdigit())):raise ValueError('تاریخ ستون '+f.name+' معتبر نیست.')
                record.extend((value or ' '*8).encode('ascii'))
            else:
                if f.length!=1 or not (value is None or type(value) is bool):raise ValueError('مقدار منطقی ستون '+f.name+' معتبر نیست.')
                record.extend(b'T' if value is True else b'F' if value is False else b'?')
        if len(record)!=schema.record_length:raise ValueError('طول ردیف با مرجع هم‌خوانی ندارد.')
        output.extend(record)
    output.extend(b'\x1a');return bytes(output)
