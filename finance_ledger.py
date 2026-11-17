"""A readable, non-posting statement built from already recorded documents."""
from decimal import Decimal


def statement(customer_id, invoices, transactions, transfers=(), checks=()):
    rows=[];checks_by_id={check['id']:check for check in checks}
    signs={'فاکتور فروش':1,'برگشت از خرید':1,'فاکتور خرید':-1,'برگشت از فروش':-1}
    incomplete=False
    for record in invoices:
        p=record['payload'];kind=p.get('document_type');sign=signs.get(kind)
        if not sign or p.get('client_id')!=customer_id or p.get('status') not in ('issued','paid'):continue
        if not isinstance(p.get('settlement_summary'),dict):incomplete=True;continue
        total=Decimal(str(p.get('totals',{}).get('total','0')))
        paid=Decimal(str(p['settlement_summary'].get('received','0')))
        title=kind+' · '+str(p.get('number',''))
        rows.append((p.get('date',''),str(p.get('document_no','')),0,title,sign*total))
        known=Decimal(0);lines=p.get('settlement',[])
        if not isinstance(lines,list):lines=[];incomplete=True
        for line in lines:
            if not isinstance(line,dict):incomplete=True;continue
            kind=line.get('kind');value=Decimal(str(line.get('amount','0')))
            if kind in ('cash','bank'):
                known+=value;rows.append((p.get('date',''),str(p.get('document_no','')),1,'تسویه نقدی / بانکی در '+title,-sign*value))
            elif kind=='check':
                check=checks_by_id.get(line.get('check_id'))
                if check and check.get('status')=='cleared':
                    known+=value;cleared=check.get('cleared_date','');incomplete=incomplete or not bool(cleared);rows.append((cleared,str(p.get('document_no','')),1,'وصول چک '+str(check.get('number',''))+' در '+title,-sign*value))
        if paid!=known:
            incomplete=True;rows.append(('',str(p.get('document_no','')),1,'تسویه پیشین با تاریخ نامشخص در '+title,-sign*(paid-known)))
    for tx in transactions:
        if tx.get('source') not in (None,'transaction') or tx.get('customer_id')!=customer_id:continue
        sign=-1 if tx['direction']=='income' else 1
        rows.append((tx.get('date',''),str(tx.get('document_no','')),2,tx.get('reason',''),sign*Decimal(str(tx['amount']))))
    for transfer in transfers:
        if transfer.get('recipient_id')==customer_id and transfer.get('status')=='cleared':
            cleared=transfer.get('cleared_date','');incomplete=incomplete or not bool(cleared);rows.append((cleared,'',3,'وصول چک خرج‌شده · '+str(transfer.get('number','')),Decimal(str(transfer['amount']))))
    rows.sort(key=lambda row:(not bool(row[0]),row[0],row[1].zfill(20),row[2]));balance=Decimal(0);result=[]
    for date,document,_,description,delta in rows:
        balance+=delta;result.append(dict(date=date or 'نامشخص',document=document,description=description,debit=str(max(delta,Decimal(0))),credit=str(max(-delta,Decimal(0))),balance=str(balance)))
    return result,incomplete
