"""Private in-session chat with LM Studio and explicitly reviewed calendar drafts."""
import html,threading,re
from PySide6.QtCore import Qt,QObject,Signal,QTimer
from PySide6.QtWidgets import (QWidget,QFrame,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QLineEdit,QComboBox,QPlainTextEdit,QTextBrowser,QDialogButtonBox,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QCheckBox,QMenu)
from lmstudio_client import LMClient,LMError,Cancelled,DEFAULT_URL,base_url,messages_for
from ai_planning import parse_plan,validate_item,save_plan,system_prompt,REPEAT
from storage import app_dir,today_j,jformat,fa
from ui_permissions import allowed,gate
from ui_icons import iconize
from assistant_model import GEMMA_MODEL

def send_arrow_icon():
    from PySide6.QtGui import QIcon,QPixmap,QPainter,QPen,QColor
    from PySide6.QtCore import QPointF
    pix=QPixmap(22,22);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor('white'),2,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.drawLine(QPointF(11,17),QPointF(11,5));p.drawLine(QPointF(11,5),QPointF(6,10));p.drawLine(QPointF(11,5),QPointF(16,10));p.end();return QIcon(pix)

def explicit_action_requested(text):
    from storage import normalize
    requested=normalize(text).casefold().replace('\u200c',' ')
    verbs=('ثبت','بساز','ایجاد','اضافه','ارسال','بفرست','بذار','بگذار','تنظیم','عوض','تغییر','ویرایش','اصلاحش کن','درست کن','راه بنداز','باز کن','بازکن','انجام','تکمیل','لغو','تایید','تأیید','بی صدا','بی‌صدا','میوت','ساکت','با صدا','حذف','پاک کن','پاکش کن','بازیابی','بازگردان','بردار','فعال کن','خاموش','روشن','لایک','بپسند','رای بده','رأی بده','وارد کن','منتشر','تهیه','بگیر')
    if re.search(r'(انجام|ثبت|ارسال|حذف|تغییر|پاک|درست|اصلاح|ایجاد|اضافه)\s*(?:ش|شون|ش را|را)?\s*(?:نکن|نده|نفرست|نساز)',requested) or 'نچین' in requested or 'نمیخوام' in requested or 'نمی خوام' in requested or 'نمی خواهم' in requested:return False
    if any(x in requested for x in ('میخوام بدونم','می خواهم بدانم','میخوام بدانم','توضیح بده','راهنمایی کن')) or re.search(r'(چطور|چگونه|چجوری|آیا)\s.*(?:کنم|کنیم|بچینم|بچینیم|بسازم|بسازیم|میشه|ممکنه)',requested):return False
    natural=('یادآوری کن','یادم بنداز','یاد م بنداز','یادم بیار','یادم بینداز','یادم باشه','یادم بمونه','یادآوری بشه','یادآوری بکن','پیام بده','پیام بدید','پیام بکن','پیغام بده','پیغام بدید','پیغام بکن','پیام بفرست','برگردون','برنامه بچین','بچین','برنامه ریزی کن','برنامه بریز','برنامه بنویس','برنامه بده','پلن بده','برام درست کن','برایم درست کن','درستش کن','بکن','انجامش بده','برام بساز','برام بفرست')
    return any(word in requested for word in verbs+natural) or bool(re.search(r'(?<!\w)رد(?!\w)',requested))

def compact_conversation(history):
    """Keep recent turns readable instead of letting one large JSON consume context."""
    rows=[]
    for index,item in enumerate(history[-24:]):
        role=item.get('role');content=str(item.get('content',''))
        if role not in ('user','assistant') or not content:continue
        limit=6000 if index==len(history[-24:])-1 and role=='user' else 2000 if role=='user' else 1400
        rows.append(dict(role=role,content=content[:limit]))
    return rows

def previous_search_hint(history,text):
    from ai_language import clean
    q=clean(text)
    if len(q)>100 and not any(x in q for x in ('همون','همین','قبلی','اون','ادامه','همان')):return ''
    prior=[str(x.get('content','')) for x in history if x.get('role')=='user' and x.get('content')]
    return ' '.join(prior[-2:])[-1200:]

def resolve_recent_reminders(history,text,events):
    """Resolve only an explicitly counted reference to uniquely named reminders."""
    from storage import normalize
    q=normalize(text).replace('\u200c',' ').casefold()
    if not re.search(r'(?:اون|آن|همون|همان|این)',q) or not re.search(r'(?:لغو|حذف|پاک)',q) or re.search(r'(?:نکن|نمی\s*خوام|چرا|چطور|چگونه|[؟?])',q):return text
    count=2 if re.search(r'(?:دو\s*تا|دوتا|2\s*تا|۲\s*تا)',q) else 3 if re.search(r'(?:سه\s*تا|3\s*تا|۳\s*تا)',q) else 0
    if not history or history[-1].get('role')!='assistant':return text
    previous=str(history[-1].get('content',''))
    if 'یادآور' not in normalize(previous) and 'یاداور' not in normalize(previous):return text
    titles=list(dict.fromkeys(re.findall(r'«([^»]{1,150})»',previous)))
    # Without an explicit number, a reference is resolvable only if exactly
    # one reminder was named; never silently select from a list.
    if not count and len(titles)==1 and re.search(r'(?:اون|آن|همون|همان|این)',q):count=1
    if len(titles)!=count:return text
    for title in titles:
        matches=[e for e in events if normalize(e.get('title','')).casefold()==normalize(title).casefold()]
        if len(matches)!=1:return text
    return text+'\nحذف یادآورهای نام‌برده‌شده: '+'، '.join('«'+title+'»' for title in titles)

