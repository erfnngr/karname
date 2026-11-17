"""Adapter between the React Home dashboard and existing Python/Qt services."""
from datetime import date, datetime, timedelta, timezone
import json
import jdatetime
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from occasions import on_date as occasions_on_date
from quotes import daily_quote
from storage import due_on, fa, jformat, today_j, jalali_date, month_last_day, MONTHS, parse_j
from ui_permissions import allowed
from weather import weather_kind
from weather_ui import measurement_caption

WEEKDAY_NAMES = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه']

DEFAULT_HOME_CARDS = ('briefing', 'weather', 'today_reminders', 'activity_stats', 'quote')

_GREETING_WISHES = {
    'morning': (
        'صبح‌تون بخیر',
        [
            'شروعی پرانرژی، آرام و پربرکت را برای امروزتان آرزو می‌کنیم.',
            'امیدواریم امروز با ذهنی شفاف و گام‌هایی مطمئن پیش بروید.',
            'صبح دل‌انگیزتان سرشار از آرامش، تمرکز و خبرهای خوش باشد.',
            'آغاز روزتان روشن و برنامه‌های امروزتان روان و به‌سامان.',
        ],
    ),
    'noon': (
        'ظهر بخیر',
        [
            'نیمروزتان پرنشاط و کارهای پیش‌روتان با تمرکز و موفقیت همراه باشد.',
            'امیدواریم بخش دوم روزتان آرام، دقیق و پربازده سپری شود.',
            'ظهر دلپذیری برایتان آرزومندیم؛ همه پیگیری‌ها به خوبی پیش برود.',
            'نیمروز پرانرژی و روانی در میز کار امروزتان داشته باشید.',
        ],
    ),
    'evening': (
        'عصر بخیر',
        [
            'عصر آرام و دلنشینی پیش رویتان باشد؛ جمع‌بندی امروز به خیر و خوشی.',
            'خسته نباشید؛ امیدواریم عصر دلپذیر و پرآرامشی داشته باشید.',
            'پایان بخش کاری امروزتان با رضایت خاطر و آرامش همراه باشد.',
            'عصر خوش و آرامی را در ادامه روز برایتان آرزو می‌کنیم.',
        ],
    ),
    'night': (
        'شب بخیر',
        [
            'شب آرام و دل‌انگیزی داشته باشید؛ خسته نباشید و امیدواریم فردایی روشن بسازید.',
            'آرامش شبانه‌تان برقرار و مرور کارهای فردا سبک و بی‌دغدغه باشد.',
            'شب خوشی برایتان آرزومندیم؛ استراحتی دلچسب و فردایی پربار.',
            'در این ساعت شب، امیدواریم خاطر آسوده و آرامش کامل همراهتان باشد.',
        ],
    ),
}


def _extract_first_name(fullname):
    text = str(fullname or '').strip()
    if not text:
        return 'دوست عزیز'
    parts = [p for p in text.split() if p]
    if not parts:
        return 'دوست عزیز'
    # Keep first meaningful given name
    if len(parts) > 1 and parts[0] in ('آقای', 'خانم', 'مهندس', 'دکتر', 'سید', 'سیده'):
        return ' '.join(parts[:2])
    return parts[0]


