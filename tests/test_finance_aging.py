import unittest
from datetime import date
from finance_aging import aging,check_summary


class AgingTest(unittest.TestCase):
    def test_overdue_and_unknown_due_dates(self):
        base={'client_id':'a','document_type':'فاکتور فروش','status':'issued','settlement_summary':{'uncollected':'1000'},'due_date':'1405/01/01'}
        rows=aging([{'payload':base,'remaining_after_allocations':'700'},{'payload':dict(base,due_date='')}],date(2026,4,10))
        self.assertEqual(rows[0]['amount'],'700');self.assertEqual(rows[0]['bucket'],'۱ تا ۳۰ روز');self.assertEqual(rows[1]['bucket'],'نامشخص')
    def test_only_open_checks_count_for_deadlines(self):
        checks=[{'due_date':'1405/01/01','status':'pending'},{'due_date':'1405/01/22','status':'deposited'},{'due_date':'1405/01/01','status':'cleared'}]
        self.assertEqual(check_summary(checks,date(2026,4,10)),{'overdue':1,'upcoming':1})
