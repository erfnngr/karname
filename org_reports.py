"""Portable reports; amounts are estimates, not a statutory payroll engine."""
import json,html
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from org_schema import SCHEMAS,STATUSES

def flat_rows(records):
    result=[]
    for r in records:
        p=r['payload'];result.append({'شناسه':r['id'],'شرکت':r.get('company_id') or 'شخصی','نوع':SCHEMAS.get(r['kind'],{}).get('label',{'task':'کار','notice':'اطلاعیه','document':'سند'}.get(r['kind'],r['kind'])),'عنوان':p.get('title',''),'موعد':p.get('due_date',p.get('date',p.get('start_date',''))),'وضعیت':STATUSES.get(p.get('status'),p.get('status','')),'نسخه':r['version'],'اطلاعات':json.dumps(p,ensure_ascii=False)})
    return result
def spreadsheet(path,rows,title='گزارش کارنامه'):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.utils import get_column_letter
    book=Workbook();sheet=book.active;sheet.title='گزارش';sheet.sheet_view.rightToLeft=True
    headers=list(rows[0]) if rows else ['پیام'];sheet.append(headers)
    for row in rows:
        values=[]
        for h in headers:
            value=row.get(h,'');value=str(value) if not isinstance(value,(int,float,Decimal)) else float(value) if isinstance(value,Decimal) else value
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):value="'"+value
            values.append(value)
        sheet.append(values)
    for cell in sheet[1]:cell.font=Font(name='Tahoma',bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='153D50')
    sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
    for i,h in enumerate(headers,1):sheet.column_dimensions[get_column_letter(i)].width=min(65,max(18,len(h)*2))
    for row in sheet.iter_rows(min_row=2):
        for cell in row:cell.font=Font(name='Tahoma',size=11);cell.alignment=Alignment(vertical='top',wrap_text=True)
    book.save(path)
def pdf_report(path,rows,title='گزارش کارنامه'):
    from PySide6.QtGui import QTextDocument,QFont,QPageSize,QPageLayout
    from PySide6.QtCore import QMarginsF
    from PySide6.QtPrintSupport import QPrinter
    columns=list(rows[0]) if rows else ['پیام'];columns=[c for c in columns if c!='اطلاعات']
    esc=lambda x:html.escape(str(x))
    body=''.join('<tr>'+''.join('<td>'+esc(row.get(col,''))+'</td>' for col in columns)+'</tr>' for row in rows)
    doc=QTextDocument();doc.setDefaultFont(QFont('Vazirmatn',10));doc.setHtml('<html dir="rtl"><style>table{border-collapse:collapse;width:100%;}td,th{border:1px solid #bdcbd4;padding:5px;}th{background:#dcebf2;}h1{color:#153d50;}</style><h1>'+esc(title)+'</h1><p>'+datetime.now().strftime('%Y-%m-%d %H:%M')+'</p><table><thead><tr>'+''.join('<th>'+esc(c)+'</th>' for c in columns)+'</tr></thead><tbody>'+body+'</tbody></table></html>')
    printer=QPrinter(QPrinter.HighResolution);printer.setOutputFormat(QPrinter.PdfFormat);printer.setOutputFileName(str(path));printer.setPageSize(QPageSize(QPageSize.A4));printer.setPageOrientation(QPageLayout.Landscape);printer.setPageMargins(QMarginsF(10,10,10,10));doc.print_(printer)
