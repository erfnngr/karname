"""Per-section theme catalog, safe JSON/CSS theme importer, and token resolver."""
import json
import re
from appearance import DARK, LIGHT, accent_foreground, contrast
from theme_catalog import PALETTES, THEMES, preset

HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
CSS_VAR_RE = re.compile(r'--([a-zA-Z0-9_-]{2,48})\s*:\s*([^;{}\n]{1,160});')
SAFE_GRADIENT_RE = re.compile(
    r'^(linear-gradient|radial-gradient)\([a-zA-Z0-9#(),.%\s+-]{4,220}\)$'
)
COLOR_KEYS = (
    'bg', 'panel', 'text', 'muted', 'border', 'field',
    'button', 'hover', 'accent', 'selected', 'today', 'danger', 'warning', 'nav',
)

# Ordered list of every customizable area of Karname:
# (key, title, kind, protected_by_default)
SECTIONS = (
    ('sidebar', 'نوار کناری و سربرگ', 'qt', False),
    ('home', 'صفحه خانه', 'react', False),
    ('workspace', 'کارها و پیگیری‌ها', 'qt', False),
    ('calendar', 'تقویم و ماه جاری', 'qt', False),
    ('calculation', 'محاسبه و حقوق', 'qt', False),
    ('clients', 'فاکتورها و مشتریان', 'qt', False),
    ('desk', 'کارتابل من', 'qt', False),
    ('company', 'فضای شرکت', 'qt', False),
    ('services', 'سامانه‌ها و خبرها', 'qt', False),
    ('attendance', 'تردد و ساعت کار', 'qt', False),
    ('occasions', 'مناسبت‌ها', 'qt', False),
    ('chat', 'چت شرکت', 'react', True),
    ('assistant', 'دستیار هوشمند', 'react', True),
    ('tax', 'مالیات', 'react', True),
)
SECTION_MAP = {key: (title, kind, protected) for key, title, kind, protected in SECTIONS}
PROTECTED_SECTIONS = frozenset(k for k, _, _, p in SECTIONS if p)
POLICIES = ('locked', 'limited', 'full')
HOME_SKINS = ('classic', 'command_bento')
EFFECT_STYLES = ('none', 'spotlight', 'aurora', 'shimmer')


def _safe_hex(value, fallback):
    if isinstance(value, str):
        val = value.strip()
        if HEX_RE.match(val):
            return val.upper()
    return fallback


def _safe_int(value, low, high, fallback):
    try:
        num = int(round(float(value)))
        return max(low, min(high, num))
    except (TypeError, ValueError):
        return fallback


def _safe_float(value, low, high, fallback):
    try:
        num = float(value)
        return max(low, min(high, num))
    except (TypeError, ValueError):
        return fallback


def _safe_gradient(value):
    if not isinstance(value, str):
        return ''
    text = ' '.join(value.strip().split())
    if not text or 'url(' in text.lower() or 'expression(' in text.lower():
        return ''
    return text if SAFE_GRADIENT_RE.match(text) else ''


def _luminance(hex_color):
    c = hex_color.lstrip('#')
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def base_palette(preset_key='default', mode='light'):
    """Return full color dict for a built-in preset and mode."""
    p = preset(preset_key)
    dark = mode == 'dark'
    colors = PALETTES.get(p)
    base = dict(colors[1 if dark else 0] if colors else (DARK if dark else LIGHT))
    base.setdefault('nav', '#0F273B' if dark else '#12314A')
    return base


