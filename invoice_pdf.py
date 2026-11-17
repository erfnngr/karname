"""Native Qt PDF printing shares the app's embedded Persian font and shaping."""
import html
from decimal import Decimal
from PySide6.QtCore import QMarginsF,QSizeF,QRectF
from PySide6.QtGui import QPdfWriter,QPageSize,QPageLayout,QFont,QTextDocument,QPainter,QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel
from customer_data import invoice
from storage import fa,package_file

def with_allocated_payments(payload,allocated,pending_checks='0'):
    """Prepare a print-only snapshot without altering the stored settlement."""
    import copy
    p=copy.deepcopy(payload);summary=p.get('settlement_summary')
    if isinstance(summary,dict):
        value=Decimal(str(allocated or 0));pending=Decimal(str(pending_checks or 0));summary['received']=str(Decimal(str(summary.get('received','0')))+value);summary['uncollected']=str(Decimal(str(summary.get('uncollected','0')))-value);summary['pending_checks']=str(Decimal(str(summary.get('pending_checks','0')))+pending)
    return p

def document(payload):
    p=invoice(payload);buyer=p.get('customer_snapshot',{});seller=p.get('seller_snapshot',{});esc=lambda value:html.escape(str(value or ''));money=lambda value:fa(f'{Decimal(str(value)):,.0f}');status=dict(draft='پیش‌نویس',issued='ثبت‌شده',paid='تسویه‌شده',cancelled='لغوشده').get(p.get('status'),'')
    rows=''.join('<tr>'+''.join('<td align="right">'+value+'</td>' for value in reversed([fa(i+1),esc(line['description']),fa(line['quantity']),esc(line['unit']),money(line['unit_price']),money(Decimal(line['discount'])+Decimal(line.get('invoice_discount_share','0'))),fa(line['tax_rate']),money(line['tax']),money(line['total'])]))+'</tr>' for i,line in enumerate(p['lines']))
    buyer_name=buyer.get('legal_name') or ' '.join(filter(None,[buyer.get('first_name'),buyer.get('last_name')])) or buyer.get('title','')
    pairs=[('نام خریدار',buyer_name),('شماره / شناسه ملی',buyer.get('national_id')),('شماره اقتصادی',buyer.get('economic_code')),('شماره ثبت',buyer.get('registration_no')),('کد پستی',buyer.get('postal_code')),('کد شعبه',buyer.get('tax_branch')),('تلفن',buyer.get('phone')),('همراه',buyer.get('mobile'))]
    buyer_rows=''
    for i in range(0,len(pairs),2):
        first,second=pairs[i:i+2];buyer_rows+='<tr>'+''.join('<td align="right" width="32%">'+esc(value)+'</td><td class="key" width="18%" align="right">'+label+'</td>' for label,value in [second,first])+'</tr>'
    buyer_rows+='<tr><td colspan="3" align="right">'+esc(buyer.get('address'))+'</td><td class="key" align="right">نشانی</td></tr>'
    sums=''.join('<tr'+(' bgcolor="#E6F1F3"' if key=='total' else '')+'><td width="50%" align="right">'+money(p['totals'][key])+'</td><td width="50%" align="right">'+label+'</td></tr>' for key,label in [('subtotal','جمع قبل از تخفیف'),('discount','تخفیف'),('tax','مالیات و عوارض'),('total','قابل پرداخت؛ ریال')])
    headers=[('ردیف',7),('شرح کالا / خدمت',23),('تعداد',6),('واحد',7),('مبلغ واحد',13),('تخفیف',11),('نرخ ٪',8),('مالیات',12),('جمع',13)];header=''.join('<th width="'+str(width)+'%" align="right">'+title+'</th>' for title,width in reversed(headers))
    contact='<p class="muted" align="right">'+esc(seller.get('phone',''))+' &nbsp; '+esc(seller.get('address',''))+'</p>' if seller.get('phone') or seller.get('address') else ''
    notes=esc(p.get('notes','')).replace(chr(10),'<br>');due='سررسید پرداخت: '+fa(p['due_date']) if p.get('due_date') else ''
    return f'''<html><head><meta charset="utf-8"><style>body{{font-family:Vazirmatn,Tahoma;color:#193649;font-size:10pt;}}h1{{font-size:20pt;color:#075E68;margin:2px 0;}}h2{{font-size:12pt;color:#075E68;margin:12px 0 5px;}}table{{border-collapse:collapse;}}td,th{{padding:6px;border:1px solid #D5E1E8;}}th{{background:#E6F1F3;color:#173A4C;}}.head td{{border:0;}}.key{{background:#F1F6F8;}}p{{margin:6px 0;}}.muted{{color:#587080;font-size:9pt;}}</style></head><body><table width="100%" class="head"><tr><td width="18%" align="left"><img width="52" height="52" src="{package_file('assets/karname.png').as_uri()}"></td><td width="82%" align="right"><h1>{esc(p['document_type'])}</h1><p>{esc(p.get('seller_name',''))}</p></td></tr></table><p align="right">شماره داخلی: {esc(p['number'])} &nbsp; | &nbsp; تاریخ: {fa(p['date'])} &nbsp; | &nbsp; وضعیت: {status}</p>{contact}<h2 align="right">مشخصات خریدار</h2><table width="100%">{buyer_rows}</table><h2 align="right">کالاها و خدمات</h2><table width="100%"><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table><p class="muted" align="right">واحد تمام مبالغ: ریال</p><table width="100%" class="head"><tr><td width="45%"><table width="100%">{sums}</table></td><td width="55%" align="right"><p>{due}</p><p>{notes}</p></td></tr></table><br><br><table width="100%" class="head"><tr><td width="50%" align="left">تأیید خریدار</td><td width="50%" align="right">مهر و امضای فروشنده</td></tr></table></body></html>'''

