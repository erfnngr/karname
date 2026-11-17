import unittest
from tax_workflows import case_review

class TaxCaseReviewTests(unittest.TestCase):
    def test_missing_evidence_only_reported_not_inferred(self):
        notes=case_review({'status':'submitted','due_date':'1405/08/30','source':'سازمان','responsible':'حسابدار'})
        self.assertTrue(any('شماره پیگیری' in x for x in notes));self.assertTrue(any('تاریخ ارسال' in x for x in notes))
        self.assertEqual(case_review({'status':'completed','due_date':'1405/08/30','source':'سازمان','responsible':'حسابدار','reference':'12','submitted_date':'1405/08/10'}),[])
