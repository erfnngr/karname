import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication
from invoice_pdf import export
app=QApplication([])
from appearance import init_font
init_font()
p={'number':'12345','date':'1405/08/01','title':'آزمایش','document_type':'فاکتور فروش','status':'issued','customer_snapshot':{'title':'مشتری نمونه','address':'تهران','national_id':'1234567890'},'seller_name':'مانا','seller_snapshot':{'phone':'12345','address':'تهران'},'lines':[{'description':'کالای نمونه','quantity':'2','unit':'عدد','unit_price':'100000','tax_rate':'10'}]}
export(Path('../../work/invoice-v811-sample.pdf'),p)
