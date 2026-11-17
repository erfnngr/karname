"""Adapter to the existing assistant panel; model execution remains native."""
import json
from PySide6.QtCore import QObject, QTimer, Signal, Slot


class ReactAssistantBridge(QObject):
    changed = Signal(str)
    completed = Signal(str, str)

    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self.panel = panel
        self.last = ''
        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        from react_design_host import should_poll_section
        if not should_poll_section(getattr(self.panel, 'owner', None), self.panel):
            return
        self.publish()

    def publish(self):
        p = self.panel
        current = p.identity == p.user_id() and not getattr(p.owner, '_locking', False)
        model_name = ''
        provider = 'lmstudio'
        templates = []
        if current and hasattr(p.owner, 'data'):
            try:
                from ai_chat_ui import connection
                cfg = connection(p.owner)
                provider = cfg.get('provider', 'lmstudio')
                model_name = cfg.get('model') or ('اول‌ای‌آی' if provider == 'avalai' else 'کارنامه')
            except Exception:
                pass
            try:
                from ui_permissions import allowed
                from ai_prompt_templates import TEMPLATES, available
                if allowed(p.owner, 'assistant', 'use'):
                    templates = [{'key': t['key'], 'title': t['title'], 'text': t['text'], 'mode': t.get('mode', 'app'), 'primary': bool(t.get('primary'))}
                                 for t in TEMPLATES if available(p.owner, t)]
            except Exception:
                pass
        mem_check = getattr(p, 'memory_check', None)
        state = {'items': [{'role': x.get('role', ''), 'content': str(x.get('content', ''))} for x in p.items] if current else [],
                 'busy': bool(p.busy or p.applying), 'status': p.status.text() if current else 'نشست کاربر تغییر کرده است.',
                 'can_send': current and p.send_button.isEnabled(), 'can_stop': current and not p.stop_button.isHidden(),
                 'can_review': current and p.plan_button.isEnabled(), 'mode': p.mode.currentData(),
                 'context_enabled': current and p.context_check.isEnabled(), 'context': current and p.context_check.isChecked(),
                 'model_name': model_name, 'provider': provider,
                 'memory_available': current and p.user_id() != 'standalone',
                 'memory_enabled': bool(current and mem_check is not None and mem_check.isChecked()),
                 'templates': templates}
        raw = json.dumps(state, ensure_ascii=False)
        if raw != self.last:
            self.last = raw
            self.changed.emit(raw)

    @Slot(str, str, str)
    def request(self, request_id, action, raw):
        try:
            if len(raw) > 40000 or len(request_id) > 80: raise ValueError('درخواست معتبر نیست.')
            payload = json.loads(raw)
            if not isinstance(payload, dict): raise ValueError('درخواست معتبر نیست.')
            p = self.panel
            if p.identity != p.user_id() or getattr(p.owner, '_locking', False): raise ValueError('نشست کاربر تغییر کرده است.')
            value = None
            if action == 'send':
                if set(payload) != {'text'} or not isinstance(payload['text'], str) or not 0 < len(payload['text'].strip()) <= 8000: raise ValueError('متن معتبر نیست.')
                if not p.send_button.isEnabled() or p.busy or p.applying: raise ValueError('ارسال در حال حاضر در دسترس نیست.')
                previous=p.prompt.toPlainText()
                if previous.strip() and previous!=payload['text']:raise ValueError('ابتدا پیش‌نویس دستیار فعلی را بررسی کنید.')
                try:
                    p.prompt.setPlainText(payload['text']);p.send()
                    if p.prompt.toPlainText().strip():raise ValueError(p.status.text() or 'درخواست پذیرفته نشد.')
                except Exception:
                    p.prompt.setPlainText(previous)
                    raise
            elif action == 'refresh':
                if payload: raise ValueError('درخواست معتبر نیست.')
                self.last = ''
            elif action == 'mode':
                if set(payload)!={'value'} or payload['value'] not in ('chat','plan','app') or p.busy or p.applying:raise ValueError('تغییر حالت در دسترس نیست.')
                index=p.mode.findData(payload['value'])
                if index<0:raise ValueError('حالت دستیار معتبر نیست.')
                p.mode.setCurrentIndex(index)
            elif action == 'context':
                if set(payload)!={'enabled'} or type(payload['enabled']) is not bool or not p.context_check.isEnabled():raise ValueError('تغییر دسترسی در دسترس نیست.')
                p.context_check.setChecked(payload['enabled'])
            elif action == 'memory':
                mem_check = getattr(p, 'memory_check', None)
                if set(payload)!={'enabled'} or type(payload['enabled']) is not bool or mem_check is None or p.user_id()=='standalone':raise ValueError('تنظیم حافظه در دسترس نیست.')
                mem_check.setChecked(payload['enabled'])
            elif action == 'clear_memory':
                if payload: raise ValueError('درخواست معتبر نیست.')
                if p.user_id()=='standalone': raise ValueError('ابتدا وارد حساب شوید.')
                from ai_memory import clear
                clear(p.user_id()); p.history = []; p.status.setText('حافظه شخصی پاک شد.')
            elif action == 'request_history_list':
                if payload: raise ValueError('درخواست معتبر نیست.')
                mem_check = getattr(p, 'memory_check', None)
                if p.user_id()=='standalone' or not (mem_check and mem_check.isChecked()):
                    value = []
                else:
                    from ai_memory import read_requests
                    labels = {'processing':'در حال پردازش یا ناتمام','interrupted':'متوقف‌شده؛ نیازمند بررسی','awaiting':'منتظر اطلاعات تکمیلی','answered':'پاسخ داده‌شده','completed':'انجام‌شده','failed':'انجام‌نشده','partial':'انجام ناقص'}
                    rows = read_requests(p.user_id(), getattr(p, 'scope_stamp', None))
                    value = [{'id': r.get('id',''), 'request': r.get('request',''), 'status': r.get('status',''), 'status_label': labels.get(r.get('status'),'نامشخص'), 'detail': str(r.get('detail',''))[:600]} for r in reversed(rows[-30:])]
            elif action == 'scheduled_list':
                if payload: raise ValueError('درخواست معتبر نیست.')
                if p.user_id()=='standalone':
                    value = []
                else:
                    from ai_schedule import read
                    from datetime import datetime, timezone, timedelta
                    from storage import fa
                    import jdatetime
                    labels = {'pending':'در انتظار','running':'در حال اجرا','failed':'ناموفق','interrupted':'متوقف‌شده'}
                    items = [x for x in read(p.user_id()) if x.get('status') in labels]
                    value = []
                    for item in items:
                        when = datetime.fromisoformat(item['due_at']).astimezone(timezone(timedelta(hours=3, minutes=30)))
                        due_fa = fa(jdatetime.date.fromgregorian(date=when.date()).strftime('%Y/%m/%d') + ' ' + when.strftime('%H:%M'))
                        value.append({'id': item['id'], 'due_at': item['due_at'], 'due_jalali': due_fa, 'status': item['status'], 'status_label': labels[item['status']], 'prompt': item['prompt'], 'mode': item.get('mode','app')})
            elif action == 'scheduled_cancel':
                if set(payload)!={'id'} or not isinstance(payload.get('id'), str) or not payload['id']: raise ValueError('شناسه درخواست معتبر نیست.')
                if p.user_id()=='standalone': raise ValueError('ابتدا وارد حساب شوید.')
                from ai_schedule import transition
                if not transition(p.user_id(), payload['id'], ('pending','failed','interrupted'), 'cancelled'):
                    raise ValueError('درخواست در حال اجرا قابل لغو نیست.')
                if hasattr(p, 'schedule_changed'): p.schedule_changed()
                p.status.setText('درخواست زمان‌بندی‌شده لغو شد.')
            elif action == 'suggest':
                if set(payload)!={'text'} or not isinstance(payload['text'],str) or len(payload['text'])>6000:raise ValueError('متن معتبر نیست.')
                from ui_permissions import allowed
                from ai_prompt_templates import suggest
                value=[{'title':x['title'],'text':x['text'],'mode':x.get('mode','app')} for x in suggest(payload['text'],p.owner)] if len(payload['text'].split())>=2 and allowed(p.owner,'assistant','use') else []
            elif action == 'schedule':
                if set(payload)!={'text'} or not isinstance(payload['text'],str) or not 0<len(payload['text'].strip())<=8000 or p.busy or p.applying:raise ValueError('زمان‌بندی در دسترس نیست.')
                previous=p.prompt.toPlainText()
                if previous.strip() and previous!=payload['text']:raise ValueError('ابتدا پیش‌نویس دستیار فعلی را بررسی کنید.')
                try:
                    p.prompt.setPlainText(payload['text']);p.schedule_prompt();value={'scheduled':not bool(p.prompt.toPlainText().strip())}
                finally:p.prompt.setPlainText(previous)
            elif action in ('stop', 'new', 'settings', 'review', 'scheduled', 'history'):
                if payload: raise ValueError('درخواست معتبر نیست.')
                if action == 'stop': p.stop()
                elif action == 'new':
                    if p.applying: raise ValueError('عملیات در حال انجام است.')
                    p.new_conversation()
                elif action == 'settings': p.settings()
                elif action == 'scheduled': p.show_scheduled_prompts()
                elif action == 'history': p.show_request_history()
                else:
                    if not p.plan_button.isEnabled(): raise ValueError('چیزی برای بررسی وجود ندارد.')
                    p.preview()
            else: raise ValueError('این عملیات دستیار مجاز نیست.')
            self.publish()
            result = {'ok': True, 'value':value}
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}
        self.completed.emit(request_id, json.dumps(result, ensure_ascii=False))

    def close(self):
        self.timer.stop()
