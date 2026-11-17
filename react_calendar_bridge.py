"""Adapter between the React 21st.dev EventManager x Jalali Calendar view and Karname events/occasions/birthdays."""
import copy
from datetime import date, datetime, timedelta
import json
import jdatetime
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from brand import event_type
from iran_calendar import day_off
from occasions import on_date as occasions_on_date
from reminders import effective_leads, group_of
from storage import MONTHS, WEEKDAYS, due_on, fa, jalali_date, jformat, month_last_day, new_event, normalize, occurrence, parse_j, today_j
from ui_permissions import allowed

ALLOWED_COLORS = {'sky', 'emerald', 'amber', 'rose', 'indigo', 'teal'}


def _event_color(ev):
    explicit = str(ev.get('color') or '').strip().lower()
    if explicit in ALLOWED_COLORS:
        return explicit
    kind = event_type(ev)
    if kind == 'tax':
        return 'sky'
    if kind == 'insurance':
        return 'amber'
    if ev.get('shared_id'):
        return 'indigo'
    return 'emerald'


def _event_category(ev):
    raw = str(ev.get('category') or '').strip()
    if raw:
        return raw
    kind = event_type(ev)
    return {'tax': 'مالیات', 'insurance': 'بیمه'}.get(kind, 'شخصی')


