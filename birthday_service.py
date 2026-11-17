"""Jalali birthday calculations, configurable missing-day policy, and reminder/celebration logic."""
from datetime import date
import jdatetime
from storage import MONTHS, fa, month_last_day, normalize, today_j

MISSING_DAY_POLICIES = (
    ('last_day_of_month', 'آخرین روز همان ماه (۲۹ اسفند در سال غیرکبیسه)'),
    ('next_day', 'اول ماه بعد (۱ فروردین در سال غیرکبیسه)'),
    ('skip', 'عدم اجرا در سال‌های فاقد آن روز'),
)


def parse_birthday(value, missing_policy=None):
    """Validate and normalize a Jalali birthday dict or YYYY/MM/DD string; return None if empty."""
    if value is None or value == '' or value == {}:
        return None
    policy = missing_policy or 'last_day_of_month'
    if isinstance(value, dict):
        if not value.get('enabled', True) or not (value.get('year') and value.get('month') and value.get('day')):
            return None
        year = int(value['year'])
        month = int(value['month'])
        day = int(value['day'])
        policy = str(value.get('missing_day_policy') or policy)
    elif isinstance(value, str):
        clean = normalize(value).strip()
        if not clean:
            return None
        parts = clean.replace('-', '/').split('/')
        if len(parts) != 3:
            raise ValueError('تاریخ تولد شمسی را با قالب ۱۳۷۲/۰۸/۲۵ وارد کنید.')
        year, month, day = (int(p) for p in parts)
    else:
        raise ValueError('ساختار تاریخ تولد معتبر نیست.')

    current_year = today_j().year
    if not 1300 <= year <= current_year:
        raise ValueError(f'سال تولد باید بین ۱۳۰۰ تا {fa(current_year)} باشد.')
    if not 1 <= month <= 12:
        raise ValueError('ماه تولد باید بین ۱ تا ۱۲ باشد.')
    try:
        jd = jdatetime.date(year, month, day)
    except ValueError as exc:
        raise ValueError('روز انتخاب‌شده در سال و ماه تولد شمسی وجود ندارد.') from exc

    if policy not in {k for k, _ in MISSING_DAY_POLICIES}:
        policy = 'last_day_of_month'

    return {
        'year': jd.year,
        'month': jd.month,
        'day': jd.day,
        'date_jalali': f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}',
        'missing_day_policy': policy,
    }


def resolve_birthday_for_year(birth, target_year, default_policy='last_day_of_month'):
    """Resolve a birthday into a concrete Jalali date in `target_year`, applying missing-day policy."""
    if not birth:
        return None
    month = int(birth['month'])
    day = int(birth['day'])
    policy = birth.get('missing_day_policy') or default_policy
    if policy not in {k for k, _ in MISSING_DAY_POLICIES}:
        policy = 'last_day_of_month'
    try:
        return jdatetime.date(target_year, month, day)
    except ValueError:
        if policy == 'skip':
            return None
        if policy == 'next_day':
            return jdatetime.date(target_year + 1, 1, 1) if month == 12 else jdatetime.date(target_year, month + 1, 1)
        return jdatetime.date(target_year, month, month_last_day(target_year, month))


def next_birthday_occurrence(birth, today_g=None, default_policy='last_day_of_month'):
    """Return (resolved_jd, target_date_g, days_until, celebration_year) for the next upcoming occurrence."""
    parsed = parse_birthday(birth)
    if not parsed:
        return None
    today_g = today_g or date.today()
    today_jal = jdatetime.date.fromgregorian(date=today_g)
    candidates = []
    for yr in (today_jal.year - 1, today_jal.year, today_jal.year + 1):
        resolved = resolve_birthday_for_year(parsed, yr, default_policy)
        if resolved is None:
            continue
        g_dt = resolved.togregorian()
        if g_dt >= today_g:
            candidates.append((g_dt, resolved, (g_dt - today_g).days, yr))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    g_dt, resolved, diff, yr = candidates[0]
    return resolved, g_dt, diff, yr


def is_user_birthday_today(birth, today_g=None, default_policy='last_day_of_month'):
    """Return (is_birthday, celebration_year, resolved_jd) for `today_g`."""
    occ = next_birthday_occurrence(birth, today_g=today_g, default_policy=default_policy)
    if not occ:
        return False, None, None
    resolved, _g_dt, diff, yr = occ
    return diff == 0, yr, resolved


def format_birthday_day_month_fa(birth):
    """Readable Persian day and month label, e.g. '۲۵ آبان'."""
    parsed = parse_birthday(birth)
    if not parsed:
        return ''
    return f"{fa(parsed['day'])} {MONTHS[parsed['month'] - 1]}"


def format_birthday_full_fa(birth):
    """Readable full Jalali birthday label."""
    parsed = parse_birthday(birth)
    if not parsed:
        return ''
    return f"{fa(parsed['day'])} {MONTHS[parsed['month'] - 1]} {fa(parsed['year'])}"


def build_reminder_copy(fullname, birth, days_until):
    """Create Persian reminder title and body mentioning name and birthday."""
    name = str(fullname or 'همکار').strip()
    when_label = format_birthday_day_month_fa(birth)
    full_label = format_birthday_full_fa(birth)
    if days_until == 3:
        lead = '۳ روز دیگر'
    elif days_until == 1:
        lead = 'فردا'
    elif days_until == 0:
        lead = 'امروز'
    else:
        lead = f'{fa(days_until)} روز دیگر'
    title = f'یادآور تولد · {name}'
    body = f'{lead} ({when_label}) تولد {name} است. تاریخ ثبت‌شده: {full_label}.'
    return title, body
