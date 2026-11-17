import json
import unittest
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from react_tax_bridge import ReactTaxBridge
from tax_workflows import WORKFLOWS


class Combo:
    def __init__(self, entries, index=0):self.entries=entries;self.index=index
    def currentText(self):return self.entries[self.index][0]
    def currentData(self):return self.entries[self.index][1]
    def count(self):return len(self.entries)
    def itemData(self,i):return self.entries[i][1]
    def itemText(self,i):return self.entries[i][0]
    def findData(self,value):return next((i for i,(_,v) in enumerate(self.entries) if v==value),-1)
    def setCurrentIndex(self,index):self.index=index
    def setCurrentText(self,value):self.index=next(i for i,(label,_) in enumerate(self.entries) if label==value)


class TaxBridgeTests(unittest.TestCase):
    def test_steps_use_selected_authorized_case(self):
        app=QApplication.instance() or QApplication([])
        category=next(iter(WORKFLOWS));record={'id':'case','company_id':'c','payload':{'tax_type':category,'workflow_done':[]}}
        panel=SimpleNamespace(workflow=Combo([(x,x) for x in WORKFLOWS]),company=Combo([('شرکت','c')]),map_case=Combo([('انتخاب',None),('پرونده','case')],1),owner=SimpleNamespace(org=SimpleNamespace(records=[record])),map_status=SimpleNamespace(text=lambda:'آماده'))
        panel.company_permitted=lambda *args:True;opened=[];panel.open_map_step=lambda index:opened.append(index)
        bridge=ReactTaxBridge(panel);states=[];results={};bridge.changed.connect(lambda raw:states.append(json.loads(raw)));bridge.completed.connect(lambda key,raw:results.update({key:json.loads(raw)}))
        bridge.request('state','refresh','{}');self.assertEqual(states[-1]['selected_case'],'case');self.assertEqual(len(states[-1]['steps']),len(WORKFLOWS[category]))
        bridge.request('open','step',json.dumps({'index':0}));self.assertTrue(results['open']['ok']);self.assertEqual(opened,[0])
        bridge.request('bad','step',json.dumps({'index':999}));self.assertFalse(results['bad']['ok'])
        panel.company_permitted=lambda *args:False;bridge.request('denied','step',json.dumps({'index':0}));self.assertFalse(results['denied']['ok']);bridge.publish();self.assertEqual(states[-1]['cases'],[]);bridge.close()