class ReactCalendarBridge(QObject):
    """Expose Karname Jalali/Gregorian events, occasions, birthdays, and editing operations to React."""

    changed = Signal(str)
    completed = Signal(str, str)

    def __init__(self, panel, parent=None, show_native=None):
        super().__init__(parent)
        self.panel = panel
        self.show_native = show_native
        self.last = ''
        self._grid_cache_key = None
        self._grid_cache_days = []
        self._occ_cache_key = None
        self._occ_cache_val = []
        self.timer = QTimer(self)
        self.timer.setInterval(2200)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        from react_design_host import should_poll_section
        if not should_poll_section(self._owner(), self.panel):
            return
        self.publish()

    def _owner(self):
        # panel may be owner.calendar_page whose parent chain is owner
        return getattr(self.panel, 'owner', None) or self.panel.window()

    def _build_state(self):
        owner = self._owner()
        settings = owner.data.get('settings', {}) if hasattr(owner, 'data') else {}
        prefs = owner.data.get('preferences', {}) if hasattr(owner, 'data') else {}
        today = today_j()
        g_today = date.today()

        year = getattr(owner, 'year', today.year)
        month = getattr(owner, 'month', today.month)
        selected = getattr(owner, 'selected', today)
        first = jalali_date(year, month, 1)
        last_day = month_last_day(year, month)
        last = jalali_date(year, month, last_day)
        offset = (first.togregorian().weekday() + 2) % 7
        greg_range = f"{first.togregorian():%B %Y} — {last.togregorian():%B %Y}"

        show_greg = bool(prefs.get('calendar_gregorian', True))
        show_occ = bool(prefs.get('calendar_occasions', True))
        show_tasks = bool(prefs.get('calendar_tasks', True))

        sel_str = f'{selected.year:04d}/{selected.month:02d}/{selected.day:02d}'
        today_str = f'{today.year:04d}/{today.month:02d}/{today.day:02d}'
        grid_key = (year, month, sel_str, today_str, show_occ)
        if grid_key == getattr(self, '_grid_cache_key', None):
            days_grid = self._grid_cache_days
        else:
            days_grid = []
            # 42 cells (6 weeks) centered on active Jalali month
            grid_start_g = first.togregorian() - timedelta(days=offset)
            for idx in range(42):
                gd = grid_start_g + timedelta(days=idx)
                jd = jdatetime.date.fromgregorian(date=gd)
                in_month = jd.year == year and jd.month == month
                occ_list = [
                    {'title': str(o.get('title', '')), 'holiday': bool(o.get('holiday')), 'source': str(o.get('source', '') or '')}
                    for o in (occasions_on_date(gd) if show_occ else [])
                ]
                days_grid.append({
                    'day': jd.day,
                    'day_fa': fa(jd.day),
                    'date_jalali': f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}',
                    'date_gregorian': gd.isoformat(),
                    'greg_label': gd.strftime('%d %b'),
                    'in_month': in_month,
                    'is_today': jd == today,
                    'is_selected': jd == selected,
                    'is_holiday': bool(day_off(gd)),
                    'weekday_idx': idx % 7,
                    'occasions': occ_list,
                })
            self._grid_cache_key = grid_key
            self._grid_cache_days = days_grid

        # Serialize real calendar events (personal + shared + desk notes)
        events_out = []
        all_events = owner.display_events() if hasattr(owner, 'display_events') else []
        for ev in all_events:
            ev_id = str(ev.get('id') or '')
            if not ev_id:
                continue
            ref_date = owner.event_reference_date(ev) if hasattr(owner, 'event_reference_date') else None
            if ref_date is None and ev.get('date_jalali'):
                try:
                    ref_date = parse_j(ev['date_jalali']).togregorian()
                except Exception:
                    ref_date = None
            date_j = str(ev.get('date_jalali') or '')
            if not date_j and ref_date is not None:
                jd_ref = jdatetime.date.fromgregorian(date=ref_date)
                date_j = f'{jd_ref.year:04d}/{jd_ref.month:02d}/{jd_ref.day:02d}'
            is_shared = bool(ev.get('shared_id'))
            is_desk = bool(ev.get('desk_note_id'))
            source_kind = 'shared' if is_shared else 'desk_note' if is_desk else 'personal'
            tags = [x for x in (ev.get('tags') or []) if isinstance(x, str)]
            if not tags:
                tags = [str(ev.get('company') or 'شخصی'), _event_category(ev)]
                if ev.get('recurrence', 'بدون تکرار') != 'بدون تکرار':
                    tags.append(ev['recurrence'])
            events_out.append({
                'id': ev_id,
                'title': str(ev.get('title', '')),
                'notes': str(ev.get('notes', '')),
                'company': str(ev.get('company') or 'شخصی'),
                'category': _event_category(ev),
                'color': _event_color(ev),
                'priority': str(ev.get('priority') or 'متوسط'),
                'recurrence': str(ev.get('recurrence') or 'بدون تکرار'),
                'date_jalali': normalize(date_j),
                'date_gregorian': ref_date.isoformat() if ref_date else '',
                'done': bool(ev.get('done') or (ref_date and ref_date.isoformat() in ev.get('completed_occurrences', []))),
                'needs_review': bool(ev.get('needs_review')),
                'source_kind': source_kind,
                'editable': not is_shared and not is_desk,
                'tags': tags[:4],
                'start_hour': str(ev.get('start_hour') or ''),
                'end_hour': str(ev.get('end_hour') or ''),
            })

        # Add teammates' birthdays into calendar view
        bdays = getattr(getattr(owner, 'org', None), 'birthdays', None) or []
        for b in bdays:
            events_out.append({
                'id': f"birthday-{b.get('user_id')}",
                'title': f"تولد {b.get('fullname', 'همکار')}" + (' (شما)' if b.get('is_self') else ''),
                'notes': f"جشن و یادآور تولد · {b.get('label_fa', '')}",
                'company': 'همکاران',
                'category': 'تولد',
                'color': 'rose',
                'priority': 'عادی',
                'recurrence': 'سالانه',
                'date_jalali': str(b.get('next_date_j') or ''),
                'date_gregorian': str(b.get('next_date_g') or ''),
                'done': False,
                'needs_review': False,
                'source_kind': 'birthday',
                'editable': False,
                'tags': ['تولد همکاران', b.get('label_fa', '')],
                'start_hour': '',
                'end_hour': '',
            })

        occ_key = (sel_str, show_occ)
        if occ_key == getattr(self, '_occ_cache_key', None):
            selected_occ = self._occ_cache_val
        else:
            selected_occ = [
                {'title': str(o.get('title', '')), 'holiday': bool(o.get('holiday')), 'source': str(o.get('source', '') or '')}
                for o in (occasions_on_date(selected.togregorian()) if show_occ else [])
            ]
            self._occ_cache_key = occ_key
            self._occ_cache_val = selected_occ

        return {
            'title': str(prefs.get('calendar_name') or 'تقویم'),
            'today': {
                'year': today.year,
                'month': today.month,
                'day': today.day,
                'jalali': jformat(today),
                'gregorian': g_today.isoformat(),
            },
            'view': {
                'year': year,
                'month': month,
                'year_fa': fa(year),
                'month_name': MONTHS[month - 1],
                'greg_range': greg_range,
                'selected_jalali': f'{selected.year:04d}/{selected.month:02d}/{selected.day:02d}',
                'selected_fa': jformat(selected),
                'selected_gregorian': selected.togregorian().isoformat(),
                'selected_occasions': selected_occ,
            },
            'weekdays': list(WEEKDAYS),
            'months': list(MONTHS),
            'days': days_grid,
            'events': events_out,
            'companies': list(owner.data.get('companies', ['شخصی'])),
            'preferences': {
                'show_gregorian': show_greg,
                'show_occasions': show_occ,
                'show_tasks': show_tasks,
            },
            'permissions': {
                'create': bool(allowed(owner, 'calendar', 'create')),
                'edit': bool(allowed(owner, 'calendar', 'edit')),
                'delete': bool(allowed(owner, 'calendar', 'delete')),
                'export': bool(allowed(owner, 'calendar', 'export')),
            },
            'theme': settings.get('theme', 'light'),
            'theme_preset': settings.get('theme_preset', 'default'),
        }

    def publish(self, *_):
        raw = json.dumps(self._build_state(), ensure_ascii=False)
        if raw != self.last:
            self.last = raw
            self.changed.emit(raw)

    def _find_event(self, owner, ev_id):
        for ev in owner.events:
            if ev.get('id') == ev_id:
                return ev, True
        for ev in owner.display_events():
            if ev.get('id') == ev_id:
                return ev, False
        return None, False

    @Slot(str, str, str)
    def request(self, request_id, action, raw):
        try:
            if len(raw) > 16000 or len(request_id) > 80:
                raise ValueError('درخواست معتبر نیست.')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('درخواست معتبر نیست.')
            owner = self._owner()
            value = None

            if action == 'refresh':
                self.last = ''
                self.publish()
            elif action == 'select_date' and isinstance(data.get('date_jalali'), str):
                jd = parse_j(data['date_jalali'])
                owner.year = jd.year
                owner.month = jd.month
                owner.selected_changed(jd)
            elif action == 'shift_month' and isinstance(data.get('delta'), int):
                delta = 1 if data['delta'] > 0 else -1
                owner.shift_month(delta)
            elif action == 'goto_today':
                owner.goto_today()
            elif action == 'jump_ym':
                yr = max(1300, min(1499, int(data.get('year', owner.year))))
                mo = max(1, min(12, int(data.get('month', owner.month))))
                owner.year = yr
                owner.month = mo
                owner.selected = jalali_date(yr, mo, min(owner.selected.day, month_last_day(yr, mo)))
                owner.refresh()
            elif action == 'create_event':
                if not allowed(owner, 'calendar', 'create'):
                    raise ValueError('دسترسی ایجاد یادآور برای این حساب فعال نیست.')
                title = str(data.get('title') or '').strip()[:140]
                if not title:
                    raise ValueError('عنوان رویداد را وارد کنید.')
                jd = parse_j(str(data.get('date_jalali') or ''))
                company = str(data.get('company') or 'شخصی').strip() or 'شخصی'
                category = str(data.get('category') or 'مالیات').strip()
                priority = str(data.get('priority') or 'مهم')
                recurrence = str(data.get('recurrence') or 'بدون تکرار')
                notes = str(data.get('notes') or '').strip()[:4000]
                color = str(data.get('color') or '').strip()
                date_str = f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}'
                ev = new_event(company, title, date_str, notes, priority, recurrence, owner.data['settings'].get('personal_lead_days'))
                ev['category'] = category
                ev['reminder_group'] = 'personal' if company == 'شخصی' else 'default'
                if color in ALLOWED_COLORS:
                    ev['color'] = color
                if isinstance(data.get('tags'), list):
                    ev['tags'] = [str(t)[:24] for t in data['tags'][:4] if str(t).strip()]
                for tk in ('start_hour', 'end_hour'):
                    if data.get(tk):
                        ev[tk] = str(data[tk])[:5]
                owner.events.append(ev)
                if company not in owner.data['companies']:
                    owner.data['companies'].append(company)
                    owner.update_companies()
                owner.persist()
                owner.refresh()
                value = {'id': ev['id']}
            elif action == 'update_event':
                if not allowed(owner, 'calendar', 'edit'):
                    raise ValueError('دسترسی ویرایش یادآور فعال نیست.')
                ev_id = str(data.get('id') or '')
                ev, is_personal = self._find_event(owner, ev_id)
                if ev is None:
                    raise ValueError('رویداد پیدا نشد.')
                if not is_personal:
                    owner.edit_event(ev)
                    return self.completed.emit(request_id, json.dumps({'ok': True, 'value': None}, ensure_ascii=False))
                title = str(data.get('title') or ev['title']).strip()[:140]
                if not title:
                    raise ValueError('عنوان رویداد نمی‌تواند خالی باشد.')
                jd = parse_j(str(data.get('date_jalali') or ev['date_jalali']))
                date_str = f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}'
                old_sig = (ev.get('date_jalali'), ev.get('recurrence'))
                ev.update(
                    title=title,
                    date_jalali=date_str,
                    company=str(data.get('company') or ev.get('company', 'شخصی')).strip() or 'شخصی',
                    category=str(data.get('category') or ev.get('category', 'مالیات')),
                    priority=str(data.get('priority') or ev.get('priority', 'مهم')),
                    recurrence=str(data.get('recurrence') or ev.get('recurrence', 'بدون تکرار')),
                    notes=str(data.get('notes') if 'notes' in data else ev.get('notes', ''))[:4000],
                    needs_review=False,
                    review_reason='',
                    snooze_until=None,
                )
                if str(data.get('color') or '') in ALLOWED_COLORS:
                    ev['color'] = str(data['color'])
                if isinstance(data.get('tags'), list):
                    ev['tags'] = [str(t)[:24] for t in data['tags'][:4] if str(t).strip()]
                for tk in ('start_hour', 'end_hour'):
                    if tk in data:
                        ev[tk] = str(data.get(tk) or '')[:5]
                if old_sig != (ev.get('date_jalali'), ev.get('recurrence')):
                    ev['last_alerts'] = {}
                if ev['company'] not in owner.data['companies']:
                    owner.data['companies'].append(ev['company'])
                    owner.update_companies()
                owner.persist()
                owner.refresh()
            elif action == 'reschedule_event':
                if not allowed(owner, 'calendar', 'edit'):
                    raise ValueError('دسترسی جابه‌جایی رویداد فعال نیست.')
                ev_id = str(data.get('id') or '')
                ev, is_personal = self._find_event(owner, ev_id)
                if ev is None:
                    raise ValueError('رویداد پیدا نشد.')
                if not is_personal:
                    raise ValueError('رویدادهای مشترک شرکت را از بخش کارها و فضای شرکت ویرایش کنید.')
                jd = parse_j(str(data.get('date_jalali') or ''))
                ev['date_jalali'] = f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}'
                ev['last_alerts'] = {}
                ev['snooze_until'] = None
                ev['needs_review'] = False
                owner.persist()
                owner.refresh()
            elif action == 'toggle_done':
                if not allowed(owner, 'calendar', 'edit'):
                    raise ValueError('دسترسی تغییر وضعیت فعال نیست.')
                ev_id = str(data.get('id') or '')
                ev, _ = self._find_event(owner, ev_id)
                if ev is None:
                    raise ValueError('رویداد پیدا نشد.')
                when = None
                if data.get('date_jalali'):
                    try:
                        when = parse_j(str(data['date_jalali'])).togregorian()
                    except ValueError:
                        when = None
                owner.set_done(ev, bool(data.get('done')), when=when)
            elif action == 'delete_event':
                if not allowed(owner, 'calendar', 'delete'):
                    raise ValueError('دسترسی حذف یادآور فعال نیست.')
                ev_id = str(data.get('id') or '')
                ev, is_personal = self._find_event(owner, ev_id)
                if ev is None:
                    raise ValueError('رویداد پیدا نشد.')
                if not is_personal:
                    raise ValueError('رویدادهای مشترک شرکت فقط از میز کار یا فضای شرکت حذف می‌شوند.')
                owner.data.setdefault('event_trash', []).append(
                    {'event': copy.deepcopy(ev), 'deleted_at': datetime.now().astimezone().isoformat()}
                )
                owner.events.remove(ev)
                owner.persist()
                owner.refresh()
            elif action == 'open_native_add':
                owner.add_event()
            elif action == 'open_native_edit':
                ev, _ = self._find_event(owner, str(data.get('id') or ''))
                if ev is not None:
                    owner.edit_event(ev)
            elif action == 'import_excel':
                owner.import_spreadsheet()
            elif action == 'export_ics':
                owner.export_ics()
            elif action == 'open_occasions':
                owner.show_occasions()
            elif action == 'open_occasion_source' and isinstance(data.get('url'), str):
                from features_ui import open_official
                open_official(data['url'])
            elif action == 'calculate_penalty':
                ev, _ = self._find_event(owner, str(data.get('id') or ''))
                if ev is not None and hasattr(owner, 'calculator'):
                    owner.tabs.setCurrentWidget(owner.calculation_page)
                    owner.calculator.select_for_event(ev)
            elif action == 'show_native' and self.show_native is not None:
                self.show_native()
            else:
                raise ValueError('عملیات تقویم شناخته‌شده نیست.')

            self.last = ''
            self.publish()
            self.completed.emit(request_id, json.dumps({'ok': True, 'value': value}, ensure_ascii=False))
        except Exception as exc:
            self.completed.emit(request_id, json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))

    def close(self):
        self.timer.stop()
