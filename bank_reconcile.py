"""Read-only suggestions for matching imported bank rows to financial documents."""
import csv
from pathlib import Path
from settlement_logic import amount
from storage import normalize,parse_j,jformat


def read_table(path):
    path=Path(path)
    if path.stat().st_size>10*1024*1024:raise ValueError('حجم فایل نباید بیشتر از ۱۰ مگابایت باشد.')
    if path.suffix.lower()=='.xlsx':
        from openpyxl import load_workbook
        wb=load_workbook(path,read_only=True,data_only=True)
        try:data=list(wb.active.iter_rows(max_row=10002,values_only=True))
        finally:wb.close()
    elif path.suffix.lower()=='.csv':
        raw=path.read_bytes()
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:text=raw.decode('cp1256')
        data=list(csv.reader(text.splitlines()))
    else:raise ValueError('فایل CSV یا XLSX را انتخاب کنید.')
    if len(data)>10001:raise ValueError('حداکثر ۱۰ هزار ردیف قابل بررسی است.')
    if not data:raise ValueError('فایل خالی است.')
    return data

def read_rows(path, columns=None):
    data=read_table(path)
    headers=[normalize(str(v or '')).strip().lower() for v in data[0]]
    columns=columns or {}
    def index(key,*names):
        if key in columns:
            value=columns[key]
            if value is None:return None
            if not isinstance(value,int) or not 0<=value<len(headers):raise ValueError('انتخاب ستون معتبر نیست.')
            return value
        return next((headers.index(n) for n in names if n in headers),None)
    di=index('date','تاریخ','تاریخ تراکنش','تاریخ عملیات','date');vi=index('amount','مبلغ','مبلغ تراکنش','amount');ti=index('direction','نوع','نوع تراکنش','direction');ri=index('description','شرح','توضیحات','description');refi=index('reference','شناسه تراکنش','شماره پیگیری','شماره ارجاع','reference');inci=index('income','واریز','بستانکار','دریافت','credit');expi=index('expense','برداشت','بدهکار','پرداخت','debit')
    if di is None or not (vi is not None and ti is not None or inci is not None and expi is not None):raise ValueError('ستون تاریخ و ستون‌های مبلغ و نوع، یا ستون‌های جداگانه واریز و برداشت لازم است.')
    result=[]
    for number,row in enumerate(data[1:],2):
        if not any(v is not None and str(v).strip() for v in row):continue
        try:
            def val(i):return str(row[i] if i is not None and i<len(row) and row[i] is not None else '').strip()
            d=normalize(jformat(parse_j(normalize(val(di)))))
            if inci is not None and expi is not None and (vi is None or ti is None):
                incoming=amount(normalize(val(inci) or '0').replace(',','').replace('٬',''));outgoing=amount(normalize(val(expi) or '0').replace(',','').replace('٬',''))
                if (incoming>0)==(outgoing>0):raise ValueError()
                direction='income' if incoming>0 else 'expense';v=str(incoming if incoming>0 else outgoing)
            else:
                v=str(amount(normalize(val(vi)).replace(',','').replace('٬','')));kind=normalize(val(ti)).lower()
                direction={'دریافت':'income','واریز':'income','بستانکار':'income','credit':'income','income':'income','پرداخت':'expense','برداشت':'expense','بدهکار':'expense','debit':'expense','expense':'expense'}.get(kind)
            if not direction or int(v)<=0:raise ValueError()
            reference=normalize(val(refi));
            if len(reference)>150:raise ValueError()
            result.append(dict(date=d,amount=v,direction=direction,description=val(ri)[:500],reference=reference,row=number))
        except (ValueError,TypeError):raise ValueError('تاریخ، مبلغ یا نوع در ردیف '+str(number)+' معتبر نیست.') from None
    return result


def suggestions(rows,transactions,bank_id):
    result=[];index={}
    for t in transactions:
        if t.get('source') not in (None,'transaction') or t.get('bank_id')!=bank_id:continue
        try:d=normalize(jformat(parse_j(t.get('date',''))))
        except ValueError:continue
        key=(d,t.get('direction'),amount(t['amount']))
        index.setdefault(key,[]).append({'document_no':t['document_no'],'id':t['id']})
    for row in rows:
        result.append(dict(row,matches=index.get((row['date'],row['direction'],amount(row['amount'])),[])))
    return result
