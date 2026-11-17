import unittest
from datetime import datetime,timedelta,timezone
from ai_language import search_query,time_window,terms,domain_hint

class LanguageWeatherTests(unittest.TestCase):
    def test_synonyms_preserve_original_and_qualify_context(self):
        self.assertIn('فاکتور',search_query('صورتحساب مشتری'))
        self.assertIn('تردد',search_query('ورود و خروج کارکنان'))
        self.assertIn('فاکتور',terms('فکتور'))
    def test_temporal_windows_are_unambiguous(self):
        today=datetime(2026,11,7).date()
        self.assertEqual(time_window('فردا',today),(today+timedelta(days=1),today+timedelta(days=1)))
        for phrase in ('پس فردا','پس‌فردا','پسفردا','جلسه پسفرداست'):self.assertEqual(time_window(phrase,today),(today+timedelta(days=2),today+timedelta(days=2)))
        self.assertEqual(time_window('کارهای گذشته',today),(None,today-timedelta(days=1)))
        self.assertEqual(time_window('کارهای آینده',today),(today,None))
    def test_reminder_and_chat_are_distinguished_conservatively(self):
        self.assertEqual(domain_hint('یادم بنداز فردا اظهارنامه بفرستم'),'reminder')
        self.assertEqual(domain_hint('فردا پیگیری قرارداد یادم بیار'),'reminder')
        self.assertEqual(domain_hint('برای فردا آلارم بذار'),'reminder')
        self.assertEqual(domain_hint('برای همکار پیغام بدید جلسه فرداست'),'chat')
        self.assertIn('یادآور',search_query('فردا یاد م بنداز'))
        self.assertEqual(domain_hint('برای گروه مدیران پیام بفرست که فردا جلسه داریم'),'chat')
        self.assertIsNone(domain_hint('یک یادآور ثبت کن و پیام گروه را هم ارسال کن'))

if __name__=='__main__':unittest.main()
