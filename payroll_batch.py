"""Reproducible batch estimates and a portable collection of Persian payslips."""
import copy,re,os,tempfile,zipfile,json
from pathlib import Path
from datetime import datetime
from payroll import compute_payroll
from storage import parse_j,normalize

def validate_batch(payload):
    p=copy.deepcopy(payload);period=normalize(p.get('period',''));parse_j(period+'/01');slips=p.get('slips',[])
    if not isinstance(slips,list) or not 1<=len(slips)<=200:raise ValueError('دوره حقوق باید ۱ تا ۲۰۰ فیش داشته باشد.')
    codes=set();results=[]
    for slip in slips:
        if not isinstance(slip,dict) or not slip.get('name','').strip() or not slip.get('code','').strip():raise ValueError('نام و کد هر فرد لازم است.')
        if slip['code'] in codes:raise ValueError('کد پرسنلی در دوره تکراری است.')
        if slip.get('unit','ریال')!='ریال':raise ValueError('دوره حقوق گروهی با واحد ریال ثبت می‌شود.')
        codes.add(slip['code']);slip['period']=period;results.append({k:str(v) for k,v in compute_payroll(slip).items()})
    p.update(period=period,results=results,total_net=str(sum(int(r['net']) for r in results)),prepared_at=datetime.now().isoformat());return p

def previous_month(month):
    d=parse_j(normalize(month)+'/01');y,m=(d.year-1,12) if d.month==1 else (d.year,d.month-1);return f'{y:04d}/{m:02d}'

def compare(slips,previous):
    lookup={str(p['code']):compute_payroll(p)['net'] for p in previous};return [str(compute_payroll(p)['net']-lookup[str(p['code'])]) if str(p['code']) in lookup else None for p in slips]

def export_collection(target,payload):
    from payroll_ui import payroll_pdf
    from pypdf import PdfWriter
    p=validate_batch(payload);target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temp:
        temp=Path(temp);paths=[];writer=PdfWriter()
        for i,slip in enumerate(p['slips']):
            code=re.sub(r'[^A-Za-z0-9_-]','_',slip['code'])[:60] or str(i+1);path=temp/f'{i+1:03d}-{code}.pdf';payroll_pdf(path,slip,compute_payroll(slip));writer.append(path);paths.append(path)
        merged=temp/'Karname-All-Payslips.pdf'
        with merged.open('wb') as f:writer.write(f)
        writer.close();manifest=temp/'calculations.json';manifest.write_text(json.dumps(p,ensure_ascii=False,indent=2),'utf-8');archive=temp/'collection.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for file in paths+[merged,manifest]:z.write(file,file.name)
        with zipfile.ZipFile(archive) as z:
            if z.testzip():raise ValueError('صحت مجموعه تأیید نشد.')
        os.replace(archive,target)
    return str(target)