def clarification_request(history,text):
    """Bind a short answer to the immediately preceding unanswered request."""
    from ai_language import clean
    answer=clean(text).replace('\u200c',' ')
    if len(history)<2 or history[-1].get('role')!='assistant' or history[-2].get('role')!='user':return text
    # A day number is accepted only when the prior question explicitly offered
    # exactly one full date with that day. Never infer the month from a guess.
    number=re.fullmatch(r'(?:روز\s*)?(\d{1,2})(?:\s*(?:ام|اُم))?[.! ]*',answer)
    previous_question=clean(str(history[-1].get('content','')))
    if number and ('؟' in previous_question or '?' in previous_question):
        from storage import normalize,parse_j,jformat
        options=[]
        for raw in re.findall(r'(?<!\d)(1[34]\d{2}[/.-]\d{1,2}[/.-]\d{1,2})(?!\d)',normalize(previous_question)):
            try:
                day=parse_j(raw)
                if day.day==int(number.group(1)):options.append(normalize(jformat(day)))
            except ValueError:continue
        options=list(dict.fromkeys(options))
        original=str(history[-2].get('content',''))
        if not explicit_action_requested(original) and re.search(r'(?:روز|تاریخ|موعد)',clean(original)):
            for item in reversed(history[:-2][-8:]):
                candidate=str(item.get('content',''))
                if item.get('role')=='assistant' and 'نتیجه واقعی برنامه' in candidate:break
                if item.get('role')=='user' and explicit_action_requested(candidate):original=candidate;break
        if len(options)==1 and explicit_action_requested(original):return original+'\nتاریخ انتخاب‌شده: '+options[0]
        return text
    if answer in ('تایید','تأیید','بله','آره','اره','باشه','اوکی','بساز','انجام بده'):
        previous=clean(history[-1].get('content',''))
        if ('گروه' in previous and any(w in previous for w in ('تایید','تأیید','بسازم','ساخت گروه','قابل اجرا نیست'))):
            for item in reversed(history[-8:]):
                candidate=str(item.get('content',''))
                if item.get('role')=='assistant' and ('گروه' in clean(candidate)) and any(w in clean(candidate) for w in ('ساخته شد','قبلاً ساخته شده بود')):break
                if item.get('role')=='user' and 'گروه' in clean(candidate) and explicit_action_requested(candidate):return candidate+'\nادامه درخواست: '+text
    # A correction following a failed operation may fill a missing field in
    # any supported section. Never infer a retry from a question, a negation,
    # or a clearly independent action; stop at an actual completed result.
    if 'درخواست قابل اجرا نیست' in previous_question and re.search(r'(?:تاریخ|ساعت|عنوان|مبلغ|موضوع|نام|شرکت|شماره|نرخ|روز|برای فردا|برای امروز)',answer) and not re.search(r'(?:چرا|چطور|چگونه|آیا|[؟?]|نکن|نساز|نفرست|بیخیال|نمی\s*خوام)',answer) and not (explicit_action_requested(answer) and re.search(r'(?:گروه|فاکتور|یادآور|یاداور|مرخصی|پیام|مشتری)',answer)):
        window=history[-10:];parts=[]
        for item in reversed(window):
            candidate=str(item.get('content',''))
            if item.get('role')=='assistant' and 'نتیجه واقعی برنامه' in candidate:break
            if item.get('role')=='user':
                parts.append(candidate)
                if explicit_action_requested(candidate):
                    return '\nاطلاعات تکمیلی (جدیدترین مقدار اولویت دارد): '.join(list(reversed(parts))+[text])
    # Resume an unfinished meeting only when the immediately preceding
    # assistant reply asked for fields, or rejected this same pending action.
    # A conversational question must never silently retry a write.
    if not re.search(r'(?:چرا|چطور|چگونه|چجوری|آیا|؟|\?)',answer) and not re.search(r'(?:لغو|بیخیال|نکن|نساز|نفرست|نمی\s*خوام)',answer) and not any(word in answer for word in ('یادآور','یاداور','فاکتور','گروه جدید','پیام بفرست','مرخصی')):
        start=max(0,len(history)-8);window=history[start:];last=clean(history[-1].get('content',''))
        pending=('درخواست قابل اجرا نیست' in last or ('جلسه' in last and any(w in last for w in ('تاریخ','ساعت','موضوع')) and any(w in last for w in ('بگویید','بگید','مشخص','لازم'))))
        meeting_index=next((i for i in range(len(window)-1,-1,-1) if window[i].get('role')=='user' and 'جلسه' in clean(window[i].get('content','')) and explicit_action_requested(window[i].get('content',''))),None)
        if pending and meeting_index is not None:
            original=str(window[meeting_index].get('content',''));parts=[original]
            prior=window[:meeting_index]
            if re.search(r'(?:باهاش|با ایشون|با او|همون گفتگو|همان گفتگو)',clean(original)):
                for entry in reversed(prior):
                    if entry.get('role')!='assistant':continue
                    match=re.search(r'گفتگوی شخصی با\s+(.{1,100}?)\s+آماده شد',str(entry.get('content','')))
                    if match:parts.append('مقصد گفتگوی شخصی: '+match.group(1));break
            parts.extend(str(item.get('content','')) for item in window[meeting_index+1:] if item.get('role')=='user')
            parts.append(text)
            return '\nاطلاعات تکمیلی (اطلاعات تازه اصلاح اطلاعات قبلی است): '.join(parts)
    def asks_for_details(value):
        question=clean(str(value))
        return '؟' in question or '?' in question or bool(re.search(r'(?:لطفا|لطفاً|خواهش می.?کنم).{0,100}(?:مشخص|وارد|اعلام|بنویس|بگویید|بگید)',question)) or bool(re.search(r'(?<!\w)(?:چه|کدام|کدوم|چند)\s+.{1,70}(?:است|هست|باشد|باشه|می.?خواهید|می.?خوای|بگید|کنم)(?!\w)',question)) or bool(re.search(r'(?<!\w)(?:چقدره|چقدر\s+است|چیه|کیه|کجاست)(?!\w)',question))
    if not asks_for_details(history[-1].get('content','')):return text
    cancel=r'(?<!\w)(?:لغو|بیخیال|نکن|نساز|نفرست|نمی\s*خوام|نمی\s*خواهم)(?!\w)'
    def date_reply(value,question):
        q=clean(str(question));value=clean(value).replace('\u200c',' ')
        day=r'(?:1[34]\d{2}[/.-]\d{1,2}[/.-]\d{1,2}|امروز|فردا|پس\s*فردا)'
        return any(w in q for w in ('تاریخ','موعد','روز')) and bool(re.fullmatch(r'(?:برای\s+|تاریخ\s+|روز\s+)?'+day+r'(?:\s+(?:بذار|بگذار|ثبت\s+کن|تنظیم\s+کن))?[.!، ]*',value))
    if not answer or len(answer)>300 or explicit_action_requested(answer) and not date_reply(answer,history[-1].get('content','')) or answer in ('بله','آره','اره','خیر','نه','باشه','اوکی') or re.search(cancel,answer):return text
    answers=[text];index=len(history)-2
    while index>=0 and len(answers)<=4:
        if history[index].get('role')!='user':break
        original=str(history[index].get('content','')).strip()
        is_date=index>0 and date_reply(original,history[index-1].get('content',''))
        if explicit_action_requested(original) and not is_date:return original+'\nاطلاعات تکمیلی: '+'\n'.join(reversed(answers))
        cleaned=clean(original).replace('\u200c',' ')
        if not original or len(original)>300 or cleaned in ('بله','آره','اره','خیر','نه','باشه','اوکی') or re.search(cancel,cleaned):break
        answers.append(original);index-=1
        if index<0 or history[index].get('role')!='assistant' or not asks_for_details(history[index].get('content','')):break
        index-=1
    return text

def connection(owner):
    value=owner.data.get('settings',{}).get('lmstudio',{})
    from avalai_client import load_credentials
    user=(getattr(owner,'session_user',None) or {}).get('id')
    cloud=load_credentials(user) if user else {}
    if cloud.get('active'):return dict(url=cloud['url'],model=cloud['model'],auto=False,provider='avalai')
    from lan_discovery import load_profile
    profile=load_profile(getattr(owner,'base_dir',None));automatic=value.get('auto',bool(profile) and value.get('url',DEFAULT_URL) in (DEFAULT_URL,'http://'+profile['preferred_ip']+':1234/v1') if profile else False)
    return dict(url=value.get('url',DEFAULT_URL),model=GEMMA_MODEL,auto=automatic)

def make_client(owner,timeout=120,cfg=None,secret=None):
    cfg=cfg or connection(owner)
    if cfg.get('provider')=='avalai':
        from avalai_client import AvalAIClient,load_credentials
        key=secret if secret is not None else load_credentials((owner.session_user or {}).get('id')) .get('key','')
        return AvalAIClient(cfg['url'],key,timeout)
    if cfg.get('auto'):
        client=getattr(owner,'auth_client',None) or getattr(getattr(owner,'org',None),'client',None)
        return LMClient.company(client,timeout)
    return LMClient(cfg['url'],token() if secret is None else secret,timeout)

def token():
    from local_vault import load
    return (load(app_dir()/'lmstudio-token.dpapi',{}) or {}).get('token','')

def emit(signal,*args):
    try:signal.emit(*args)
    except RuntimeError:pass  # The dialog/window may have been closed meanwhile.

class Bridge(QObject):
    piece=Signal(int,str);done=Signal(int,object,object);models=Signal(int,object)

