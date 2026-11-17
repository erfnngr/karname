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