def normalize_theme(raw, fallback_id='custom_theme'):
    """Validate and fill missing fields for a theme dictionary."""
    if not isinstance(raw, dict):
        raw = {}
    mode = 'dark' if str(raw.get('mode', '')).lower() == 'dark' else 'light'
    defaults = base_palette('default', mode)
    src_colors = raw.get('colors') if isinstance(raw.get('colors'), dict) else raw
    colors = {k: _safe_hex(src_colors.get(k), defaults[k]) for k in COLOR_KEYS}

    if _safe_hex(src_colors.get('nav'), '') == '':
        colors['nav'] = colors['panel'] if mode == 'dark' else '#12314A'

    src_tokens = raw.get('tokens') if isinstance(raw.get('tokens'), dict) else {}
    shadow = str(src_tokens.get('shadow', raw.get('shadow', 'soft'))).lower()
    if shadow not in ('none', 'soft', 'strong'):
        shadow = 'soft'
    radius = _safe_int(src_tokens.get('radius', raw.get('radius', 14)), 0, 28, 14)
    glass_alpha = _safe_int(src_tokens.get('glass_alpha', raw.get('glass_alpha', 82)), 20, 100, 82)
    glass_blur = _safe_int(src_tokens.get('glass_blur', raw.get('glass_blur', 16)), 0, 32, 16)
    font_scale = round(_safe_float(src_tokens.get('font_scale', raw.get('font_scale', 1.0)), 0.85, 1.25, 1.0), 2)
    bg_gradient = _safe_gradient(src_tokens.get('bg_gradient', raw.get('bg_gradient', '')))
    layout_skin = str(src_tokens.get('layout_skin', raw.get('layout_skin', 'classic'))).lower()
    if layout_skin not in HOME_SKINS:
        layout_skin = 'classic'
    effect = str(src_tokens.get('effect', raw.get('effect', 'none'))).lower()
    if effect not in EFFECT_STYLES:
        effect = 'none'

    raw_vars = src_tokens.get('vars') if isinstance(raw_vars := src_tokens.get('vars'), dict) else {}
    safe_vars = {}
    for k, v in list(raw_vars.items())[:24]:
        if isinstance(k, str) and re.match(r'^--[a-zA-Z0-9_-]{2,48}$', k.strip()) and isinstance(v, str):
            val = v.strip()
            if len(val) <= 120 and 'url(' not in val.lower() and '<' not in val and ';' not in val:
                safe_vars[k.strip()] = val

    tid = str(raw.get('id') or fallback_id or 'custom_theme').strip()
    tid = re.sub(r'[^a-zA-Z0-9_-]', '_', tid)[:48] or 'custom_theme'
    name = str(raw.get('name') or 'تم سفارشی').strip()[:60] or 'تم سفارشی'

    return {
        'id': tid,
        'name': name,
        'mode': mode,
        'colors': colors,
        'tokens': {
            'radius': radius,
            'glass_alpha': glass_alpha,
            'glass_blur': glass_blur,
            'shadow': shadow,
            'font_scale': font_scale,
            'bg_gradient': bg_gradient,
            'layout_skin': layout_skin,
            'effect': effect,
            'vars': safe_vars,
        },
    }


def list_all_themes(settings):
    """Return ordered list of built-in + user custom themes with full definitions."""
    items = []
    for key, title, default_mode in THEMES:
        items.append({
            'id': key,
            'name': title,
            'builtin': True,
            'mode': default_mode,
            'colors': base_palette(key, default_mode),
            'tokens': {
                'radius': 15 if key == 'glass_mist' else 10 if key in ('emerald_ivory', 'violet_modular') else 12,
                'glass_alpha': 84,
                'shadow': 'soft',
                'font_scale': 1.0,
                'bg_gradient': '',
                'vars': {},
            },
        })
    customs = (settings or {}).get('custom_themes') or {}
    if isinstance(customs, dict):
        for tid, raw in customs.items():
            norm = normalize_theme(raw, fallback_id=str(tid))
            norm['id'] = str(tid)
            norm['builtin'] = False
            items.append(norm)
    return items


def _css_hex(val):
    v = val.strip()
    if re.match(r'^#[0-9A-Fa-f]{6}$', v):
        return v.upper()
    m = re.match(r'^#([0-9A-Fa-f]{3})$', v)
    if m:
        s = m.group(1)
        return ('#' + ''.join(ch * 2 for ch in s)).upper()
    return ''


