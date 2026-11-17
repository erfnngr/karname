import os,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import ai_memory
from ai_prompt_templates import suggest
from ai_chat_ui import explicit_action_requested

class AssistantMemoryTests(unittest.TestCase):
    def test_request_state_is_private_and_explicitly_updated(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(ai_memory,'app_dir',return_value=Path(folder)),patch('local_vault.transform',side_effect=lambda data,decrypt=False:bytes(x^0x5a for x in data)):
            ai_memory.save_request('alice','role-a','id1','جلسه بساز','awaiting','تاریخ را بگویید')
            self.assertEqual(ai_memory.read_requests('alice','role-a')[0]['status'],'awaiting')
            self.assertEqual(ai_memory.read_requests('alice','role-b'),[]);self.assertEqual(ai_memory.read_requests('bob','role-a'),[])
            ai_memory.save_request('alice','role-a','id1','جلسه فردا','completed','ثبت شد')
            rows=ai_memory.read_requests('alice','role-a');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'completed')
            self.assertFalse(ai_memory.save_request('alice','role-a','id2','api key xyz','answered',''))
            ai_memory.clear('alice');self.assertEqual(ai_memory.read_requests('alice','role-a'),[])
    def test_conversation_is_separate_per_account_and_excludes_secret_turns(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(ai_memory,'app_dir',return_value=Path(folder)),patch('local_vault.transform',side_effect=lambda data,decrypt=False:bytes(x^0x5a for x in data)):
            rows=[{'role':'user','content':'جلسه با همکار بساز'},{'role':'assistant','content':'چه تاریخی؟'},{'role':'user','content':'api key secret'},{'role':'assistant','content':'دریافت شد'}]
            ai_memory.save_conversation('alice',rows)
            self.assertEqual(ai_memory.read_conversation('alice'),rows[:2]);self.assertEqual(ai_memory.read_conversation('bob'),[])
            self.assertNotIn('همکار'.encode(),ai_memory.conversation_path('alice').read_bytes())
            ai_memory.clear('alice');self.assertEqual(ai_memory.read_conversation('alice'),[])
            ai_memory.save_conversation('alice',rows,'role-a');self.assertEqual(ai_memory.read_conversation('alice','role-b'),[]);self.assertEqual(ai_memory.read_conversation('alice','role-a'),rows[:2])
    def test_account_isolation_encryption_recall_and_clear(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(ai_memory,'app_dir',return_value=Path(folder)):
            self.assertTrue(ai_memory.record('alice','یادآوری بیمه را ثبت کن','یک یادآوری ثبت شد'))
            self.assertTrue(ai_memory.record('bob','یک کار دیگر','ثبت شد'))
            self.assertEqual(len(ai_memory.read('alice')),1);self.assertNotEqual(ai_memory.path_for('alice'),ai_memory.path_for('bob'))
            self.assertNotIn('بیمه'.encode(),ai_memory.path_for('alice').read_bytes())
            self.assertIn('بیمه',ai_memory.recall('alice','بیمه')[0]['request'])
            self.assertFalse(ai_memory.record('alice','API key: abcdef','ثبت شد'));self.assertEqual(len(ai_memory.read('alice')),1)
            ai_memory.clear('alice');self.assertFalse(ai_memory.read('alice'));self.assertTrue(ai_memory.read('bob'))
    def test_suggestions_are_short_and_match_synonyms(self):
        owner=SimpleNamespace(session_user=None)
        result=suggest('صورتحساب',owner);self.assertTrue(result);self.assertLessEqual(len(result),3)
        self.assertEqual(suggest('',owner),[])
    def test_colloquial_action_and_negation(self):
        self.assertTrue(explicit_action_requested('فاکتور را درست کن'))
        self.assertFalse(explicit_action_requested('این فاکتور را درست نکن'))
        self.assertFalse(explicit_action_requested('میخوام بدونم چطور فاکتور ثبت کنم'))

if __name__=='__main__':unittest.main()
