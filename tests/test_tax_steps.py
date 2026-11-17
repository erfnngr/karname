import unittest
from tax_workflows import workflow_progress,WORKFLOWS
from org_store import Store,DomainError

class TaxStepTests(unittest.TestCase):
    def test_insurance_steps_are_sequential_and_persistent_data_validates(self):
        payload=dict(title='بیمه آبان',tax_type='بیمه کارکنان',period='1405/08',status='draft',insurance_workshop='123',insured_names='کارمند اول\nکارمند دوم')
        self.assertEqual(workflow_progress(payload),[False]*len(WORKFLOWS['بیمه کارکنان']))
        payload['workflow_done']=[True,False];Store.validate(None,'tax_case',payload)
        payload['workflow_done']=[False,True]
        with self.assertRaises(DomainError):Store.validate(None,'tax_case',payload)
        payload['workflow_done']=['yes']
        with self.assertRaises(DomainError):Store.validate(None,'tax_case',payload)