def parse_imported_theme(text, fallback_name='تم واردشده'):
    """Parse JSON or CSS variable blocks sent by user/design into a validated theme dict.

    Supports either a single theme payload or a multi-section bundle (`themes` / `sections`).
    Returns dict: `{'themes': [normalized_theme, ...], 'sections': {sec: theme_id}}`.
    """
    raw_text = (text or '').strip()
    if not raw_text:
        raise ValueError('متن تم خالی است.')

    # 1. Try JSON payload
    if raw_text.startswith('{') or raw_text.startswith('['):
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f'فرمت JSON معتبر نیست: {exc.msg}') from exc
        if isinstance(data, list):
            themes = [normalize_theme(item, fallback_id=f'imported_{i+1}') for i, item in enumerate(data) if isinstance(item, dict)]
            if not themes:
                raise ValueError('هیچ تم معتبری در فهرست پیدا نشد.')
            return {'themes': themes, 'sections': {}}
        if isinstance(data, dict):
            if isinstance(data.get('themes'), list) or isinstance(data.get('themes'), dict):
                raw_themes = data['themes']
                themes = []
                if isinstance(raw_themes, dict):
                    for k, v in raw_themes.items():
                        if isinstance(v, dict):
                            themes.append(normalize_theme({**v, 'id': k}, fallback_id=str(k)))
                else:
                    for i, v in enumerate(raw_themes):
                        if isinstance(v, dict):
                            themes.append(normalize_theme(v, fallback_id=f'imported_{i+1}'))
                sec_map = data.get('sections') if isinstance(data.get('sections'), dict) else {}
                return {'themes': themes, 'sections': {str(k): str(v) for k, v in sec_map.items() if k in SECTION_MAP}}
            theme_obj = data.get('theme') if isinstance(data.get('theme'), dict) else data
            norm = normalize_theme(theme_obj)
            if not theme_obj.get('name'):
                norm['name'] = fallback_name
            sec_map = data.get('sections') if isinstance(data.get('sections'), dict) else {}
            return {'themes': [norm], 'sections': {str(k): str(v) for k, v in sec_map.items() if k in SECTION_MAP}}

    # 2. Fallback: extract CSS custom properties (`--color-background`, `--bg`, `--accent`, etc.)
    extracted = {}
    safe_vars = {}
    bg_gradient = ''
    radius = 14
    for match in CSS_VAR_RE.finditer(raw_text):
        var_name = match.group(1).lower()
        val = match.group(2).strip()
        hx = _css_hex(val)
        if var_name in ('bg', 'background', 'color-background', 'app-bg'):
            if hx:
                extracted['bg'] = hx
        elif var_name in ('panel', 'card', 'surface', 'color-card', 'app-panel'):
            if hx:
                extracted['panel'] = hx
        elif var_name in ('text', 'fg', 'foreground', 'color-foreground', 'app-text'):
            if hx:
                extracted['text'] = hx
        elif var_name in ('muted', 'muted-foreground', 'color-muted-foreground', 'app-muted'):
            if hx:
                extracted['muted'] = hx
        elif var_name in ('border', 'color-border', 'app-border'):
            if hx:
                extracted['border'] = hx
        elif var_name in ('field', 'input', 'color-input'):
            if hx:
                extracted['field'] = hx
        elif var_name in ('button', 'secondary', 'color-secondary', 'color-muted'):
            if hx:
                extracted['button'] = hx
        elif var_name in ('hover', 'accent-bg', 'color-accent'):
            if hx:
                extracted['hover'] = hx
        elif var_name in ('accent', 'primary', 'color-primary', 'app-accent'):
            if hx:
                extracted['accent'] = hx
        elif var_name in ('nav', 'sidebar', 'color-sidebar'):
            if hx:
                extracted['nav'] = hx
        elif var_name in ('radius', 'card-radius', 'radius-lg'):
            m_rad = re.match(r'^(\d{1,2})', val)
            if m_rad:
                radius = _safe_int(m_rad.group(1), 0, 28, 14)
        elif var_name in ('home-bg', 'bg-gradient', 'background-image'):
            g = _safe_gradient(val)
            if g:
                bg_gradient = g
        elif hx and len(safe_vars) < 20:
            safe_vars['--' + var_name] = hx

    if not extracted:
        raise ValueError('رنگ یا متغیر معتبری در متن ارسالی پیدا نشد (JSON یا متغیرهای CSS ارسال کنید).')

    bg = extracted.get('bg', '#F3F6FA')
    mode = 'dark' if _luminance(bg) < 0.4 else 'light'
    norm = normalize_theme({
        'name': fallback_name,
        'mode': mode,
        'colors': extracted,
        'tokens': {
            'radius': radius,
            'bg_gradient': bg_gradient,
            'vars': safe_vars,
        },
    })
    return {'themes': [norm], 'sections': {}}


def _lookup_theme(settings, theme_ref, global_mode):
    if isinstance(theme_ref, dict):
        return normalize_theme(theme_ref)
    if isinstance(theme_ref, str) and theme_ref:
        customs = (settings or {}).get('custom_themes') or {}
        if isinstance(customs, dict) and theme_ref in customs and isinstance(customs[theme_ref], dict):
            return normalize_theme({**customs[theme_ref], 'id': theme_ref}, fallback_id=theme_ref)
        builtin_keys = {k for k, _, _ in THEMES}
        if theme_ref in builtin_keys:
            return {
                'id': theme_ref,
                'name': dict((k, t) for k, t, _ in THEMES).get(theme_ref, theme_ref),
                'mode': global_mode,
                'colors': base_palette(theme_ref, global_mode),
                'tokens': {'radius': 15 if theme_ref == 'glass_mist' else 10, 'glass_alpha': 84, 'shadow': 'soft', 'font_scale': 1.0, 'bg_gradient': '', 'vars': {}},
            }
    global_preset = preset((settings or {}).get('theme_preset', 'default'))
    return {
        'id': global_preset,
        'name': 'تم عمومی برنامه',
        'mode': global_mode,
        'colors': base_palette(global_preset, global_mode),
        'tokens': {'radius': 15 if global_preset == 'glass_mist' else 10, 'glass_alpha': 84, 'shadow': 'soft', 'font_scale': 1.0, 'bg_gradient': '', 'vars': {}},
    }