def sample_document(payload,options=None):
    """Printable invoice arranged like the user's supplied workbook."""
    p=invoice(payload); buyer=p.get('customer_snapshot',{}); seller=p.get('seller_snapshot',{});options=options if isinstance(options,dict) else {}
    esc=lambda v:html.escape(str(v or ''))
    money=lambda v:fa(f'{Decimal(str(v or 0)):,.0f}')
    def party(title,data,name):
        address=' '.join(filter(None,[data.get('province',''),data.get('city',''),data.get('address','')]))
        return ('<tr><th colspan="4">مشخصات '+title+'</th></tr>'
          '<tr><td colspan="2">نام شخص حقیقی / حقوقی: '+esc(name)+'</td><td>شماره اقتصادی: '+esc(data.get('economic_code'))+'</td><td>شماره ثبت: '+esc(data.get('registration_no'))+'</td></tr>'
          '<tr><td colspan="2">نشانی کامل: '+esc(address)+'</td><td>کد پستی ده رقمی: '+esc(data.get('postal_code'))+'</td><td>شناسه ملی: '+esc(data.get('national_id'))+'</td></tr>'
          '<tr><td colspan="3">نشانی: '+esc(data.get('address'))+'</td><td>تلفن / فکس: '+esc(data.get('phone'))+'</td></tr>')
    headings=['ردیف','کد کالا','شرح کالا یا خدمات','تعداد / مقدار','واحد اندازه‌گیری','مبلغ واحد (ریال)','مبلغ کل (ریال)','مبلغ تخفیف (ریال)','مبلغ کل پس از تخفیف (ریال)','مالیات و ارزش افزوده (ریال)','جمع مبلغ کل به‌علاوه مالیات (ریال)']
    def cells(values,tag='td'):
        return '<tr>'+''.join('<'+tag+'>'+str(x)+'</'+tag+'>' for x in reversed(values))+'</tr>'
    lines=[]
    for i,line in enumerate(p['lines']):
        discount=Decimal(line['discount'])+Decimal(line.get('invoice_discount_share','0'))
        lines.append(cells([fa(i+1),esc(line.get('product_code','')),esc(line['description']),fa(line['quantity']),esc(line['unit']),money(line['unit_price']),money(line['subtotal']),money(discount),money(Decimal(line['subtotal'])-discount),money(line['tax']),money(line['total'])]))
    for i in range(len(lines),max(0,min(12,int(options.get('blank_rows',7))))):lines.append(cells([fa(i+1)]+['']*10))
    buyer_name=buyer.get('legal_name') or ' '.join(filter(None,[buyer.get('first_name'),buyer.get('last_name')])) or buyer.get('title','')
    from brand import company_brand
    logo_size=max(30,min(100,int(options.get('logo_size',65))));mark='<img src="karname-company-logo" width="'+str(logo_size)+'" height="'+str(round(logo_size*50/65))+'">' if options.get('show_logo',True) and (seller.get('logo') or company_brand(p.get('seller_name',''))) else ''
    heading={'پیش‌فاکتور':'پیش‌فاکتور','فاکتور فروش':'صورتحساب فروش کالا و خدمات','فاکتور خرید':'فاکتور خرید','برگشت از فروش':'برگشت از فروش','برگشت از خرید':'برگشت از خرید'}.get(p['document_type'],p['document_type'])
    parties=(party('فروشنده',buyer,buyer_name)+party('خریدار',seller,p.get('seller_name',''))) if p['document_type'] in ('فاکتور خرید','برگشت از خرید') else (party('فروشنده',seller,p.get('seller_name',''))+party('خریدار',buyer,buyer_name))
    if not options.get('show_seller',True) or not options.get('show_buyer',True):
        seller_part=party('فروشنده',buyer,buyer_name) if p['document_type'] in ('فاکتور خرید','برگشت از خرید') else party('فروشنده',seller,p.get('seller_name',''))
        buyer_part=party('خریدار',seller,p.get('seller_name','')) if p['document_type'] in ('فاکتور خرید','برگشت از خرید') else party('خریدار',buyer,buyer_name)
        parties=(seller_part if options.get('show_seller',True) else '')+(buyer_part if options.get('show_buyer',True) else '')
    summary=p.get('settlement_summary') or {};financial=''
    if summary and options.get('show_financial',True):
        financial='<tr><td>تخفیف: '+money(p['totals']['discount'])+' ریال | نقد و بانک: '+money(summary.get('received'))+' ریال | چک در انتظار وصول: '+money(summary.get('pending_checks'))+' ریال | مانده تسویه‌نشده: '+money(summary.get('uncollected'))+' ریال</td></tr>'
    charge=('<tr><td>هزینه اضافی: '+money(p['totals']['additional_charge'])+' ریال | مالیات هزینه: '+money(p['totals']['charge_tax'])+' ریال</td></tr>') if p['totals'].get('additional_charge') else ''
    bank='<tr><td>شماره حساب: '+esc(seller.get('account_no'))+' &nbsp; شماره شبا: '+esc(seller.get('iban'))+'</td></tr>' if options.get('show_bank',True) else ''
    footer='<tr><td>'+esc(str(options.get('footer',''))[:500]).replace('\n','<br>')+'</td></tr>' if options.get('footer') else ''
    notes='<tr><td>توضیحات: '+esc(p.get('notes','')).replace('\n','<br>')+'</td></tr>' if options.get('show_notes',True) and p.get('notes') else ''
    signatures='<tr><td>مهر و امضای فروشنده &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; مهر و امضا خریدار</td></tr>' if options.get('show_signature',True) else ''
    font_size=max(7,min(11,int(options.get('font_size',8))));padding=max(2,min(8,int(options.get('cell_padding',4))))
    return ('''<html><head><meta charset="utf-8"><style>body{font-family:Vazirmatn,Tahoma;font-size:''' + str(font_size) + '''pt;color:#111}table{border-collapse:collapse}td,th{border:1px solid #444;padding:''' + str(padding) + '''px;text-align:right}th{background:#ededed;text-align:center}.heading td{border:0}.center{text-align:center}</style></head><body>''')+\
        '<table class="heading" width="100%"><tr><td width="22%">شماره فاکتور: '+esc('پس از ثبت' if p['number']=='__AUTO__' else p['number'])+'<br>شماره سند: '+esc(p.get('document_no') or 'پس از ثبت')+'<br>تاریخ: '+fa(p['date'])+('<br>پیش‌فاکتور مبنا: '+esc(p['source_quote_number']) if p.get('source_quote_number') else '')+'</td><td width="58%" class="center"><h2>'+esc(heading)+'</h2></td><td width="20%" class="center">'+mark+'</td></tr></table>'+\
        '<table width="100%">'+parties+'</table>'+\
        '<table width="100%"><tr><th colspan="11">مشخصات کالا یا خدمات</th></tr>'+cells(headings,'th')+''.join(lines)+'</table>'+\
        '<table width="100%">'+charge+'<tr><td>جمع کل: '+money(p['totals']['total'])+' ریال</td></tr>'+financial+bank+notes+footer+signatures+'</table></body></html>'

