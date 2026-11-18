"""Inspect DBF structure without printing or exporting employee records.

This reads the physical schema only. It does not infer Persian encoding or
claim compatibility with the Social Security Organization's acceptance system.
"""
from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    length: int
    decimals: int


@dataclass(frozen=True)
class Schema:
    version: int
    code_page: int
    header_length: int
    record_length: int
    record_count: int
    fields: tuple[Field, ...]


def inspect_schema(path, *, max_bytes=256 * 1024 * 1024):
    path = Path(path)
    size = path.stat().st_size
    if size < 33 or size > max_bytes:
        raise ValueError('اندازه فایل DBF معتبر نیست.')
    with path.open('rb') as stream:
        header = stream.read(32)
        count = struct.unpack_from('<I', header, 4)[0]
        header_length, record_length = struct.unpack_from('<HH', header, 8)
        if header_length < 33 or header_length > size or record_length < 2:
            raise ValueError('سرآیند یا طول رکورد DBF معتبر نیست.')
        if header_length + count * record_length > size:
            raise ValueError('تعداد یا طول رکوردها با اندازه فایل سازگار نیست.')
        fields = []
        while stream.tell() < header_length:
            first = stream.read(1)
            if first == b'\r':
                break
            descriptor = first + stream.read(31)
            if len(descriptor) != 32 or stream.tell() >= header_length:
                raise ValueError('توصیف ستون‌های DBF ناقص است.')
            try:
                name = descriptor[:11].split(b'\0', 1)[0].decode('ascii')
                kind = chr(descriptor[11])
            except (UnicodeDecodeError, ValueError) as exc:
                raise ValueError('نام یا نوع ستون معتبر نیست.') from exc
            length, decimals = descriptor[16], descriptor[17]
            if not name or not 1 <= length <= 255 or decimals > length or not 32 <= ord(kind) <= 126:
                raise ValueError('مشخصات ستون DBF معتبر نیست.')
            if any(field.name.casefold() == name.casefold() for field in fields):
                raise ValueError('نام ستون DBF تکراری است.')
            fields.append(Field(name, kind, length, decimals))
        else:
            raise ValueError('پایان فهرست ستون‌های DBF پیدا نشد.')
        if not fields or sum(field.length for field in fields) + 1 != record_length:
            raise ValueError('طول ستون‌ها با طول رکورد برابر نیست.')
        return Schema(header[0], header[29], header_length, record_length, count, tuple(fields))


def compare_schemas(reference: Schema, candidate: Schema):
    """Return structural differences, without exposing data in either file."""
    differences = []
    for name, label in (('version', 'نوع DBF'), ('code_page', 'شناسه صفحه کد'),
                        ('header_length', 'طول سرآیند'), ('record_length', 'طول رکورد')):
        expected, actual = getattr(reference, name), getattr(candidate, name)
        if expected != actual:
            differences.append(f'{label}: مقدار مرجع {expected}، مقدار فایل {actual}')
    for index in range(max(len(reference.fields), len(candidate.fields))):
        expected = reference.fields[index] if index < len(reference.fields) else None
        actual = candidate.fields[index] if index < len(candidate.fields) else None
        if expected != actual:
            def describe(field):
                return 'وجود ندارد' if field is None else f'{field.name} ({field.kind}, {field.length}, {field.decimals})'
            differences.append(f'ستون {index+1}: مرجع {describe(expected)}، فایل {describe(actual)}')
    return differences

def field_evolution(reference: Schema, candidate: Schema):
    """Compare named fields without treating appended columns as shifted fields."""
    before={f.name:f for f in reference.fields};after={f.name:f for f in candidate.fields}
    added=[f.name for f in candidate.fields if f.name not in before]
    removed=[f.name for f in reference.fields if f.name not in after]
    changed=[name for name in before if name in after and before[name]!=after[name]]
    old_order=[f.name for f in reference.fields if f.name in after]
    new_order=[f.name for f in candidate.fields if f.name in before]
    return {'added':added,'removed':removed,'changed':changed,'common_order_equal':old_order==new_order,
            'code_page_equal':reference.code_page==candidate.code_page,'version_equal':reference.version==candidate.version}

def encoding_statistics(path, encodings=('utf-8','cp1256'), *, max_records=10000):
    """Return aggregate decode counts only; never return any record content.

    A successful decode is not evidence of the correct Persian encoding.
    """
    schema=inspect_schema(path)
    if schema.record_count>max_records:raise ValueError('تعداد رکوردها برای بررسی نمونه بیش از حد مجاز است.')
    counts={encoding:{'non_ascii':0,'decodable':0} for encoding in encodings}
    with Path(path).open('rb') as stream:
        stream.seek(schema.header_length)
        for _ in range(schema.record_count):
            record=stream.read(schema.record_length)
            if len(record)!=schema.record_length:raise ValueError('رکورد ناقص است.')
            if record[:1]!=b' ':continue
            offset=1
            for field in schema.fields:
                raw=record[offset:offset+field.length].rstrip(b' \x00');offset+=field.length
                if field.kind!='C' or not any(byte>=128 for byte in raw):continue
                for encoding in encodings:
                    counts[encoding]['non_ascii']+=1
                    try:raw.decode(encoding,'strict');counts[encoding]['decodable']+=1
                    except (UnicodeError,LookupError):pass
    return counts

def assess_reference_pair(workshop,employees):
    """Flag known gaps; a clean result is not proof of official compatibility."""
    w={f.name.upper() for f in workshop.fields};e={f.name.upper() for f in employees.fields};issues=[]
    if 'DSK_ID' not in w or 'DSW_ID' not in e:issues.append('فایل‌ها نشانه‌های اصلی کارگاه و کارکنان را ندارند؛ ترتیب فایل‌ها را بررسی کنید.')
    if 'DSK_INC' not in w:issues.append('ستون جداگانه پایه سنوات کارگاه در نمونه وجود ندارد.')
    if not {'DSK_SPOUSE','DSK_SPOUS'} & w:issues.append('ستون جداگانه حق تأهل کارگاه در نمونه وجود ندارد.')
    if 'DSW_INC' not in e:issues.append('ستون جداگانه پایه سنوات کارکنان در نمونه وجود ندارد.')
    if 'DSW_SPOUSE' not in e:issues.append('ستون جداگانه حق تأهل کارکنان در نمونه وجود ندارد.')
    if workshop.code_page!=employees.code_page:issues.append('شناسه صفحه کد در دو سرآیند متفاوت است؛ کدگذاری باید جداگانه بررسی شود.')
    return issues

def roundtrip_statistics(path,decode,encode,*,max_records=10000):
    """Compare non-ASCII field bytes in aggregate without returning field values."""
    schema=inspect_schema(path)
    if schema.record_count>max_records:raise ValueError('تعداد رکوردها برای بررسی نمونه بیش از حد مجاز است.')
    fields={}
    with Path(path).open('rb') as stream:
        stream.seek(schema.header_length)
        for _ in range(schema.record_count):
            record=stream.read(schema.record_length)
            if len(record)!=schema.record_length:raise ValueError('رکورد ناقص است.')
            if record[:1]!=b' ':continue
            offset=1
            for field in schema.fields:
                raw=record[offset:offset+field.length].rstrip(b' \x00');offset+=field.length
                if field.kind!='C' or not any(byte>=128 for byte in raw):continue
                stat=fields.setdefault(field.name,{'total':0,'exact':0,'errors':0});stat['total']+=1
                try:
                    text=decode(raw);encoded=encode(text.strip())
                    if encoded==raw:stat['exact']+=1
                except Exception:stat['errors']+=1
    return fields
