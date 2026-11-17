import os,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
import storage
from ai_schedule import add,read,write,recover,transition,path_for,backup_data,prepare_restore,reschedule

class AssistantScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':self.tmp.name});self.env.start();storage.set_profile(None)
    def tearDown(self):storage.set_profile(None);self.env.stop();self.tmp.cleanup()
    def test_private_storage_recovery_and_account_isolation(self):
        future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat();entry=add('user-a','متن خصوصی نمونه','chat',future);add('user-b','درخواست دیگر','app',future);self.assertNotIn('متن خصوصی نمونه'.encode(),path_for('user-a').read_bytes());self.assertEqual(read('user-b')[0]['prompt'],'درخواست دیگر');self.assertTrue(transition('user-a',entry['id'],('pending',),'running'));recover('user-a');self.assertEqual(read('user-a')[0]['status'],'interrupted');self.assertEqual(read('user-b')[0]['status'],'pending');self.assertFalse(transition('user-a',entry['id'],('pending',),'running'))
    def test_backup_restore_preserves_future_and_pauses_overdue(self):
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw):
            future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat();add('user-a','فردا','chat',future);add('user-a','قدیمی','app',future);items=read('user-a');items[1]['due_at']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat();write('user-a',items);backup=backup_data('user-a');restored=prepare_restore('user-a',backup);self.assertEqual([x['status'] for x in restored],['pending','interrupted'])
            with self.assertRaises(ValueError):prepare_restore('user-b',backup)
    def test_interrupted_request_can_be_rescheduled_by_its_owner(self):
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw):
            future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat();entry=add('user-a','درخواست','app',future);transition('user-a',entry['id'],('pending',),'running');recover('user-a');later=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat();reschedule('user-a',entry['id'],later);self.assertEqual(read('user-a')[0]['status'],'pending');self.assertTrue(read('user-a')[0]['due_at'].startswith(later[:16]))
            with self.assertRaises(ValueError):reschedule('user-b',entry['id'],later)