def set_invoice_document(doc,payload,options=None):
    import base64
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage
    image=QImage();raw=payload.get('seller_snapshot',{}).get('logo','')
    if raw:
        try:image.loadFromData(base64.b64decode(raw,validate=True))
        except (ValueError,TypeError):pass
    if image.isNull():
        from brand import company_brand
        brand=company_brand(payload.get('seller_name','')) or {}
        if brand.get('file'):image.load(str(package_file('assets/'+brand['file'])))
        elif brand.get('data'):
            try:image.loadFromData(base64.b64decode(brand['data'],validate=True))
            except (ValueError,TypeError):pass
    if not image.isNull():doc.addResource(QTextDocument.ImageResource,QUrl('karname-company-logo'),image)
    doc.setHtml(sample_document(payload,options))


class InvoicePreview(QWidget):
    """Fit one complete print page to the viewport, with page navigation."""
    class Page(QWidget):
        def __init__(self,doc,parent=None):
            super().__init__(parent);self.doc=doc;self.page=0;self.setMinimumSize(320,220)
        def paintEvent(self,event):
            painter=QPainter(self);size=self.doc.pageSize();scale=min((self.width()-16)/size.width(),(self.height()-16)/size.height());scale=max(0.01,scale)
            width=size.width()*scale;height=size.height()*scale;x=(self.width()-width)/2;y=(self.height()-height)/2
            painter.fillRect(QRectF(x,y,width,height),QColor('white'));painter.save();painter.translate(x,y);painter.scale(scale,scale);painter.setClipRect(QRectF(0,0,size.width(),size.height()));painter.translate(0,-self.page*size.height());self.doc.drawContents(painter,QRectF(0,self.page*size.height(),size.width(),size.height()));painter.restore()
    def __init__(self,payload,options=None,parent=None):
        super().__init__(parent);self.doc=QTextDocument(self);self.doc.setDefaultFont(QFont('Vazirmatn',9));self.doc.setDocumentMargin(14);set_invoice_document(self.doc,payload,options);self.doc.setPageSize(QSizeF(1123,794));self.page_count=max(1,self.doc.pageCount())
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);self.page=InvoicePreview.Page(self.doc,self);layout.addWidget(self.page,1);bar=QHBoxLayout();bar.addStretch();self.previous=QPushButton('صفحه قبل');self.next=QPushButton('صفحه بعد');self.counter=QLabel();bar.addWidget(self.previous);bar.addWidget(self.counter);bar.addWidget(self.next);bar.addStretch();layout.addLayout(bar);self.previous.clicked.connect(lambda:self.move(-1));self.next.clicked.connect(lambda:self.move(1));self.update_navigation()
    def move(self,step):
        self.page.page=max(0,min(self.page_count-1,self.page.page+step));self.page.update();self.update_navigation()
    def update_navigation(self):
        self.counter.setText('صفحه '+fa(self.page.page+1)+' از '+fa(self.page_count));self.previous.setEnabled(self.page.page>0);self.next.setEnabled(self.page.page+1<self.page_count)

def export(path,payload,options=None):
    writer=QPdfWriter(str(path));writer.setResolution(96);writer.setPageSize(QPageSize(QPageSize.A4));writer.setPageOrientation(QPageLayout.Landscape);writer.setPageMargins(QMarginsF(12,12,12,12),QPageLayout.Millimeter);writer.setTitle(payload.get('title','فاکتور مشتری'));writer.setCreator('کارنامه');doc=QTextDocument();doc.setDefaultFont(QFont('Vazirmatn',10));set_invoice_document(doc,payload,options);doc.setPageSize(QSizeF(writer.width(),writer.height()));doc.print_(writer)