def resolve_section_theme(settings, section_key):
    """Resolve the active theme colors, tokens, and override flags for a specific section."""
    settings = settings or {}
    global_mode = 'dark' if settings.get('theme') == 'dark' else 'light'
    global_theme = _lookup_theme(settings, preset(settings.get('theme_preset', 'default')), global_mode)

    section_themes = settings.get('section_themes') or {}
    assigned_ref = section_themes.get(section_key) if isinstance(section_themes, dict) else None
    has_custom = bool(assigned_ref)

    policies = settings.get('section_policies') or {}
    is_protected = section_key in PROTECTED_SECTIONS
    policy = policies.get(section_key, 'locked' if is_protected else 'full') if isinstance(policies, dict) else ('locked' if is_protected else 'full')
    if policy not in POLICIES:
        policy = 'locked' if is_protected else 'full'
    if not is_protected:
        policy = 'full'

    if not has_custom or policy == 'locked':
        return {
            'section': section_key,
            'overridden': False,
            'policy': policy,
            'theme': global_theme,
        }

    chosen = _lookup_theme(settings, assigned_ref, global_mode)
    if is_protected and policy == 'limited':
        # Keep the section's own base surface/mode and only adapt its accent highlight cleanly.
        merged_colors = dict(global_theme['colors'])
        accent = chosen['colors']['accent']
        # Ensure readable contrast against the base surface
        if contrast(accent, merged_colors['panel']) < 2.2:
            accent = global_theme['colors']['accent']
        merged_colors['accent'] = accent
        merged_theme = {
            'id': chosen['id'],
            'name': chosen['name'],
            'mode': global_theme['mode'],
            'colors': merged_colors,
            'tokens': dict(global_theme['tokens']),
        }
        return {
            'section': section_key,
            'overridden': True,
            'policy': 'limited',
            'theme': merged_theme,
        }

    return {
        'section': section_key,
        'overridden': True,
        'policy': 'full',
        'theme': chosen,
    }


def section_appearance_payload(settings, section_key='default'):
    """Build JSON-serializable payload sent to ReactAppearanceBridge."""
    if section_key not in SECTION_MAP:
        global_mode = 'dark' if (settings or {}).get('theme') == 'dark' else 'light'
        t = _lookup_theme(settings, preset((settings or {}).get('theme_preset', 'default')), global_mode)
        c = t['colors']
        return {
            'section': section_key,
            'policy': 'full',
            'dark': global_mode == 'dark',
            'colors': {
                **{k: c[k] for k in ('bg', 'panel', 'text', 'muted', 'border', 'field', 'button', 'hover', 'accent')},
                'accent_text': accent_foreground(c['accent']),
            },
            'tokens': t['tokens'],
        }

    resolved = resolve_section_theme(settings, section_key)
    theme = resolved['theme']
    c = theme['colors']
    return {
        'section': section_key,
        'preset': theme.get('id', 'default'),
        'policy': resolved['policy'],
        'overridden': resolved['overridden'],
        'dark': theme['mode'] == 'dark',
        'colors': {
            **{k: c[k] for k in ('bg', 'panel', 'text', 'muted', 'border', 'field', 'button', 'hover', 'accent')},
            'accent_text': accent_foreground(c['accent']),
        },
        'tokens': theme['tokens'],
    }


def apply_theme_to_sections(settings, theme_id, include_protected=False, protected_policy='limited', targets=None):
    """Assign `theme_id` to selected or standard sections inside `settings`."""
    section_themes = dict(settings.get('section_themes') or {})
    section_policies = dict(settings.get('section_policies') or {})
    keys = list(targets) if targets is not None else [k for k, _, _, _ in SECTIONS]
    for key in keys:
        if key not in SECTION_MAP:
            continue
        if key in PROTECTED_SECTIONS:
            if include_protected:
                section_themes[key] = theme_id
                section_policies[key] = protected_policy if protected_policy in POLICIES else 'limited'
        else:
            section_themes[key] = theme_id
    settings['section_themes'] = section_themes
    settings['section_policies'] = section_policies


def clear_section_theme(settings, section_key):
    """Reset a section back to inheriting the global appearance."""
    section_themes = dict(settings.get('section_themes') or {})
    section_themes.pop(section_key, None)
    settings['section_themes'] = section_themes