class LMStudioSettings(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.bridge=Bridge(self);self.bridge.done.connect(self.received);self.worker=None;v=QVBoxLayout(self);note=QLabel('مدل را در LM Studio بارگذاری و از بخش Developer، Server را روشن کنید. نشانی پیش‌فرض برای همین کامپیوتر است. متن گفتگو و، در صورت فعال‌بودن دسترسی دستیار، خلاصه کارها و یادآورهای مجاز این حساب به همین نشانی فرستاده می‌شوند.');note.setWordWrap(True);v.addWidget(note);f=QFormLayout();v.addLayout(f);cfg=connection(owner);local=owner.data.get('settings',{}).get('lmstudio',{});self.url=QLineEdit(local.get('url',DEFAULT_URL));self.url.setLayoutDirection(Qt.LeftToRight);f.addRow('نشانی سرویس',self.url);self.model=QComboBox();self.model.setEditable(True);self.model.setMinimumWidth(200)
        self.model.addItem('کارنامه',GEMMA_MODEL)
        from avalai_client import load_credentials,DEFAULT_AVALAI_URL
        user=(owner.session_user or {}).get('id');cloud=load_credentials(user) if user else {}
        self.cloud_enabled=QCheckBox('استفاده از اول‌ای‌آی با کلید شخصی');self.cloud_enabled.setToolTip('خاموش: مدل Gemma؛ روشن: اول‌ای‌آی');self.cloud_enabled.setChecked(bool(cloud.get('active')));f.addRow(self.cloud_enabled)
        self.cloud_url=QLineEdit(cloud.get('url',DEFAULT_AVALAI_URL));self.cloud_url.setLayoutDirection(Qt.LeftToRight);f.addRow('نشانی اول‌ای‌آی',self.cloud_url)
        self.cloud_model=QLineEdit(cloud.get('model',''));self.cloud_model.setLayoutDirection(Qt.LeftToRight);self.cloud_model.setPlaceholderText('Model ID');f.addRow('شناسه مدل',self.cloud_model)
        self.cloud_key=QLineEdit();self.cloud_key.setEchoMode(QLineEdit.Password);self.cloud_key.setPlaceholderText('خالی: استفاده از کلید ذخیره‌شده');f.addRow('کلید API شخصی',self.cloud_key)
        self.cloud_clear=QCheckBox('حذف کلید شخصی ذخیره‌شده');f.addRow(self.cloud_clear)
        privacy=QLabel('با انتخاب اول‌ای‌آی، متن گفتگو و اطلاعات مجاز فعال‌شده برای پاسخ به آن سرویس ارسال می‌شوند.');privacy.setWordWrap(True);f.addRow(privacy)
        self.form=f;self.privacy=privacy;self.cloud_enabled.toggled.connect(self.cloud_changed)
        f.addRow('دستیار',self.model);self.automatic=QCheckBox('استفاده خودکار از دستیار شبکه شرکت');self.automatic.setChecked(local.get('auto',cfg['auto']));f.addRow(self.automatic);self.key=QLineEdit();self.key.setEchoMode(QLineEdit.Password);self.key.setPlaceholderText('اختیاری؛ اگر LM Studio احراز هویت می‌خواهد');f.addRow('کلید دسترسی',self.key);self.clear_key=QCheckBox('کلید ذخیره‌شده این حساب پاک شود');f.addRow(self.clear_key);self.check=QPushButton('آزمایش اتصال');self.check.clicked.connect(self.probe);v.addWidget(self.check);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);v.addWidget(self.status);hint=QLabel('در حالت خودکار، دستیار روی میزبان شرکت اجرا می‌شود و روی این دستگاه نصب LM Studio لازم نیست. برای اتصال دلخواه، حالت خودکار را خاموش و نشانی را ویرایش کنید. کلید اتصال با حفاظت حساب ویندوز نگهداری می‌شود.');hint.setWordWrap(True);v.addWidget(hint);v.addStretch();self.automatic.toggled.connect(self.auto_changed)
        can=allowed(owner,'assistant','configure')
        for w in (self.url,self.model,self.key,self.clear_key,self.automatic):w.setEnabled(can)
        self.cloud_enabled.setEnabled(allowed(owner,'assistant','use'));self.check.setEnabled(allowed(owner,'assistant','use'))
        self.model.setEditable(False);self.model.setEnabled(False);f.setRowVisible(self.model,False)
        self.provider_saved=dict(provider=cfg.get('provider','gemma'),model=cfg['model'],auto=bool(cfg.get('auto')))
        self.provider_indicator=QLabel();self.provider_indicator.setWordWrap(True);self.provider_indicator.setTextFormat(Qt.PlainText);self.provider_indicator.setObjectName('Sub');v.insertWidget(1,self.provider_indicator)
        self.advanced=QCheckBox('تنظیمات پیشرفته اتصال');v.insertWidget(v.count()-1,self.advanced);self.advanced.toggled.connect(lambda _:self.cloud_changed(self.cloud_enabled.isChecked()))
        self.cloud_model.textChanged.connect(self.update_provider_indicator);self.automatic.toggled.connect(self.update_provider_indicator)
        self.auto_changed(self.automatic.isChecked());self.cloud_changed(self.cloud_enabled.isChecked())
        note.setText('سرویس موردنظر را انتخاب کنید. برای Gemma، برنامه LM Studio و سرور آن باید روی میزبان روشن باشند.')
        self.destroyed.connect(self.stop)
    def auto_changed(self,active):
        editable=allowed(self.owner,'assistant','configure') and not active
        for w in (self.url,self.key,self.clear_key):w.setEnabled(editable)
    def cloud_changed(self,active):
        enabled=allowed(self.owner,'assistant','use')
        for w in (self.cloud_url,self.cloud_model,self.cloud_key):w.setEnabled(active and enabled)
        self.cloud_clear.setEnabled(enabled)
        advanced=self.advanced.isChecked()
        for w in (self.cloud_model,self.cloud_key,self.privacy):self.form.setRowVisible(w,active)
        for w in (self.cloud_url,self.cloud_clear):self.form.setRowVisible(w,active and advanced)
        for w in (self.url,self.automatic,self.key,self.clear_key):self.form.setRowVisible(w,not active and advanced)
        self.advanced.setText('تنظیمات پیشرفته اتصال')
        self.status.setText('اول‌ای‌آی: شناسه مدل و کلید شخصی را وارد کنید.' if active else 'Gemma از LM Studio یا میزبان شرکت استفاده می‌کند.')
        self.update_provider_indicator()
    def update_provider_indicator(self,*_):
        def describe(config):
            if config['provider']=='avalai':return 'اول‌ای‌آی با کلید شخصی'+(' · '+config['model'] if config['model'] else '')
            return 'Gemma · '+('میزبان شبکه شرکت' if config['auto'] else 'LM Studio')
        selected=dict(provider='avalai' if self.cloud_enabled.isChecked() else 'gemma',model=self.cloud_model.text().strip() if self.cloud_enabled.isChecked() else GEMMA_MODEL,auto=False if self.cloud_enabled.isChecked() else self.automatic.isChecked())
        saved=self.provider_saved
        changed=selected['provider']!=saved['provider'] or (selected['provider']=='avalai' and selected['model']!=saved['model']) or (selected['provider']=='gemma' and selected['auto']!=saved['auto'])
        self.provider_indicator.setText('سرویس ذخیره‌شده: '+describe(saved)+('\nانتخاب جدید پس از ذخیره: '+describe(selected) if changed else ''))
    def stop(self,*_):
        if self.worker:self.worker.cancel()
    def values(self):
        if not allowed(self.owner,'assistant','configure'):return connection(self.owner)
        return dict(url=base_url(self.url.text()),model=GEMMA_MODEL,auto=self.automatic.isChecked())
    def cloud_values(self):
        from avalai_client import avalai_url
        model=self.cloud_model.text().strip()
        if not model or len(model)>300:raise ValueError('شناسه مدل را وارد کنید.')
        return dict(url=avalai_url(self.cloud_url.text()),model=model,auto=False,provider='avalai')
    def commit(self):
        if not allowed(self.owner,'assistant','use'):return
        from local_vault import save
        from avalai_client import load_credentials,credential_path
        user=(self.owner.session_user or {}).get('id');cloud=load_credentials(user) if user else {}
        if self.cloud_clear.isChecked():
            if self.cloud_enabled.isChecked():raise ValueError('برای حذف کلید، ابتدا استفاده از اول‌ای‌آی را خاموش کنید.')
            if user:save(credential_path(user),{})
            cloud={}
        if self.cloud_enabled.isChecked():
            cfg=self.cloud_values();key=self.cloud_key.text().strip() or cloud.get('key','')
            if not key:raise ValueError('کلید API شخصی را وارد کنید.')
            save(credential_path(user),dict(active=True,key=key,url=cfg['url'],model=cfg['model']))
        elif cloud:save(credential_path(user),dict(cloud,active=False))
        if allowed(self.owner,'assistant','configure'):
            if self.key.text().strip():save(app_dir()/'lmstudio-token.dpapi',dict(token=self.key.text().strip()))
            elif self.clear_key.isChecked():save(app_dir()/'lmstudio-token.dpapi',{})
    def probe(self):
        if not gate(self.owner,'assistant','use'):return
        try:
            cfg=self.cloud_values() if self.cloud_enabled.isChecked() else self.values()
            if cfg.get('provider')=='avalai':
                from avalai_client import load_credentials
                secret=self.cloud_key.text().strip() or load_credentials((self.owner.session_user or {}).get('id')).get('key','')
            else:secret=self.key.text().strip() or ('' if self.clear_key.isChecked() else token())
            self.worker=make_client(self.owner,12,cfg,secret)
        except (ValueError,OSError) as exc:self.status.setText(str(exc));return
        self.check.setEnabled(False);self.status.setText('در حال بررسی اتصال…');client=self.worker
        def work():
            try:emit(self.bridge.done,0,client.models(),None)
            except Exception as exc:emit(self.bridge.done,0,None,exc)
            finally:client.close()
        threading.Thread(target=work,daemon=True).start()
    def received(self,job,models,error):
        self.worker=None;self.check.setEnabled(allowed(self.owner,'assistant','use'))
        if error:self.status.setText(str(error));return
        selected=self.cloud_model.text().strip() if self.cloud_enabled.isChecked() else GEMMA_MODEL
        self.status.setText('اتصال برقرار است و مدل انتخاب‌شده پیدا شد.' if selected in models else 'اتصال برقرار است؛ شناسه مدل در فهرست دریافت‌شده پیدا نشد.')

class LMStudioDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('تنظیم سرویس هوش مصنوعی');self.setLayoutDirection(Qt.RightToLeft);self.resize(640,440);v=QVBoxLayout(self);self.panel=LMStudioSettings(owner);v.addWidget(self.panel);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Save).setText('ذخیره اتصال');b.button(QDialogButtonBox.Cancel).setText('بستن');b.accepted.connect(self.save);b.rejected.connect(self.reject);v.addWidget(b)
    def save(self):
        if not gate(self.owner,'assistant','use'):return
        try:
            if not allowed(self.owner,'assistant','configure'):self.panel.commit();self.accept();return
            cfg=self.panel.values();self.panel.commit();old=self.owner.data['settings'].get('lmstudio');self.owner.data['settings']['lmstudio']=cfg
            try:self.owner.persist()
            except Exception:
                if old is None:self.owner.data['settings'].pop('lmstudio',None)
                else:self.owner.data['settings']['lmstudio']=old
                raise
            self.accept()
        except Exception as exc:QMessageBox.warning(self,'تنظیم اتصال',str(exc))
    def done(self,result):self.panel.stop();super().done(result)

class PromptEdit(QPlainTextEdit):
    submitted=Signal()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:self.submitted.emit();event.accept();return
        super().keyPressEvent(event)

