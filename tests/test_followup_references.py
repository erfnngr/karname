import unittest
from ai_chat_ui import clarification_request, resolve_recent_reminders
from storage import new_event

class FollowupReferences(unittest.TestCase):
    def test_failed_request_correction_retains_original_but_new_action_is_separate(self):
        history=[{'role':'user','content':'پرداخت اجاره را ثبت کن'},{'role':'assistant','content':'درخواست قابل اجرا نیست: مبلغ مشخص نیست.'}]
        self.assertIn('پرداخت اجاره',clarification_request(history,'مبلغ ۱۰۰۰۰ ریال'))
        self.assertEqual(clarification_request(history,'چرا؟'),'چرا؟')
        new='فاکتور فروش با مبلغ ۲۰۰۰۰ بساز';self.assertEqual(clarification_request(history,new),new)
        history[-1]['content']='نتیجه واقعی برنامه: ✓ ذخیره شد'
        self.assertEqual(clarification_request(history,'مبلغ ۱۰۰۰۰ ریال'),'مبلغ ۱۰۰۰۰ ریال')
    def test_day_number_requires_one_explicit_offered_date(self):
        history=[{'role':'user','content':'برای شنبه هفته بعد یادآور بساز'},{'role':'assistant','content':'کدام تاریخ؟ ۱۴۰۵/۰۸/۲۳ یا ۱۴۰۵/۰۸/۳۰؟'}]
        result=clarification_request(history,'۲۳');self.assertIn('1405/08/23',result);self.assertIn('یادآور',result)
        history[-1]['content']='کدام؟ ۱۴۰۵/۰۸/۲۳ یا ۱۴۰۵/۰۹/۲۳؟'
        self.assertEqual(clarification_request(history,'۲۳'),'۲۳')
        extended=[{'role':'user','content':'برای جلسه یادآور بساز'},{'role':'assistant','content':'درخواست قابل اجرا نیست: تاریخ لازم است.'},{'role':'user','content':'روز دقیق را چطور مشخص کنم؟'},{'role':'assistant','content':'کدام تاریخ؟ ۱۴۰۵/۰۸/۲۳ یا ۱۴۰۵/۰۸/۳۰؟'}]
        self.assertIn('برای جلسه',clarification_request(extended,'۲۳'));self.assertIn('1405/08/23',clarification_request(extended,'۲۳'))
    def test_weekday_uses_next_occurrence_and_rejects_other_date(self):
        from datetime import date
        from ai_language import time_window
        from ai_app_actions import ensure_requested_day
        self.assertEqual(time_window('برای شنبه جلسه بذار',date(2026,11,11)),(date(2026,11,14),date(2026,11,14)))
        self.assertEqual(time_window('شنبه هفته بعد',date(2026,11,11)),(date(2026,11,21),date(2026,11,21)))
        ctx={'query':'برای شنبه جلسه بذار','public':{'today_jalali':'1405/08/20'}}
        ensure_requested_day('1405/08/23',ctx)
        with self.assertRaises(ValueError):ensure_requested_day('1405/08/24',ctx)
    def test_counted_reference_requires_unique_targets_and_affirmative_request(self):
        events=[new_event('شخصی','تست تاریخ','1405/08/21'),new_event('شخصی','تست حافظه','1405/08/21')]
        history=[{'role':'assistant','content':'دو یادآور «تست تاریخ» و «تست حافظه» دارید.'}]
        for request in ('اون دوتا رو لغو کن','اون ۲ تا رو پاک کن','همون دوتا رو حذف کن'):
            self.assertIn('تست حافظه',resolve_recent_reminders(history,request,events))
        for request in ('اون دوتارو لغو نکن','چرا اون دوتا حذف نشد؟','اون سه تا رو حذف کن'):
            self.assertEqual(resolve_recent_reminders(history,request,events),request)
        events.append(new_event('شخصی','تست تاریخ','1405/08/22'))
        self.assertEqual(resolve_recent_reminders(history,'اون دوتا رو لغو کن',events),'اون دوتا رو لغو کن')

    def test_singular_reference_never_selects_among_multiple(self):
        events=[new_event('شخصی','قرارداد','1405/08/21'),new_event('شخصی','بیمه','1405/08/21')]
        one=[{'role':'assistant','content':'یادآور «قرارداد» فرداست.'}]
        self.assertIn('قرارداد',resolve_recent_reminders(one,'اونو حذف کن',events))
        many=[{'role':'assistant','content':'یادآورها «قرارداد» و «بیمه» هستند.'}]
        self.assertEqual(resolve_recent_reminders(many,'اونو حذف کن',events),'اونو حذف کن')

    def test_meeting_followup_does_not_absorb_new_request(self):
        history=[{'role':'user','content':'چت با آقای پزنده بساز'},{'role':'assistant','content':'گفتگوی شخصی با دکتر پزنده آماده شد.'},{'role':'user','content':'یه جلسه باهاش بذار'},{'role':'assistant','content':'برای جلسه تاریخ ساعت و موضوع لازم است بگویید.'}]
        combined=clarification_request(history,'فردا ساعت 10 موضوع آزمایش')
        self.assertIn('پزنده',combined);self.assertIn('آزمایش',combined)
        request='یه یادآور برای مالیات بساز'
        self.assertEqual(clarification_request(history,request),request)