def _time_greeting(fullname, g_today=None, hour=None):
    now = datetime.now()
    h = now.hour if hour is None else int(hour)
    if 5 <= h < 12:
        period = 'morning'
    elif 12 <= h < 16:
        period = 'noon'
    elif 16 <= h < 20:
        period = 'evening'
    else:
        period = 'night'
    first_name = _extract_first_name(fullname)
    salutation_phrase, wishes = _GREETING_WISHES[period]
    seed = (g_today or now.date()).toordinal() + (h // 3)
    subtitle = wishes[seed % len(wishes)]
    badge = {'morning': 'آغاز روز کاری', 'noon': 'میانه روز', 'evening': 'ساعات پایانی روز', 'night': 'حالت شبانه'}[period]
    return {
        'period': period,
        'first_name': first_name,
        'salutation': f'سلام {first_name}، {salutation_phrase}',
        'subtitle': subtitle,
        'badge': badge,
    }

MODULE_CATALOG = (
    ('workspace', 'کارها و پیگیری‌ها', 'مدیریت وظایف، درخواست‌ها و پیگیری روزانه'),
    ('chat', 'چت', 'گفتگوهای تیمی، شخصی و پیام‌های ذخیره‌شده'),
    ('assistant', 'دستیار هوشمند', 'همکار هوش مصنوعی متصل به اطلاعات برنامه'),
    ('tax', 'مالیات', 'نقشه مراحل پرونده‌های مالیاتی و مقایسه فصلی'),
    ('calendar', 'تقویم', 'یادآورها، سررسیدها و رویدادهای ماهانه'),
    ('clients', 'فاکتورها', 'مشتریان، فاکتورها و پیگیری مالی'),
    ('desk', 'کارتابل من', 'یادداشت‌ها و کارهای شخصی'),
    ('company', 'فضای شرکت', 'اسناد و تنظیمات شرکت و دسترسی‌ها'),
    ('services', 'سامانه‌ها', 'درگاه‌ها و سامانه‌های کاربردی'),
    ('attendance', 'تردد و ساعت کار', 'گزارش ساعات کار و حضور و غیاب'),
    ('occasions', 'مناسبت‌ها', 'فهرست کامل مناسبت‌های سال'),
)


class ReactHomeBridge(QObject):
    """Expose real Home dashboard state and safe actions to React."""

    changed = Signal(str)
    completed = Signal(str, str)

    def __init__(self, panel, parent=None, show_native=None):
        super().__init__(parent)
        self.panel = panel
        self.show_native = show_native
        self.last = ''
        ws = getattr(panel, 'weather_service', None)
        if ws is not None:
            ws.changed.connect(self.publish)
            ws.comparison_changed.connect(self.publish)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        try:
            owner = self.panel.owner
            tabs = getattr(owner, 'tabs', None)
            if tabs is not None and tabs.currentWidget() is not self.panel:
                return
        except Exception:
            pass
        self.publish()

    def _weather_payload(self):
        panel = self.panel
        owner = panel.owner
        settings = owner.data.get('settings', {})
        enabled = bool(settings.get('weather_enabled', True))
        ws = getattr(panel, 'weather_service', None)
        if not enabled or ws is None:
            return {'enabled': False}

        base = {
            'enabled': True,
            'busy': bool(ws.busy),
            'error': str(ws.error or ''),
            'cached': bool(getattr(ws, 'cached', False)),
            'show_hourly': bool(settings.get('weather_hourly', True)),
            'show_weekly': bool(settings.get('weather_weekly', True)),
            'comparison': {
                'busy': bool(getattr(ws, 'comparison_busy', False)),
                'error': str(getattr(ws, 'comparison_error', '') or ''),
                'data': getattr(ws, 'comparison', None),
            },
        }
        data = ws.data
        if not data:
            return base

        current = data['current']
        kind, label = weather_kind(current['symbol'], at_time=current.get('time'))
        stamp = ws.checked_at.strftime('%H:%M') if ws.checked_at else ''
        caption = measurement_caption(data) or (('آخرین دریافت ' + fa(stamp)) if stamp else '')
        if getattr(ws, 'cached', False) or ws.error:
            caption = (caption + ' · ذخیره‌شده').strip(' ·')
        station = (current.get('observation') or {}).get('station_name', '')

        hours = []
        for h in data.get('hours', [])[:24]:
            hk, hl = weather_kind(h['symbol'], at_time=h.get('time'))
            hours.append({
                'time': fa(h['time'].strftime('%H:%M')),
                'temp': fa(round(h['temp'])),
                'kind': hk,
                'label': hl,
            })

        days = []
        for d in data.get('days', []):
            dk, dl = weather_kind(d['symbol'])
            jd = jdatetime.date.fromgregorian(date=d['date'])
            name = 'امروز' if d['date'] == current['time'].date() else WEEKDAY_NAMES[d['date'].weekday()]
            days.append({
                'name': name,
                'date_fa': fa(jd.strftime('%m/%d')),
                'min': fa(round(d['min'])),
                'max': fa(round(d['max'])),
                'kind': dk,
                'label': dl,
            })

        base.update({
            'has_data': True,
            'estimated': bool(data.get('estimated')),
            'location': str(data.get('location') or 'تهران'),
            'caption': caption,
            'station': str(station or ''),
            'last_checked': fa(stamp) if stamp else '',
            'current': {
                'temp': fa(round(current['temp'])),
                'kind': kind,
                'label': label,
                'humidity': fa(current['humidity']) if current.get('humidity') is not None else None,
                'wind': fa(round(current['wind'])) if current.get('wind') is not None else None,
            },
            'hours': hours,
            'days': days,
        })
        return base

    def _build_state(self):
        panel = self.panel
        owner = panel.owner
        settings = owner.data.get('settings', {})
        prefs = owner.data.get('preferences', {})
        user = owner.session_user or {}

        today = today_j()
        g_today = date.today()
        weekday = WEEKDAY_NAMES[g_today.weekday()]

        cal_allowed = allowed(owner, 'calendar')
        ws_allowed = allowed(owner, 'workspace')
        occ_allowed = allowed(owner, 'occasions') or cal_allowed
        settings_allowed = allowed(owner, 'settings')

        reminders = []
        reminders_total = 0
        calendar_events = owner.display_events() if cal_allowed else []
        if cal_allowed:
            due = [e for e in calendar_events if due_on(e, g_today)]
            reminders_total = len(due)
            for item in due:
                reminders.append({
                    'title': str(item.get('title', '')),
                    'company': str(item.get('company', 'شخصی') or 'شخصی'),
                    'priority': str(item.get('priority', 'متوسط')),
                    'done': bool(item.get('done') or g_today.isoformat() in item.get('completed_occurrences', [])),
                })

        occasions = []
        if occ_allowed:
            for occ in occasions_on_date(g_today)[:5]:
                occasions.append({
                    'title': str(occ.get('title', '')),
                    'holiday': bool(occ.get('holiday')),
                    'source': str(occ.get('source', '') or ''),
                })

        activity = {'allowed': ws_allowed, 'overdue': 0, 'review': 0, 'requests': 0, 'next_meeting': '', 'total': 0}
        if ws_allowed:
            snap = getattr(getattr(owner, 'workspace', None), 'snapshot', None) or {}
            tasks = snap.get('tasks', [])
            meetings = snap.get('meetings', [])
            meeting_label = ''
            if meetings:
                meeting = meetings[0]
                meeting_label = str(meeting.get('title', '')[:48])
                try:
                    at = datetime.fromisoformat(str(meeting.get('at', '')).replace('Z', '+00:00'))
                    if at.tzinfo is not None:
                        local = at.astimezone(timezone(timedelta(hours=3, minutes=30)))
                        jd = jdatetime.date.fromgregorian(date=local.date())
                        meeting_label += ' · ' + fa(jformat(jd)) + ' ' + fa(local.strftime('%H:%M'))
                except (ValueError, TypeError):
                    pass
            overdue = sum(t.get('overdue', False) and t.get('mine', False) for t in tasks)
            review = sum(t.get('review', False) for t in tasks)
            requests = sum(r.get('can_review', False) for r in snap.get('requests', []))
            activity.update({
                'overdue': int(overdue),
                'overdue_fa': fa(overdue),
                'review': int(review),
                'review_fa': fa(review),
                'requests': int(requests),
                'requests_fa': fa(requests),
                'total': len(tasks),
                'total_fa': fa(len(tasks)),
                'next_meeting': meeting_label,
            })

        quote_state = {'enabled': False}
        if settings.get('daily_quote_enabled', True):
            q = getattr(panel, 'current_quote', None) or daily_quote()
            if q:
                quote_state = {
                    'enabled': True,
                    'text': str(q.get('text', '')),
                    'author': str(q.get('author', '')),
                    'work': str(q.get('work', '')),
                    'section': str(q.get('section', '')),
                    'has_source': bool(q.get('source')),
                }

        from home_layout import BENTO_DEFAULT_MODULES
        from theme_catalog import preset
        all_modules = []
        visible_pref = set(prefs.get('visible_modules', [k for k, _, _ in MODULE_CATALOG]))
        cal_title = str(prefs.get('calendar_name') or 'تقویم')
        by_key = {}
        for key, title, desc in MODULE_CATALOG:
            if key not in owner.modules:
                continue
            if not allowed(owner, key):
                continue
            if key in ('attendance', 'occasions') and key not in visible_pref:
                continue
            entry = {
                'key': key,
                'title': cal_title if key == 'calendar' else title,
                'desc': desc,
            }
            all_modules.append(entry)
            by_key[key] = entry

        saved_bento = prefs.get('bento_modules')
        if isinstance(saved_bento, list):
            bento_keys = [k for k in saved_bento if k in by_key][:6]
        else:
            bento_keys = [k for k in BENTO_DEFAULT_MODULES if k in by_key]
            for entry in all_modules:
                if len(bento_keys) >= 6:
                    break
                if entry['key'] not in bento_keys:
                    bento_keys.append(entry['key'])
            bento_keys = bento_keys[:6]
        bento_modules = [by_key[k] for k in bento_keys]
        theme_key = preset(settings.get('theme_preset', 'default'))
        weather_payload = self._weather_payload()
        fullname = str(user.get('fullname') or 'کاربر کارنامه')
        greeting = _time_greeting(fullname, g_today=g_today)
        briefing = self._build_briefing(
            today=today,
            weekday=weekday,
            reminders=reminders,
            reminders_total=reminders_total,
            activity=activity,
            occasions=occasions,
            weather_payload=weather_payload,
            first_name=greeting['first_name'],
            calendar_allowed=cal_allowed,
        )
        saved_cards = prefs.get('home_cards')
        if isinstance(saved_cards, list):
            cards_pref = [k for k in saved_cards if k in DEFAULT_HOME_CARDS]
        else:
            cards_pref = list(DEFAULT_HOME_CARDS)
        card_cols = prefs.get('home_card_columns', 'auto')
        if card_cols not in ('auto', 2, 3):
            card_cols = 'auto'
        density_mode = prefs.get('home_density_mode', 'comfortable')
        if density_mode not in ('compact', 'comfortable', 'spacious'):
            density_mode = 'comfortable'

        return {
            'user': {
                'fullname': fullname,
                'first_name': greeting['first_name'],
                'username': str(user.get('username') or ''),
            },
            'greeting': greeting,
            'home_prefs': {
                'cards': cards_pref,
                'columns': card_cols,
                'density': density_mode,
            },
            'today': {
                'jalali': jformat(today),
                'gregorian': g_today.isoformat(),
                'weekday': str(weekday),
            },
            'mini_calendar': self._mini_calendar(today, calendar_events) if cal_allowed else None,
            'permissions': {
                'calendar': cal_allowed,
                'calendar_create': bool(cal_allowed and allowed(owner, 'calendar', 'create')),
                'workspace': ws_allowed,
                'assistant': allowed(owner, 'assistant', 'use'),
                'settings': settings_allowed,
                'settings_edit': bool(settings_allowed and allowed(owner, 'settings', 'edit')),
            },
            'reminders': reminders[:8],
            'reminders_total': reminders_total,
            'reminders_total_fa': fa(reminders_total),
            'occasions': occasions,
            'activity': activity,
            'weather': weather_payload,
            'quote': quote_state,
            'modules': all_modules,
            'bento_modules': bento_modules,
            'briefing': briefing,
            'theme': self._home_mode(settings),
            'theme_preset': theme_key,
            'home_skin': self._home_skin(settings),
        }

    def _mini_calendar(self, today, events):
        # Recompute recurrence markers only when the month or event data changes.
        from iran_calendar import day_off
        key = (today.year, today.month, today.day, json.dumps(events, ensure_ascii=False, sort_keys=True, default=str))
        if key == getattr(self, '_mini_key', None):
            return self._mini_value
        first = jalali_date(today.year, today.month, 1).togregorian()
        offset = (first.weekday() + 2) % 7
        cells = []
        for day in range(1, month_last_day(today.year, today.month) + 1):
            gd = first + timedelta(days=day-1)
            cells.append({'day': day, 'label': fa(day), 'date': f'{today.year:04d}/{today.month:02d}/{day:02d}',
                          'today': day == today.day, 'holiday': bool(day_off(gd)),
                          'has_events': any(due_on(event, gd) for event in events)})
        self._mini_key = key
        self._mini_value = {'title': MONTHS[today.month-1]+' '+fa(today.year), 'offset': offset, 'days': cells}
        return self._mini_value

    def _build_briefing(self, *, today, weekday, reminders, reminders_total, activity, occasions, weather_payload, first_name='دوست عزیز', calendar_allowed=True):
        owner = self.panel.owner
        bullets = []
        parts = []

        # 1) Tasks & deadlines status
        pending_rem = sum(1 for r in reminders if not r.get('done'))
        if reminders_total > 0:
            rem_text = (
                f'برای امروز {fa(reminders_total)} یادآور ثبت شده که {fa(pending_rem)} مورد آن در انتظار انجام است.'
                if pending_rem
                else f'تمام {fa(reminders_total)} یادآور امروز با موفقیت انجام شده است.'
            )
            parts.append(rem_text)
            bullets.append({'type': 'reminder', 'title': 'یادآورهای امروز', 'detail': rem_text})
        elif calendar_allowed:
            parts.append('برای امروز یادآور باز وجود ندارد.')

        if activity.get('allowed'):
            overdue = int(activity.get('overdue') or 0)
            review = int(activity.get('review') or 0)
            reqs = int(activity.get('requests') or 0)
            work_bits = []
            if overdue:
                work_bits.append(f'{fa(overdue)} کار معوق')
            if review:
                work_bits.append(f'{fa(review)} مورد در انتظار تأیید')
            if reqs:
                work_bits.append(f'{fa(reqs)} درخواست نیازمند بررسی')
            if work_bits:
                work_detail = f'در کارتابل، {" و ".join(work_bits)} ثبت شده است.'
            else:
                work_detail = 'وضعیت کارهای شما مرتب است و هیچ مورد معوقی در صف نیست.'
            if activity.get('next_meeting'):
                work_detail += f' همچنین جلسه «{activity["next_meeting"]}» پیش رویتان قرار دارد.'
            parts.append(work_detail)
            bullets.append({'type': 'work', 'title': 'وضعیت کارها', 'detail': work_detail})

        # 2) Weather tip
        cur_w = weather_payload.get('current') if weather_payload.get('has_data') else None
        if cur_w:
            wlabel = cur_w.get('label', '')
            wtemp = cur_w.get('temp', '')
            advice = ''
            kind = cur_w.get('kind', '')
            if kind in ('cloud-rain', 'cloud-lightning'):
                advice = ' همراه داشتن چتر توصیه می‌شود.'
            elif kind == 'cloud-snow':
                advice = ' هوا سرد و برفی است؛ پوشش گرم مناسب خواهد بود.'
            w_detail = f'هوای {weather_payload.get("location", "تهران")} {wlabel} با دمای {wtemp}° است.{advice}'
            parts.append(w_detail)
            bullets.append({'type': 'weather', 'title': 'وضعیت هوا', 'detail': w_detail})

        # 3) Upcoming or today's birthdays
        bdays = getattr(getattr(owner, 'org', None), 'birthdays', None) or []
        near_bdays = [b for b in bdays if not b.get('is_self') and 0 <= int(b.get('days_until', 99)) <= 3]
        if near_bdays:
            first_b = near_bdays[0]
            when_str = 'امروز' if first_b['days_until'] == 0 else f'{fa(first_b["days_until"])} روز دیگر'
            b_detail = f'تولد {first_b["fullname"]} {when_str} ({first_b.get("label_fa", "")}) است.'
            parts.append(b_detail)
            bullets.append({'type': 'birthday', 'title': 'تولد همکاران', 'detail': b_detail})

        # 4) Occasions
        if occasions:
            occ_detail = occasions[0].get('title', '')
            if occasions[0].get('holiday'):
                occ_detail += ' (تعطیل رسمی)'
            parts.append(f'مناسبت امروز: {occ_detail}.')
            bullets.append({'type': 'occasion', 'title': 'مناسبت روز', 'detail': occ_detail})

        priority = {'birthday': 0, 'reminder': 1, 'work': 2, 'occasion': 3, 'weather': 4}
        bullets.sort(key=lambda item: priority.get(item['type'], 5))
        summary = f'{first_name} عزیز، امروز {weekday} {jformat(today)}، ' + ' '.join(parts)
        return {
            'summary': summary,
            'ai_powered': False,
            'bullets': bullets[:3],
        }

    def _home_mode(self, settings):
        from section_themes import resolve_section_theme
        return resolve_section_theme(settings, 'home')['theme']['mode']

    def _home_skin(self, settings):
        from theme_catalog import preset
        if preset(settings.get('theme_preset', 'default')) == 'bento_grid':
            return 'command_bento'
        from section_themes import HOME_SKINS, resolve_section_theme
        res = resolve_section_theme(settings, 'home')
        tok_skin = (res['theme'].get('tokens') or {}).get('layout_skin')
        return tok_skin if tok_skin in HOME_SKINS else 'classic'

    def publish(self, *_):
        raw = json.dumps(self._build_state(), ensure_ascii=False)
        if raw != self.last:
            self.last = raw
            self.changed.emit(raw)

    @Slot(str, str, str)
    def request(self, request_id, action, raw):
        try:
            if len(raw) > 4000 or len(request_id) > 80:
                raise ValueError('درخواست معتبر نیست.')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('درخواست معتبر نیست.')

            panel = self.panel
            owner = panel.owner
            value = None

            if action == 'refresh' and not data:
                self.last = ''
                self.publish()
            elif action == 'open_module' and set(data) == {'key'} and isinstance(data['key'], str):
                key = data['key']
                if key not in owner.modules or not allowed(owner, key):
                    raise ValueError('دسترسی به این بخش مجاز نیست.')
                owner.tabs.setCurrentWidget(owner.modules[key])
            elif action == 'open_calendar_day' and set(data) == {'date'} and isinstance(data['date'], str):
                if not allowed(owner, 'calendar'):
                    raise ValueError('دسترسی به تقویم مجاز نیست.')
                selected = parse_j(data['date'])
                owner.year, owner.month = selected.year, selected.month
                owner.selected_changed(selected)
                owner.tabs.setCurrentWidget(owner.modules['calendar'])
            elif action == 'open_assistant_prompt' and set(data) == {'prompt'} and isinstance(data['prompt'], str):
                if not allowed(owner, 'assistant', 'use'):
                    raise ValueError('دسترسی به دستیار هوشمند مجاز نیست.')
                owner.tabs.setCurrentWidget(owner.ai)
                prompt_text = data['prompt'].strip()
                if prompt_text and hasattr(owner.ai, 'prompt'):
                    owner.ai.prompt.setPlainText(prompt_text)
            elif action == 'open_my_day' and not data:
                if not allowed(owner, 'workspace'):
                    raise ValueError('دسترسی به کارها و پیگیری‌ها فعال نیست.')
                owner.tabs.setCurrentWidget(owner.workspace)
                owner.workspace.view.setCurrentIndex(2)
            elif action in ('add_event', 'new_reminder') and not data:
                owner.add_event()
                self.last = ''
                self.publish()
            elif action == 'open_command_palette' and not data:
                from workspace_ui import CommandPalette
                CommandPalette(owner).exec()
            elif action == 'open_settings' and not data:
                if not allowed(owner, 'settings'):
                    raise ValueError('دسترسی به تنظیمات مجاز نیست.')
                owner.settings()
            elif action == 'toggle_theme' and not data:
                from navigation_shortcuts import toggle_theme
                if not toggle_theme(owner):
                    raise ValueError('تغییر حالت انجام نشد؛ تنظیمات و دسترسی را بررسی کنید.')
                self.last = ''
                self.publish()
            elif action == 'open_quote_source' and not data:
                panel.open_quote_source()
            elif action == 'open_occasion_source' and set(data) == {'url'} and isinstance(data['url'], str):
                url = data['url'].strip()
                if not url.startswith(('http://', 'https://')):
                    raise ValueError('نشانی منبع معتبر نیست.')
                from features_ui import open_official
                open_official(url)
            elif action == 'refresh_weather' and not data:
                ws = getattr(panel, 'weather_service', None)
                if ws is not None:
                    ws.next_check = 0
                    ws.refresh()
            elif action == 'compare_weather' and not data:
                ws = getattr(panel, 'weather_service', None)
                if ws is not None and hasattr(ws, 'compare'):
                    ws.compare()
            elif action == 'open_native_weather' and not data:
                panel.weather.show_details()
            elif action == 'show_native' and not data and self.show_native is not None:
                self.show_native()
            elif action == 'set_home_skin' and set(data) == {'skin'} and isinstance(data['skin'], str):
                from section_themes import HOME_SKINS
                skin = data['skin']
                if skin not in HOME_SKINS:
                    raise ValueError('سبک نمایش معتبر نیست.')
                settings = owner.data.setdefault('settings', {})
                settings['home_skin'] = skin
                try:
                    owner.persist()
                except Exception:
                    pass
                self.last = ''
                self.publish()
            else:
                raise ValueError('عملیات شناخته‌شده نیست.')

            self.completed.emit(request_id, json.dumps({'ok': True, 'value': value}, ensure_ascii=False))
        except Exception as exc:
            self.completed.emit(request_id, json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))

    def close(self):
        self.timer.stop()
        ws = getattr(self.panel, 'weather_service', None)
        if ws is not None:
            for sig in (ws.changed, ws.comparison_changed):
                try:
                    sig.disconnect(self.publish)
                except (RuntimeError, TypeError):
                    pass