class PlanPreview(QDialog):
    def __init__(self,owner,items):
        super().__init__(owner);self.items=items;self.result_items=[];self.setWindowTitle('بازبینی برنامه و یادآورها');self.setLayoutDirection(Qt.RightToLeft);self.resize(900,510);v=QVBoxLayout(self);note=QLabel('این موارد پیشنهاد مدل‌اند. عنوان، تاریخ و فاصله یادآوری را بررسی یا ویرایش کنید. فقط ردیف‌های انتخاب‌شده، پس از زدن دکمه ثبت، به تقویم شخصی شما اضافه می‌شوند.');note.setWordWrap(True);v.addWidget(note);self.table=QTableWidget(len(items),5);self.table.setHorizontalHeaderLabels(['ثبت','عنوان','تاریخ شمسی','روزهای قبل از موعد','تکرار']);self.table.verticalHeader().hide();self.table.setEditTriggers(QAbstractItemView.AllEditTriggers);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.table.setColumnWidth(0,40);self.table.setColumnWidth(2,125);self.table.setColumnWidth(3,170);self.table.setColumnWidth(4,130);v.addWidget(self.table,1)
        for i,item in enumerate(items):
            check=QTableWidgetItem();check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);check.setCheckState(Qt.Checked);self.table.setItem(i,0,check)
            for j,text in enumerate((item['title'],item['date_jalali'],', '.join(map(str,item['lead_days']))),1):cell=QTableWidgetItem(text);cell.setToolTip(item['notes']);self.table.setItem(i,j,cell)
            combo=QComboBox();combo.addItems(REPEAT);combo.setCurrentText(item['recurrence']);self.table.setCellWidget(i,4,combo)
        self.error=QLabel();self.error.setWordWrap(True);v.addWidget(self.error);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Save).setText('ثبت موارد انتخاب‌شده در تقویم');b.button(QDialogButtonBox.Cancel).setText('انصراف');b.accepted.connect(self.validate);b.rejected.connect(self.reject);v.addWidget(b)
    def validate(self):
        try:
            result=[]
            for i,item in enumerate(self.items):
                if self.table.item(i,0).checkState()!=Qt.Checked:continue
                result.append(validate_item(dict(item,title=self.table.item(i,1).text(),date_jalali=self.table.item(i,2).text(),lead_days=self.table.item(i,3).text(),recurrence=self.table.cellWidget(i,4).currentText())))
            if not result:raise ValueError('حداقل یک یادآور انتخاب کنید.')
            self.result_items=result;self.accept()
        except ValueError as exc:self.error.setText(str(exc))

class AIChatPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.history=[];self.items=[];self.proposals=[];self.busy=False;self.worker=None;self.job=0;self.reply_index=None;self.identity=self.user_id();self.scope_stamp=None;self.app_actions=[];self.app_context=None;self.applying=False;self.bridge=Bridge(self);self.bridge.piece.connect(self.piece);self.bridge.done.connect(self.finished);self.bridge.models.connect(self.set_models);v=QVBoxLayout(self);v.setContentsMargins(16,12,16,12);top=QHBoxLayout();title=QLabel('کارنامه');title.setObjectName('Hero');top.addWidget(title);top.addStretch();self.settings_button=QPushButton('تنظیم اتصال');iconize(self.settings_button,'settings');self.settings_button.clicked.connect(self.settings);top.addWidget(self.settings_button);self.new_button=QPushButton('گفتگوی تازه');self.new_button.clicked.connect(self.reset);top.addWidget(self.new_button);v.addLayout(top);options=QHBoxLayout();self.model=QComboBox();self.model.setEditable(True);self.model.setMinimumWidth(180);cfg=connection(owner)
        if cfg['model']:self.model.addItem(cfg['model'])
        from brand import logo
        top.insertWidget(0,logo('کارنامه',30))
        self.model.setEditable(False);self.model.setEnabled(False)
        self.model.hide();self.connect_button=QPushButton('بررسی اتصال');self.connect_button.clicked.connect(self.probe);options.addWidget(self.connect_button);self.mode=QComboBox();self.mode.addItem('گفتگو','chat');self.mode.addItem('برنامه‌ریزی شخصی','plan');self.mode.addItem('دستیار برنامه','app');self.mode.setCurrentIndex(2);self.mode.currentIndexChanged.connect(lambda:self.apply_access());options.addStretch();v.addLayout(options);self.status=QLabel('درخواست خود را بنویسید؛ کارنامه بر اساس دسترسی حساب شما اقدام می‌کند.');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);v.addWidget(self.status);self.context_check=QCheckBox('دسترسی کارنامه به تقویم، کارها و خلاصه اسناد مالی، فاکتورها و چک‌های مجاز من');self.context_check.setChecked(owner.data['settings'].get('ai_app_access',True));self.context_check.toggled.connect(self.context_changed);v.addWidget(self.context_check);self.transcript=QTextBrowser();self.transcript.setObjectName('AssistantTranscript');self.transcript.setOpenExternalLinks(False);self.transcript.setOpenLinks(False);v.addWidget(self.transcript,1);self.plan_button=QPushButton('ثبت برنامه در تقویم');self.plan_button.clicked.connect(self.preview);self.plan_button.setEnabled(False);v.addWidget(self.plan_button);self.plan_button.hide();self.prompt=PromptEdit();self.prompt.setObjectName('AssistantPrompt');self.prompt.setPlaceholderText('از کارنامه بپرسید یا درخواست خود را بنویسید…');self.prompt.setMaximumHeight(82);self.prompt.submitted.connect(self.send);composer=QFrame();composer.setObjectName('AssistantComposer');composer_layout=QVBoxLayout(composer);composer_layout.setContentsMargins(10,8,10,8);composer_layout.addWidget(self.prompt);v.addWidget(composer);self.install_prompt_templates(v);row=QHBoxLayout();self.provider_button=QPushButton('مدل و اتصال');self.provider_button.setAccessibleName('تنظیم مدل و اتصال دستیار');self.provider_button.clicked.connect(self.settings);row.addWidget(self.provider_button);row.addWidget(self.mode);row.addStretch();self.send_button=QPushButton();self.send_button.setIcon(send_arrow_icon());self.send_button.setAccessibleName('ارسال پیام');self.send_button.setToolTip('ارسال پیام');self.send_button.setFixedSize(38,38);self.send_button.setProperty('flowNative',True);self.send_button.setObjectName('Primary');self.send_button.clicked.connect(self.send);row.addWidget(self.send_button);schedule=QPushButton('زمان‌بندی درخواست');iconize(schedule,'meeting');schedule.clicked.connect(self.schedule_prompt);row.addWidget(schedule);scheduled=QPushButton('درخواست‌های زمان‌بندی‌شده');iconize(scheduled,'open');scheduled.clicked.connect(self.show_scheduled_prompts);row.addWidget(scheduled);self.stop_button=QPushButton('توقف پاسخ');self.stop_button.clicked.connect(self.stop);self.stop_button.hide();row.addWidget(self.stop_button);row.addStretch();hint=QLabel('حافظه شخصی در همین رایانه ذخیره می‌شود.');hint.setObjectName('Sub');hint.hide();row.addWidget(hint);composer_layout.addLayout(row);self.render_timer=QTimer(self);self.render_timer.setSingleShot(True);self.render_timer.setInterval(80);self.render_timer.timeout.connect(self.render);self.scheduled_job=None;self.schedule_users=set();self.schedule_timer=QTimer(self);self.schedule_timer.setInterval(5000);self.schedule_timer.timeout.connect(self.process_scheduled_prompts);self.schedule_timer.start();self.destroyed.connect(self.cancel);self.apply_access();self.render()
        self.context_check.hide();self.memory_check.hide();self.erase_memory_button.hide();privacy=QPushButton('تنظیمات دستیار');privacy_menu=QMenu(privacy);access_action=privacy_menu.addAction('دسترسی به اطلاعات برنامه');access_action.setCheckable(True);access_action.setChecked(self.context_check.isChecked());access_action.toggled.connect(self.context_check.setChecked);self.context_check.toggled.connect(access_action.setChecked);memory_action=privacy_menu.addAction('حافظه شخصی');memory_action.setCheckable(True);memory_action.setChecked(self.memory_check.isChecked());memory_action.toggled.connect(self.memory_check.setChecked);self.memory_check.toggled.connect(memory_action.setChecked);privacy_menu.addAction('پاک کردن حافظه',self.clear_memory);privacy.setMenu(privacy_menu);top.addWidget(privacy);self.new_button.clicked.disconnect(self.reset);self.new_button.clicked.connect(self.new_conversation)
        requests_button=QPushButton('درخواست‌های اخیر');requests_button.setToolTip('مشاهده وضعیت درخواست‌ها و ادامه دستی آنها');requests_button.clicked.connect(self.show_request_history);top.addWidget(requests_button)
        self.restore_conversation()
    def schedule_prompt(self):
        if not gate(self.owner,'assistant','use'):return
        text=self.prompt.toPlainText().strip()
        if not text:self.status.setText('ابتدا متن درخواست را بنویسید.');return
        if self.mode.currentData() in ('app','plan') and self.select_placeholder():self.status.setText('ابتدا موارد داخل کروشه را تکمیل کنید.');return
        from chat_ui import ScheduleDialog
        dialog=ScheduleDialog(self)
        if dialog.exec()!=QDialog.Accepted:return
        try:
            from ai_schedule import add
            add(self.user_id(),text,self.mode.currentData(),dialog.due_at);self.prompt.clear()
            if self.schedule_changed():self.status.setText('درخواست زمان‌بندی شد؛ برای ارسال، برنامه و حساب شما باید باز باشند.')
        except Exception as exc:self.status.setText(str(exc))
    def schedule_changed(self):
        import uuid
        self.owner.data['assistant_schedule_revision']=uuid.uuid4().hex
        try:self.owner.persist();return True
        except Exception as exc:self.status.setText('درخواست ثبت شد ولی وضعیت پشتیبان به‌روز نشد: '+str(exc));return False
    def show_scheduled_prompts(self):
        try:
            from ai_schedule import read,transition,reschedule
            user=self.user_id();items=[x for x in read(user) if x.get('status') in ('pending','running','failed','interrupted')]
            dialog=QDialog(self);dialog.setWindowTitle('درخواست‌های زمان‌بندی‌شده من');dialog.setLayout(QVBoxLayout());table=QTableWidget(len(items),3);table.setHorizontalHeaderLabels(['زمان تهران','وضعیت','درخواست']);table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch);dialog.layout().addWidget(table)
            from datetime import datetime,timezone,timedelta
            import jdatetime
            for i,item in enumerate(items):
                when=datetime.fromisoformat(item['due_at']).astimezone(timezone(timedelta(hours=3,minutes=30)));date=jdatetime.date.fromgregorian(date=when.date()).strftime('%Y/%m/%d')+' '+when.strftime('%H:%M');state={'pending':'در انتظار','running':'در حال اجرا','failed':'ناموفق','interrupted':'متوقف‌شده؛ نیازمند بررسی'}[item['status']]
                for j,value in enumerate((fa(date),state,item['prompt'])):table.setItem(i,j,QTableWidgetItem(value))
            buttons=QDialogButtonBox(QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Cancel).setText('بستن');choice={};remove=buttons.addButton('لغو انتخاب‌شده',QDialogButtonBox.ActionRole);change=buttons.addButton('تغییر زمان',QDialogButtonBox.ActionRole);remove.clicked.connect(lambda:(choice.update(action='cancel'),dialog.accept()));change.clicked.connect(lambda:(choice.update(action='reschedule'),dialog.accept()));buttons.rejected.connect(dialog.reject);dialog.layout().addWidget(buttons);dialog.resize(660,360)
            if dialog.exec()==QDialog.Accepted and 0<=table.currentRow()<len(items):
                item=items[table.currentRow()]
                if choice.get('action')=='reschedule':
                    from chat_ui import ScheduleDialog
                    picker=ScheduleDialog(self)
                    if picker.exec()==QDialog.Accepted:
                        reschedule(user,item['id'],picker.due_at)
                        if self.schedule_changed():self.status.setText('زمان درخواست تغییر کرد.')
                elif not transition(user,item['id'],('pending','failed','interrupted'),'cancelled'):self.status.setText('درخواست در حال اجرا قابل لغو نیست.')
                elif self.schedule_changed():self.status.setText('درخواست زمان‌بندی‌شده لغو شد.')
        except Exception as exc:self.status.setText(str(exc))
    def scheduled_finish(self,status):
        if not self.scheduled_job:return
        from ai_schedule import transition
        user,id=self.scheduled_job;self.scheduled_job=None
        previous=getattr(self,'scheduled_mode_previous',None);self.scheduled_mode_previous=None
        if previous and user==self.user_id() and self.mode.currentData()==previous[1]:self.mode.setCurrentIndex(previous[0])
        try:saved=transition(user,id,('running',),status)
        except Exception as exc:self.status.setText('وضعیت درخواست زمان‌بندی‌شده ذخیره نشد: '+str(exc));return
        if saved and user==self.user_id():self.schedule_changed()
        if saved and status in ('completed','failed') and user==self.user_id() and hasattr(self.owner,'popup'):
            try:self.owner.popup('پاسخ درخواست زمان‌بندی‌شده آماده است.' if status=='completed' else 'درخواست زمان‌بندی‌شده انجام نشد؛ بخش دستیار را بررسی کنید.',title='دستیار کارنامه')
            except Exception:pass
    def process_scheduled_prompts(self):
        if self.busy or self.applying or self.scheduled_job or self.prompt.toPlainText().strip() or getattr(self.owner,'_locking',False) or not allowed(self.owner,'assistant','use'):return
        user=self.user_id()
        if user=='standalone':return
        try:
            from ai_schedule import read,recover,transition
            from datetime import datetime,timezone
            if user not in self.schedule_users:recover(user);self.schedule_users.add(user)
            now=datetime.now(timezone.utc);items=read(user);due=next((x for x in sorted(items,key=lambda x:x['due_at']) if x.get('status')=='pending' and datetime.fromisoformat(x['due_at'])<=now),None)
            if not due or not transition(user,due['id'],('pending',),'running'):return
            self.scheduled_job=(user,due['id']);self.scheduled_mode_previous=(self.mode.currentIndex(),due['mode']);self.mode.setCurrentIndex(self.mode.findData(due['mode']));self.prompt.setPlainText(due['prompt']);self.send()
            if not self.busy:self.scheduled_finish('failed')
        except Exception as exc:self.status.setText('بررسی درخواست زمان‌بندی‌شده انجام نشد: '+str(exc))
    def context_changed(self,value):
        draft=self.prompt.toPlainText();self.owner.data['settings']['ai_app_access']=value;self.reset();self.prompt.setPlainText(draft);self.status.setText('دسترسی به اطلاعات مجاز برنامه '+('فعال' if value else 'غیرفعال')+' شد؛ گفتگوی تازه آغاز شد.')
        try:self.owner.persist()
        except Exception as exc:self.status.setText('این انتخاب در نشست فعلی اعمال شد؛ ذخیره تنظیمات انجام نشد: '+str(exc))
    def install_prompt_templates(self,layout):
        from ai_prompt_templates import TEMPLATES
        from PySide6.QtGui import QAction
        self.template_controls=[(template,QAction(template['title'],self)) for template in TEMPLATES];self.template_buttons={};self.more_templates=QPushButton(self);self.more_templates.hide()
        row=QHBoxLayout();self.suggestion_label=QLabel('پیشنهاد:');self.suggestion_label.setObjectName('Sub');row.addWidget(self.suggestion_label);self.suggest_buttons=[]
        for _ in range(3):
            button=QPushButton();button.setFixedHeight(30);button.setStyleSheet('font-size:11px;padding:4px 8px;text-align:center;');button.clicked.connect(lambda checked=False,b=button:self.fill_template(b.property('templateKey')));row.addWidget(button);self.suggest_buttons.append(button)
        row.addStretch();layout.addLayout(row);self.prompt.textChanged.connect(self.update_suggestions);self.suggestion_label.hide()
        memory=QHBoxLayout();self.memory_check=QCheckBox('حافظه شخصی');self.memory_check.setToolTip('سابقه روی این رایانه رمزگذاری می‌شود و بخش مرتبط به مدل انتخاب‌شده ارسال می‌شود.');self.memory_check.setChecked(bool(self.user_id()!='standalone' and self.owner.data.setdefault('assistant_memory_options',{}).get(self.user_id(),True)));self.memory_check.toggled.connect(self.memory_changed);memory.addWidget(self.memory_check)
        erase=QPushButton('پاک کردن حافظه');self.erase_memory_button=erase;erase.clicked.connect(self.clear_memory);memory.addWidget(erase);memory.addStretch();layout.addLayout(memory);self.update_suggestions()
    def memory_changed(self,enabled):
        if self.user_id()=='standalone':return
        self.owner.data.setdefault('assistant_memory_options',{})[self.user_id()]=enabled
        try:self.owner.persist()
        except Exception as exc:self.status.setText('ذخیره تنظیم حافظه انجام نشد: '+str(exc))
    def clear_memory(self):
        if self.user_id()=='standalone':self.status.setText('ابتدا وارد حساب شوید.');return
        if QMessageBox.question(self,'پاک کردن حافظه','حافظه شخصی دستیار در این رایانه پاک شود؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:
            from ai_memory import clear
            clear(self.user_id());self.history=[];self.status.setText('حافظه شخصی پاک شد.')
        except Exception as exc:self.status.setText('پاک کردن حافظه انجام نشد: '+str(exc))
    def update_suggestions(self):
        from ai_prompt_templates import suggest
        text=self.prompt.toPlainText()
        matches=suggest(text,self.owner) if len(text.split())>=2 and allowed(self.owner,'assistant','use') else []
        self.suggestion_label.setVisible(bool(matches))
        for i,button in enumerate(self.suggest_buttons):
            visible=i<len(matches);button.setVisible(visible)
            if visible:button.setText(matches[i]['title']);button.setProperty('templateKey',matches[i]['key']);button.setToolTip(matches[i]['text'])
    def fill_template(self,key):
        if self.applying or not allowed(self.owner,'assistant','use'):return
        from ai_prompt_templates import TEMPLATES,available
        item=next((t for t in TEMPLATES if t['key']==key),None)
        if not item or not available(self.owner,item):return
        self.mode.setCurrentIndex(self.mode.findData(item.get('mode','app')));self.prompt.selectAll();self.prompt.insertPlainText(item['text']);self.prompt.setFocus();self.select_placeholder();self.status.setText('متن پیشنهادی در کادر قرار گرفت؛ آن را تکمیل و سپس ارسال کنید.')
    def select_placeholder(self):
        import re
        from PySide6.QtGui import QTextCursor
        match=re.search(r'\[[^\]\n]{1,100}\]',self.prompt.toPlainText())
        if match:
            cursor=self.prompt.textCursor();cursor.setPosition(match.start());cursor.setPosition(match.end(),QTextCursor.KeepAnchor);self.prompt.setTextCursor(cursor);return True
        return False
    def user_id(self):return (self.owner.session_user or {}).get('id','standalone')
    def restore_conversation(self):
        if self.user_id()=='standalone' or not self.memory_check.isChecked():return
        try:
            from ai_memory import read_conversation
            self.history=read_conversation(self.user_id(),self.scope_stamp);self.items=[dict(role=x['role'],content=x['content']) for x in self.history]
            if self.history:self.status.setText('گفتگوی قبلی بازیابی شد؛ هیچ عملی خودکار اجرا نشده است.')
            self.render()
        except Exception as exc:self.status.setText('بازیابی گفتگو انجام نشد: '+str(exc))
    def store_conversation(self):
        if self.user_id()=='standalone' or not self.memory_check.isChecked():return
        try:
            from ai_memory import save_conversation
            save_conversation(self.user_id(),self.history,self.scope_stamp)
        except Exception as exc:self.status.setText('ذخیره گفتگو انجام نشد: '+str(exc))
    def mark_request_interrupted(self):
        if self.user_id()=='standalone' or not self.memory_check.isChecked() or not getattr(self,'pending_request_id',None):return
        try:
            from ai_memory import save_request
            save_request(self.user_id(),self.scope_stamp,self.pending_request_id,getattr(self,'pending_journal_request',''),'interrupted','نتیجه عملیات تأیید نشده است؛ قبل از تلاش دوباره وضعیت برنامه را بررسی کنید.')
        except Exception:pass
    def show_request_history(self):
        from PySide6.QtWidgets import QListWidget,QListWidgetItem
        from storage import normalize
        dialog=QDialog(self);dialog.setWindowTitle('درخواست‌های اخیر');dialog.resize(680,440);layout=QVBoxLayout(dialog)
        note=QLabel('وضعیت اجرا بر اساس نتیجه برنامه ثبت می‌شود؛ ادامه دادن چیزی را خودکار اجرا نمی‌کند.');note.setWordWrap(True);layout.addWidget(note)
        rows=[]
        if self.user_id()!='standalone' and self.memory_check.isChecked():
            try:
                from ai_memory import read_requests
                labels={'processing':'در حال پردازش یا ناتمام؛ نتیجه را بررسی کنید','interrupted':'متوقف‌شده؛ نتیجه را بررسی کنید','awaiting':'منتظر اطلاعات','answered':'پاسخ داده‌شده','completed':'انجام‌شده','failed':'انجام‌نشده','partial':'انجام ناقص'}
                rows=[(r.get('request',''),labels.get(r.get('status'),'نامشخص'),r.get('detail','')) for r in read_requests(self.user_id(),self.scope_stamp)]
            except Exception as exc:note.setText('خواندن درخواست‌ها ممکن نشد: '+str(exc))
        listing=QListWidget();layout.addWidget(listing)
        for text,status,answer in reversed(rows):
            item=QListWidgetItem(status+'  ·  '+text[:110]);item.setToolTip(answer[:1000]);listing.addItem(item)
        button=QPushButton('قرار دادن درخواست در کادر');layout.addWidget(button)
        def choose():
            index=listing.currentRow();ordered=list(reversed(rows))
            if not 0<=index<len(ordered):return
            self.prompt.setPlainText(ordered[index][0]);self.prompt.setFocus();dialog.accept()
        button.clicked.connect(choose);dialog.exec()
    def current(self,job):return job==self.job and self.identity==self.user_id() and not getattr(self.owner,'_locking',False)
    def apply_access(self):
        actor=self.owner.session_user or {};stamp=__import__('json').dumps(dict(id=actor.get('id'),role=actor.get('global_role'),memberships=actor.get('memberships',[])),sort_keys=True)
        old=self.scope_stamp;self.scope_stamp=stamp
        if old is not None and old!=stamp:
            changed_user=self.identity!=self.user_id();self.reset()
            if changed_user:self.restore_conversation()
            return
        available=not self.busy and not self.applying;self.send_button.setEnabled(available and allowed(self.owner,'assistant','use'));self.connect_button.setEnabled(available and allowed(self.owner,'assistant','use'));self.settings_button.setVisible(allowed(self.owner,'assistant','use'));self.settings_button.setEnabled(available);self.new_button.setEnabled(not self.applying);self.prompt.setEnabled(not self.applying)
        self.context_check.blockSignals(True);active=self.mode.currentData()=='app' and allowed(self.owner,'assistant','context');self.context_check.setChecked(active and self.owner.data['settings'].get('ai_app_access',True));self.context_check.setEnabled(active and available);self.context_check.blockSignals(False)
        self.plan_button.setText('بازبینی و اعمال تغییرات' if self.app_actions else 'بازبینی و ثبت پیشنهاد در تقویم');self.plan_button.setEnabled(available and allowed(self.owner,'assistant','use') and (bool(self.app_actions) or bool(self.proposals) and allowed(self.owner,'calendar','create')))
        from ai_prompt_templates import available
        secondary=False
        for template,control in self.template_controls:
            visible=available(self.owner,template);control.setVisible(visible);control.setEnabled(not self.applying and allowed(self.owner,'assistant','use'))
            if visible and not template.get('primary'):secondary=True
        self.more_templates.hide();self.update_suggestions()
        self.memory_check.blockSignals(True);self.memory_check.setEnabled(self.user_id()!='standalone');self.memory_check.setChecked(bool(self.user_id()!='standalone' and self.owner.data.setdefault('assistant_memory_options',{}).get(self.user_id(),True)));self.memory_check.blockSignals(False)
        if self.identity!=self.user_id():self.reset();self.restore_conversation()
        elif self.busy and not allowed(self.owner,'assistant','use'):self.stop()
    def showEvent(self,event):super().showEvent(event);self.apply_access();self.render()
    def settings(self):
        if not gate(self.owner,'assistant','use'):return
        d=LMStudioDialog(self.owner)
        if d.exec()==QDialog.Accepted:
            draft=self.prompt.toPlainText();self.reset();self.prompt.setPlainText(draft)
            cfg=connection(self.owner);self.model.clear()
            if cfg['model']:self.model.addItem(cfg['model'])
            self.status.setText('تنظیم اتصال ذخیره شد؛ برای دریافت مدل‌ها اتصال را بزنید.')
    def cancel(self,*_):
        if self.worker:self.worker.cancel()
    def stop(self):
        if self.busy:self.mark_request_interrupted()
        self.scheduled_finish('interrupted')
        if not self.prompt.toPlainText().strip() and getattr(self,'pending_prompt',''):self.prompt.setPlainText(self.pending_prompt)
        self.cancel();self.job+=1;self.worker=None;self.busy=False;self.stop_button.hide();self.proposals=[];self.app_actions=[];self.app_context=None;self.status.setText('دریافت متوقف شد. پاسخ ناقص، وارد ادامه گفتگو یا تقویم نمی‌شود.');self.apply_access();self.render()
    def reset(self):
        self.scheduled_finish('interrupted')
        self.cancel();self.job+=1;self.worker=None;self.busy=False;self.history=[];self.items=[];self.proposals=[];self.app_actions=[];self.app_context=None;self.reply_index=None;self.pending_prompt='';self.identity=self.user_id();self.stop_button.hide();self.prompt.clear();self.status.setText('گفتگوی تازه؛ دسترسی به کارها از گزینه مربوط قابل تنظیم است.');self.apply_access();self.render()
    def new_conversation(self):
        self.reset();self.store_conversation()
    def begin(self):
        self.busy=True;self.job+=1;self.structured_job=None;self.identity=self.user_id();self.stop_button.show();self.proposals=[];self.app_actions=[];self.app_context=None;self.apply_access();return self.job
    def set_models(self,job,models):
        if not self.current(job):return
        self.model.clear();self.model.addItem(GEMMA_MODEL)
    def probe(self):
        if self.busy or not gate(self.owner,'assistant','use'):return
        self.pending_request_id=None
        try:self.worker=make_client(self.owner,12)
        except Exception as exc:self.status.setText(str(exc));return
        job=self.begin();client=self.worker;self.status.setText('در حال اتصال به LM Studio…')
        def work():
            try:
                selected=connection(self.owner)['model'];models=[m for m in client.models() if m==selected];emit(self.bridge.models,job,models);emit(self.bridge.done,job,dict(probe=True,models=models),None)
            except Exception as exc:emit(self.bridge.done,job,None,exc)
            finally:client.close()
        threading.Thread(target=work,daemon=True).start()
    def send(self):
        if self.busy or not gate(self.owner,'assistant','use'):return
        text=self.prompt.toPlainText().strip()
        if not text:return
        if re.fullmatch(r'\s*(?:چرا|چرا انجام نشد|چرا انجام نمیدی)[؟?!.\s]*',text) and self.history and self.history[-1].get('role')=='assistant':
            previous=str(self.history[-1].get('content',''))
            if previous.startswith('درخواست قابل اجرا نیست:'):
                reason=previous.split(':',1)[1].strip()
                reply='درخواست قبلی ثبت نشد. دلیل ثبت‌شده در برنامه: '+reason+'\nاین پیام به‌تنهایی به معنی نداشتن دسترسی به تقویم یا چت نیست. می‌توانید درخواست را اصلاح و دوباره ارسال کنید.'
                self.history=(self.history+[dict(role='user',content=text),dict(role='assistant',content=reply)])[-24:];self.items.extend([dict(role='user',content=text),dict(role='assistant',content=reply)]);self.prompt.clear();self.store_conversation();self.render();return
        if self.mode.currentData() in ('app','plan') and self.select_placeholder():self.status.setText('عنوان، نام یا تاریخ داخل کروشه را پیش از ارسال کامل کنید.');return
        if len(text)>6000:self.status.setText('پیام را کوتاه‌تر از ۶۰۰۰ نویسه بنویسید.');return
        memory_prompt=''
        if self.memory_check.isChecked() and self.user_id()!='standalone':
            try:
                from ai_memory import recall,prompt
                memory_prompt=prompt(recall(self.user_id(),text))[:2200]
            except Exception as exc:self.status.setText('حافظه قابل خواندن نیست: '+str(exc));return
        try:self.worker=make_client(self.owner)
        except Exception as exc:self.status.setText(str(exc));return
        job=self.begin();client=self.worker;model=connection(self.owner)['model'];planning=self.mode.currentData()=='plan';explanation=bool(re.fullmatch(r'\s*(?:چرا|چرا انجام نشد|چرا انجام نمیدی|چی شد|چه شد|انجام شد|انجام شد یا نه)[؟?!.\s]*',text));application=self.mode.currentData()=='app' and not explanation;self.structured_job=job if planning or application else None;from ai_app_actions import capture;app_snapshot=capture(self.owner) if application else None;include_context=self.context_check.isChecked();search_hint=previous_search_hint(self.history,text);effective=clarification_request(self.history,text) if application or planning else text;effective=resolve_recent_reminders(self.history,effective,app_snapshot['events']) if application and include_context else effective;request_history=self.history+[dict(role='user',content=text)];model_history=compact_conversation(request_history);messages=messages_for(model_history,system_prompt(jformat(today_j()),planning)+memory_prompt+('\nبه سؤال درباره درخواست قبلی با توجه به نتیجه واقعی ثبت‌شده در گفتگو پاسخ بده. حدس نزن و عملیات را دوباره انجام نده.' if explanation else ''),max_chars=10000);self.items.append(dict(role='user',content=text));self.items.append(dict(role='assistant',content=''));self.reply_index=len(self.items)-1;self.pending_prompt=text;self.pending_action_prompt=effective;self.prompt.clear();self.status.setText('در انتظار پاسخ مدل…');self.render()
        import uuid
        self.pending_request_id=uuid.uuid4().hex
        self.plan_result_status=None
        self.pending_journal_request=text
        if effective!=text and self.user_id()!='standalone' and self.memory_check.isChecked():
            try:
                from ai_memory import read_requests
                entries=read_requests(self.user_id(),self.scope_stamp)
                previous=next((item.get('content','') for item in reversed(self.history) if item.get('role')=='user'),'')
                if entries and entries[-1].get('status')=='awaiting' and previous and (entries[-1].get('request')==previous or entries[-1].get('request','').endswith(previous)):
                    self.pending_request_id=entries[-1]['id'];self.pending_journal_request=effective
            except Exception:pass
        if self.user_id()!='standalone' and self.memory_check.isChecked():
            try:
                from ai_memory import save_request
                save_request(self.user_id(),self.scope_stamp,self.pending_request_id,self.pending_journal_request,'processing','پاسخ یا نتیجه عملیات هنوز تأیید نشده است.')
            except Exception as exc:self.status.setText('ذخیره وضعیت درخواست ممکن نشد: '+str(exc))
        def work():
            try:
                chosen=model;app_context=None;outgoing=messages
                if application:
                    from ai_app_actions import collect,action_prompt
                    from ai_language import domain_instruction
                    app_context=collect(app_snapshot,effective,include_context,search_hint);outgoing=messages_for(model_history,'شما دستیار فارسی کارنامه هستید. زمینه نوبت‌های قبلی را برای فهم سؤال ادامه‌دار حفظ کن؛ از داده فعلی و مجوزهای فعلی پیروی کن. درخواست‌های محاوره‌ای و مترادف‌ها را درک کن. برای پرسش‌های عمومی پاسخ روشن بده. سؤال «چرا» درخواست اجرای دوباره نیست. اگر در درخواست نام چند یادآور برای حذف آمده، برای هر کدام یک عملیات مستقل پیشنهاد بده. فقط وقتی کاربر عملاً خواستار اقدامی است و جزئیات کافی و مجاز داری، آن را درخواست کن؛ در ابهام سؤال بپرس.\nدرخواست تکمیل‌شده: '+effective+'\n'+domain_instruction(effective)+'\n'+memory_prompt+'\n'+action_prompt(app_context),max_chars=10000)
                if not chosen:
                    models=client.models()
                    if not models:raise LMError('مدل گفتگو پیدا نشد؛ مدل را در LM Studio بارگذاری کنید.')
                    chosen=models[0];emit(self.bridge.models,job,models)
                answer=client.chat(chosen,outgoing,lambda piece:emit(self.bridge.piece,job,piece));emit(self.bridge.done,job,dict(answer=answer,history=request_history,planning=planning,model=chosen,application=application,app_context=app_context),None)
            except Exception as exc:emit(self.bridge.done,job,None,exc)
            finally:client.close()
        threading.Thread(target=work,daemon=True).start()
    def piece(self,job,text):
        if not self.current(job) or self.reply_index is None:return
        self.status.setText('در حال دریافت پاسخ…')
        if self.structured_job==job:return
        self.items[self.reply_index]['content']+=text
        if not self.render_timer.isActive():self.render_timer.start()
    def finished(self,job,value,error):
        if not self.current(job):return
        self.worker=None;self.busy=False;self.stop_button.hide()
        if error:
            self.mark_request_interrupted()
            self.scheduled_finish('failed')
            if not self.prompt.toPlainText().strip() and getattr(self,'pending_prompt',''):self.prompt.setPlainText(self.pending_prompt)
            self.status.setText('دریافت متوقف شد.' if isinstance(error,Cancelled) else str(error));self.apply_access();self.render();return
        if value.get('probe'):self.status.setText('اتصال کارنامه برقرار است.' if value['models'] else 'دستیار آماده نیست؛ اتصال میزبان را بررسی کنید.')
        else:
            self.history=(value['history']+[dict(role='assistant',content=value['answer'])])[-24:];self.status.setText('پاسخ کارنامه دریافت شد.')
            if value.get('application'):
                from ai_app_actions import parse_answer
                self.app_context=value['app_context']
                try:
                    reply,self.app_actions=parse_answer(value['answer'],self.app_context)
                    resolved=getattr(self,'pending_action_prompt','')
                    if '\nحذف یادآورهای نام‌برده‌شده: ' in resolved:
                        expected=set(re.findall(r'«([^»]+)»',resolved.split('\nحذف یادآورهای نام‌برده‌شده: ',1)[1]))
                        selected=[self.app_context.get('targets',{}).get(a.get('target'),{}).get('event',{}).get('title') for a in self.app_actions if a.get('type')=='reminder_delete']
                        if len(selected)!=len(expected) or set(selected)!=expected or len(self.app_actions)!=len(expected):
                            self.app_actions=[];raise ValueError('همه یادآورهای اشاره‌شده به‌طور یکتا مشخص نشدند؛ هیچ موردی حذف نشد.')
                    from ai_language import domain_hint
                    domain=domain_hint(getattr(self,'pending_action_prompt',self.pending_prompt));chat_actions={'message_send','message_schedule','chat_special','chat_file_send','chat_mute','chat_like','chat_vote','chat_delete','chat_restore','chat_group_create','chat_direct_create','chat_saved_create','chat_group_archive','chat_group_restore'};reminder_actions={'reminder_create','reminder_update','reminder_delete','reminder_restore','task_reminder','reminder_settings'}
                    if any(a['type'] in (reminder_actions if domain=='chat' else chat_actions if domain=='reminder' else set()) for a in self.app_actions):
                        self.app_actions=[];raise ValueError('عمل پیشنهادی با بخش درخواستی شما همخوان نیست؛ لطفاً مقصد یا نوع یادآور را روشن‌تر بنویسید.')
                    from ai_actions_ui import proposal_text
                    self.items[self.reply_index]['content']=proposal_text(self.app_actions,self.app_context) if self.app_actions else reply or 'اطلاعات درخواستی در فهرست فعلی پیدا نشد.'
                    if self.app_actions:
                        if explicit_action_requested(getattr(self,'pending_action_prompt',self.pending_prompt)):self.status.setText('در حال انجام درخواست…');QTimer.singleShot(0,self.apply_app_actions)
                        else:self.scheduled_finish('failed');self.app_actions=[];self.items[self.reply_index]['content']='برای انجام تغییر، دستور را به‌صورت صریح بنویسید.';self.status.setText('درخواست تغییر را دقیق بیان کنید.')
                    else:self.status.setText('پاسخ آماده است.')
                except ValueError as exc:
                    self.scheduled_finish('failed')
                    if '{' not in value['answer'] and not value['answer'].lstrip().startswith('['):self.items[self.reply_index]['content']=value['answer'];self.status.setText('پاسخ خواندنی؛ تغییری اعمال نشد.')
                    else:self.items[self.reply_index]['content']='درخواست قابل اجرا نیست: '+str(exc);self.status.setText(str(exc))
            elif value['planning']:
                if '{' not in value['answer'] and not value['answer'].lstrip().startswith('['):
                    self.proposals=[];self.scheduled_finish('failed');self.items[self.reply_index]['content']=value['answer'];self.status.setText('پاسخ آماده است؛ برنامه‌ای ثبت نشد.')
                else:
                    self.finish_plan(value)
            else:self.items[self.reply_index]['content']=value['answer']
        if not value.get('probe') and self.reply_index is not None and self.history and self.history[-1]['role']=='assistant':self.history[-1]['content']=self.items[self.reply_index]['content']
        if not value.get('probe') and not self.app_actions and self.reply_index is not None:self.save_memory(self.items[self.reply_index]['content'],getattr(self,'plan_result_status',None) if value.get('planning') else None)
        if self.scheduled_job and not self.app_actions:self.scheduled_finish('completed')
        self.apply_access();self.render()
    def finish_plan(self,value):
        self.plan_result_status='failed'
        try:
            from ai_app_actions import ensure_requested_day,lead,validate_explicit_schedule
            from storage import normalize
            from reminders import DEFAULT_LEADS
            self.proposals=parse_plan(value['answer']);q=normalize(getattr(self,'pending_action_prompt',self.pending_prompt));ctx={'query':q,'prior_user_hint':previous_search_hint(value['history'][:-1],q),'public':{'today_jalali':normalize(jformat(today_j()))}}
            if not explicit_action_requested(q):raise ValueError('برای ثبت برنامه، درخواست را به‌صورت صریح بنویسید.')
            offsets_explicit=bool(re.search(r'(?:\d|یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده)\s*روز|روز\s*(?:قبل|پیش|موعد|سررسید)',q))
            for row in self.proposals:
                ensure_requested_day(row['date_jalali'],ctx,allow_range=True)
                if offsets_explicit:validate_explicit_schedule({'changes':{'lead_days':row['lead_days']}},{'type':'reminder_create','changes':row},ctx)
                else:row['lead_days']=lead(self.owner.data['settings'].get('personal_lead_days') or DEFAULT_LEADS)
            count=save_plan(self.owner,self.proposals);self.plan_result_status='completed';self.items[self.reply_index]['content']=fa(count)+' یادآور ثبت شد.\n\n'+'\n\n'.join(fa(i+1)+' ـ '+row['title']+'\nموعد: '+fa(row['date_jalali']) for i,row in enumerate(self.proposals));self.proposals=[];self.status.setText('برنامه در تقویم ثبت شد.')
        except (ValueError,PermissionError) as exc:self.proposals=[];self.scheduled_finish('failed');self.items[self.reply_index]['content']='برنامه قابل ثبت نیست. لطفاً درخواست و تاریخ‌ها را دقیق‌تر بنویسید.';self.status.setText(str(exc))
    def save_memory(self,result,execution=None):
        if not self.memory_check.isChecked() or self.user_id()=='standalone':return
        try:
            from ai_memory import record
            record(self.user_id(),getattr(self,'pending_prompt',''),result)
            from ai_memory import save_request
            import uuid
            if execution is None:
                status='failed' if 'درخواست قابل اجرا نیست' in result else 'awaiting' if '؟' in result or '?' in result else 'answered'
            else:status=execution
            request_id=getattr(self,'pending_request_id','') or uuid.uuid4().hex
            save_request(self.user_id(),self.scope_stamp,request_id,getattr(self,'pending_journal_request',getattr(self,'pending_prompt','')),status,result)
            self.store_conversation()
        except Exception as exc:self.status.setText('پاسخ دریافت شد اما ذخیره حافظه انجام نشد: '+str(exc))
    def render(self):
        from appearance import palette_for,contrast
        colors=palette_for(self.owner.data['settings']);fg=colors['text'];mine=colors['selected'];bot=colors['panel'];scroll=self.transcript.verticalScrollBar();position=scroll.value();follow=position>=scroll.maximum()-35;parts=[]
        if getattr(self,'_schedule_icon_color',None)!=fg:
            from ui_icons import symbol
            for button in self.findChildren(QPushButton):
                key={'زمان‌بندی درخواست':'schedule','درخواست‌های زمان‌بندی‌شده':'schedule_list'}.get(button.accessibleName())
                if key:button.setIcon(symbol(key,fg))
            self._schedule_icon_color=fg
        for item in self.items[-48:]:
            title='شما' if item['role']=='user' else 'کارنامه';body=html.escape(item['content'] or ('در انتظار پاسخ…' if self.busy else 'پاسخی دریافت نشد.')).replace('\n','<br>');bg=mine if item['role']=='user' else bot;ink=fg if contrast(fg,bg)>=4.5 else max(('#FFFFFF','#111111'),key=lambda value:contrast(value,bg));alignment='right' if item['role']=='user' else 'left';parts.append(f'<table dir="rtl" align="{alignment}" width="78%" border="0" cellpadding="12" cellspacing="0" bgcolor="{bg}"><tr><td style="color:{ink};"><b>{title}</b><br>{body}</td></tr></table><br>')
        if not parts:parts=[f'<p dir="rtl" style="color:{fg};">به دستیار کارنامه خوش آمدید. مدل LM Studio را متصل کنید و سؤال یا درخواست برنامه‌ریزی خود را بنویسید.</p>']
        self.transcript.setHtml(''.join(parts))
        scroll.setValue(scroll.maximum() if follow else min(position,scroll.maximum()))
    def preview(self):
        if self.app_actions:return self.preview_app()
        if not gate(self.owner,'assistant','use') or not gate(self.owner,'calendar','create') or not self.proposals:return
        d=PlanPreview(self.owner,self.proposals)
        if d.exec()!=QDialog.Accepted:return
        try:
            count=save_plan(self.owner,d.result_items);self.proposals=[];self.status.setText(fa(count)+' یادآور در تقویم شخصی ثبت شد؛ موارد تکراری دوباره ثبت نمی‌شوند.');self.apply_access()
        except Exception as exc:QMessageBox.warning(self,'ثبت برنامه',str(exc))

    def preview_app(self):
        if not gate(self.owner,'assistant','use') or not self.app_context:return
        self.apply_app_actions()
    def apply_app_actions(self):
        if self.applying or not self.app_actions or not self.app_context:return
        if not allowed(self.owner,'assistant','use'):
            self.scheduled_finish('failed');self.app_actions=[];self.status.setText('دسترسی دستیار تغییر کرده است.');self.apply_access();return
        from ai_app_actions import execute
        from ai_language import explicit_message_request
        from personalization_ui import request_wait
        from storage import normalize
        original=normalize(getattr(self,'pending_action_prompt',getattr(self,'pending_prompt',''))).casefold()
        for action in self.app_actions:
            if action['type']=='message_send' and (not explicit_message_request(original) or normalize(action['changes']['text']).casefold() not in original):
                self.scheduled_finish('failed');self.status.setText('متن و مقصد پیام را دقیق بنویسید.');self.app_actions=[];self.apply_access();return
        identity=self.user_id();self.applying=True;self.apply_access()
        try:
            results=execute(self.owner,self.app_actions,self.app_context,lambda path,payload=None,**query:request_wait(self.owner,path,payload,**query))
            if identity!=self.user_id():return
            completed=[r['action'] for r in results if r['ok']];self.app_actions=[a for a in self.app_actions if a not in completed];text='نتیجه واقعی برنامه:\n'+'\n'.join(('✓ ' if r['ok'] else 'نیازمند بررسی: ')+r['message'] for r in results);self.items.append(dict(role='app',content=text))
            if self.history and self.history[-1]['role']=='assistant':self.history[-1]['content']+='\n\n'+text
            elif self.history:self.history.append(dict(role='assistant',content=text))
            self.save_memory(text,'completed' if results and all(r['ok'] for r in results) else 'partial' if any(r['ok'] for r in results) else 'failed')
            self.status.setText(fa(len(completed))+' مورد انجام شد.' if all(r['ok'] for r in results) else fa(len(completed))+' مورد انجام شد؛ بقیه اعمال نشدند و نیاز به بازبینی دارند.')
            self.scheduled_finish('completed' if results and all(r['ok'] for r in results) else 'failed')
        except Exception as exc:self.scheduled_finish('failed');self.status.setText(str(exc))
        finally:self.applying=False;self.apply_access();self.render()


