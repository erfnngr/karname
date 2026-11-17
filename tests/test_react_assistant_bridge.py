import json
import unittest
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from react_assistant_bridge import ReactAssistantBridge


class AssistantBridgeTests(unittest.TestCase):
    def test_existing_panel_handles_send_and_denies_unknown_actions(self):
        app = QApplication.instance() or QApplication([])
        class Prompt:
            text = ''
            def setPlainText(self, value): self.text = value
            def toPlainText(self): return self.text
        panel = SimpleNamespace(items=[], busy=False, applying=False, status=SimpleNamespace(text=lambda:'آماده'),
                                send_button=SimpleNamespace(isEnabled=lambda:True), stop_button=SimpleNamespace(isHidden=lambda:True),
                                plan_button=SimpleNamespace(isEnabled=lambda:False), prompt=Prompt())
        called=[]
        panel.mode=SimpleNamespace(currentData=lambda:'app');panel.context_check=SimpleNamespace(isEnabled=lambda:True,isChecked=lambda:True)
        panel.identity='u';panel.user_id=lambda:'u';panel.owner=SimpleNamespace(_locking=False)
        panel.send=lambda:(called.append(panel.prompt.text),panel.prompt.setPlainText(''))
        bridge=ReactAssistantBridge(panel);results={};bridge.completed.connect(lambda key,raw:results.update({key:json.loads(raw)}))
        bridge.request('1','send',json.dumps({'text':'سلام'}));self.assertEqual(called,['سلام']);self.assertTrue(results['1']['ok'])
        panel.send=lambda:None
        bridge.request('rejected','send',json.dumps({'text':'متن نامعتبر'}));self.assertFalse(results['rejected']['ok']);self.assertEqual(panel.prompt.text,'')
        bridge.request('2','send',json.dumps({'text':'سلام','model':'other'}));self.assertFalse(results['2']['ok'])
        bridge.request('3','delete_everything','{}');self.assertFalse(results['3']['ok'])
        panel.prompt.text='';panel.schedule_prompt=lambda:None
        bridge.request('cancel-schedule','schedule',json.dumps({'text':'بعداً'}));self.assertFalse(results['cancel-schedule']['value']['scheduled']);self.assertEqual(panel.prompt.text,'')
        panel.schedule_prompt=lambda:panel.prompt.setPlainText('')
        bridge.request('save-schedule','schedule',json.dumps({'text':'بعداً'}));self.assertTrue(results['save-schedule']['value']['scheduled'])
        panel.identity='other';bridge.request('5','send',json.dumps({'text':'خصوصی'}));self.assertFalse(results['5']['ok']);panel.identity='u'
        panel.busy=True;bridge.request('4','send',json.dumps({'text':'دوباره'}));self.assertFalse(results['4']['ok']);bridge.close()
