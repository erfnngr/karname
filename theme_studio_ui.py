"""Interactive Per-Section Theme Studio & JSON/CSS Theme Importer for Karname."""
import copy
import json
import uuid
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from color_wheel import ColorWheelDialog
from section_themes import (
    PROTECTED_SECTIONS,
    SECTIONS,
    SECTION_MAP,
    apply_theme_to_sections,
    clear_section_theme,
    list_all_themes,
    normalize_theme,
    parse_imported_theme,
    resolve_section_theme,
)

COLOR_LABELS = (
    ('bg', 'پس‌زمینه اصلی'),
    ('panel', 'کارت و پنل'),
    ('text', 'متن اصلی'),
    ('muted', 'متن فرعی'),
    ('accent', 'رنگ تاکیدی (دکمه/شاخص)'),
    ('border', 'خطوط و حاشیه'),
    ('field', 'کادر ورودی'),
    ('button', 'پس‌زمینه دکمه'),
    ('hover', 'حالت اشاره (Hover)'),
    ('nav', 'نوار کناری / سربرگ'),
)


class ThemeImportDialog(QDialog):
    """Dialog allowing user to paste or load JSON / CSS theme definitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ورود تم سفارشی (JSON یا CSS)')
        self.resize(620, 480)
        self.setLayoutDirection(Qt.RightToLeft)
        self.parsed = None

        root = QVBoxLayout(self)
        hint = QLabel(
            'متن تم (JSON یا متغیرهای CSS مثل --color-background / --accent) را اینجا جای‌گذاری کنید '
            'یا یک فایل .json / .css انتخاب کنید:'
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('مثلاً: تم مینیمال آبی یا تم ارسالی')
        form.addRow('نام تم (در صورت نداشتن نام):', self.name_edit)
        root.addLayout(form)

        self.editor = QPlainTextEdit()
        self.editor.setLayoutDirection(Qt.LeftToRight)
        self.editor.setPlaceholderText('{\n  "name": "تم من",\n  "mode": "light",\n  "colors": {\n    "bg": "#F4F7FB",\n    "panel": "#FFFFFF",\n    "text": "#132238",\n    "accent": "#2563EB"\n  },\n  "tokens": { "radius": 16, "glass_alpha": 85 }\n}')
        root.addWidget(self.editor, 1)

        self.auto_apply = QCheckBox('بلافاصله روی همه بخش‌ها (به‌جز چت، دستیار و مالیات) اعمال شود')
        self.auto_apply.setChecked(True)
        root.addWidget(self.auto_apply)

        row = QHBoxLayout()
        pick_file = QPushButton('انتخاب فایل (.json / .css)')
        pick_file.clicked.connect(self._load_file)
        row.addWidget(pick_file)
        row.addStretch()
        ok_btn = QPushButton('خواندن و ذخیره تم')
        ok_btn.setObjectName('Primary')
        ok_btn.clicked.connect(self._accept_import)
        cancel_btn = QPushButton('انصراف')
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)
        root.addLayout(row)

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'انتخاب فایل تم', '', 'Theme Files (*.json *.css *.txt);;All Files (*)'
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.editor.setPlainText(f.read())
        except OSError as exc:
            QMessageBox.warning(self, 'خطا در خواندن فایل', str(exc))

    def _accept_import(self):
        try:
            fallback = self.name_edit.text().strip() or 'تم واردشده'
            self.parsed = parse_imported_theme(self.editor.toPlainText(), fallback_name=fallback)
        except ValueError as exc:
            QMessageBox.warning(self, 'تم معتبر نیست', str(exc))
            return
        self.accept()


class ThemeStudioPanel(QWidget):
    """Per-section theme assignment, custom palette builder, and safe JSON/CSS import/export."""

    def __init__(self, owner, initial_settings, parent=None):
        super().__init__(parent)
        self.owner = owner
        self.working = {
            'theme': initial_settings.get('theme', 'light'),
            'theme_preset': initial_settings.get('theme_preset', 'default'),
            'custom_themes': copy.deepcopy(initial_settings.get('custom_themes') or {}),
            'section_themes': dict(initial_settings.get('section_themes') or {}),
            'section_policies': dict(initial_settings.get('section_policies') or {}),
        }
        self._draft_colors = {}
        self._color_buttons = {}
        self._loading = False
        self._build_ui()
        self._reload_theme_combos()
        self._refresh_sections_list()
        self.sections_list.setCurrentRow(1)  # Default focus on Home

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        top_note = QLabel(
            'برای هر بخش برنامه به‌طور مستقل تم انتخاب یا وارد کنید. بخش‌های «چت»، «دستیار هوشمند» و «مالیات» '
            'به‌صورت پیش‌فرض محافظت شده‌اند تا ظاهر فعلی‌شان تغییر نکند (یا فقط رنگ تاکیدی آن‌ها عوض شود).'
        )
        top_note.setWordWrap(True)
        layout.addWidget(top_note)

        # Toolbar: Import / Export / Bulk Apply / Reset
        bar = QHBoxLayout()
        import_btn = QPushButton('ورود تم (JSON / CSS)')
        import_btn.setObjectName('Primary')
        import_btn.clicked.connect(self._open_import)
        export_btn = QPushButton('کپی JSON تم')
        export_btn.clicked.connect(self._export_current)
        bulk_btn = QPushButton('اعمال به همه (جز چت/دستیار/مالیات)')
        bulk_btn.clicked.connect(lambda: self._apply_bulk(include_protected=False))
        limited_btn = QPushButton('اعمال محدود به چت/دستیار/مالیات')
        limited_btn.clicked.connect(lambda: self._apply_bulk(include_protected=True))
        reset_all_btn = QPushButton('بازگردانی همه')
        reset_all_btn.clicked.connect(self._reset_all)
        for b in (import_btn, export_btn, bulk_btn, limited_btn, reset_all_btn):
            bar.addWidget(b)
        bar.addStretch()
        layout.addLayout(bar)

        split = QHBoxLayout()
        split.setSpacing(12)

        # Section list
        sec_box = QGroupBox('بخش‌های برنامه')
        sec_v = QVBoxLayout(sec_box)
        self.sections_list = QListWidget()
        self.sections_list.setMinimumWidth(250)
        self.sections_list.currentRowChanged.connect(self._on_section_changed)
        sec_v.addWidget(self.sections_list)
        split.addWidget(sec_box, 1)

        # Right pane: active section assignment + customizer
        right = QVBoxLayout()
        assign_box = QGroupBox('تنظیم تم بخش انتخاب‌شده')
        assign_form = QFormLayout(assign_box)

        self.section_label = QLabel('')
        self.section_label.setStyleSheet('font-weight:bold;')
        assign_form.addRow('بخش:', self.section_label)

        self.section_theme_combo = QComboBox()
        self.section_theme_combo.currentIndexChanged.connect(self._on_section_theme_picked)
        assign_form.addRow('تم اختصاصی این بخش:', self.section_theme_combo)

        self.policy_combo = QComboBox()
        self.policy_combo.addItem('قفل شده (حفظ کامل ظاهر فعلی این بخش)', 'locked')
        self.policy_combo.addItem('اعمال محدود (فقط رنگ اصلی/تاکیدی، بدون تغییر چیدمان)', 'limited')
        self.policy_combo.addItem('اعمال کامل تم روی این بخش', 'full')
        self.policy_combo.currentIndexChanged.connect(self._on_policy_changed)
        self.policy_row_label = QLabel('نحوه اعمال روی بخش محافظت‌شده:')
        assign_form.addRow(self.policy_row_label, self.policy_combo)

        right.addWidget(assign_box)

        # Custom Theme Designer / Editor
        editor_box = QGroupBox('ساخت یا ویرایش تم سفارشی')
        ed_v = QVBoxLayout(editor_box)

        meta_form = QFormLayout()
        self.theme_name_edit = QLineEdit()
        self.theme_name_edit.setPlaceholderText('نام تم سفارشی جدید...')
        meta_form.addRow('نام تم:', self.theme_name_edit)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem('روشن (Light)', 'light')
        self.mode_combo.addItem('تیره (Dark)', 'dark')
        self.mode_combo.currentIndexChanged.connect(self._update_preview)
        meta_form.addRow('حالت روشنایی:', self.mode_combo)

        tok_row = QHBoxLayout()
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(0, 28)
        self.radius_spin.setSuffix(' px')
        self.radius_spin.setValue(14)
        self.radius_spin.valueChanged.connect(self._update_preview)
        self.glass_spin = QSpinBox()
        self.glass_spin.setRange(20, 100)
        self.glass_spin.setSuffix(' %')
        self.glass_spin.setValue(84)
        self.glass_spin.valueChanged.connect(self._update_preview)
        tok_row.addWidget(QLabel('گردی گوشه‌ها:'))
        tok_row.addWidget(self.radius_spin)
        tok_row.addWidget(QLabel('شفافیت کارت:'))
        tok_row.addWidget(self.glass_spin)
        tok_row.addStretch()
        meta_form.addRow('جزئیات استایل:', tok_row)

        self.gradient_edit = QLineEdit()
        self.gradient_edit.setLayoutDirection(Qt.LeftToRight)
        self.gradient_edit.setPlaceholderText('اختیاری: linear-gradient(135deg, #EEF4FF 0%, #F9FAFF 100%)')
        meta_form.addRow('گرادیانت پس‌زمینه خانه:', self.gradient_edit)

        skin_row = QHBoxLayout()
        self.skin_combo = QComboBox()
        for sk, label in [
            ('classic', 'استاندارد ۳ ستونه'),
            ('command_bento', 'بنتو گرید (Bento Grid)'),
        ]:
            self.skin_combo.addItem(label, sk)
        self.blur_spin = QSpinBox()
        self.blur_spin.setRange(0, 32)
        self.blur_spin.setSuffix(' px')
        self.blur_spin.setValue(18)
        skin_row.addWidget(self.skin_combo, 1)
        skin_row.addWidget(QLabel('تاری شیشه:'))
        skin_row.addWidget(self.blur_spin)
        meta_form.addRow('چیدمان صفحه خانه:', skin_row)
        ed_v.addLayout(meta_form)

        grid = QGridLayout()
        for idx, (ckey, clabel) in enumerate(COLOR_LABELS):
            btn = QPushButton(clabel)
            btn.clicked.connect(lambda _=False, k=ckey: self._pick_color(k))
            self._color_buttons[ckey] = btn
            grid.addWidget(btn, idx // 2, idx % 2)
        ed_v.addLayout(grid)

        self.preview_frame = QFrame()
        self.preview_frame.setMinimumHeight(74)
        pv = QHBoxLayout(self.preview_frame)
        pv.setContentsMargins(12, 10, 12, 10)
        self.preview_card = QFrame()
        pc = QHBoxLayout(self.preview_card)
        pc.setContentsMargins(10, 8, 10, 8)
        self.preview_title = QLabel('پیش‌نمایش کارت و خوانایی متن')
        self.preview_badge = QPushButton('دکمه اصلی')
        self.preview_badge.setEnabled(False)
        pc.addWidget(self.preview_title, 1)
        pc.addWidget(self.preview_badge)
        pv.addWidget(self.preview_card)
        ed_v.addWidget(self.preview_frame)

        btn_row = QHBoxLayout()
        save_new_btn = QPushButton('ذخیره به‌عنوان تم جدید و اعمال به بخش')
        save_new_btn.setObjectName('Primary')
        save_new_btn.clicked.connect(lambda: self._save_custom_theme(as_new=True))
        update_btn = QPushButton('به‌روزرسانی تم سفارشی فعلی')
        update_btn.clicked.connect(lambda: self._save_custom_theme(as_new=False))
        delete_btn = QPushButton('حذف این تم سفارشی')
        delete_btn.clicked.connect(self._delete_custom_theme)
        btn_row.addWidget(save_new_btn)
        btn_row.addWidget(update_btn)
        btn_row.addWidget(delete_btn)
        ed_v.addLayout(btn_row)

        right.addWidget(editor_box, 1)
        split.addLayout(right, 2)
        layout.addLayout(split, 1)

    def _current_section_key(self):
        row = self.sections_list.currentRow()
        if 0 <= row < len(SECTIONS):
            return SECTIONS[row][0]
        return 'home'

    def _reload_theme_combos(self):
        self._loading = True
        prev = self.section_theme_combo.currentData()
        self.section_theme_combo.clear()
        self.section_theme_combo.addItem('پیش‌فرض (پیروی از تم عمومی برنامه)', '')
        for item in list_all_themes(self.working):
            suffix = ' [سفارشی]' if not item['builtin'] else ''
            self.section_theme_combo.addItem(f"{item['name']}{suffix}", item['id'])
        if prev:
            idx = self.section_theme_combo.findData(prev)
            if idx >= 0:
                self.section_theme_combo.setCurrentIndex(idx)
        self._loading = False

    def _refresh_sections_list(self):
        cur_row = max(0, self.sections_list.currentRow())
        self.sections_list.blockSignals(True)
        self.sections_list.clear()
        themes_by_id = {t['id']: t['name'] for t in list_all_themes(self.working)}
        for key, title, kind, protected in SECTIONS:
            assigned = self.working['section_themes'].get(key, '')
            policy = self.working['section_policies'].get(key, 'locked' if protected else 'full')
            kind_badge = 'React' if kind == 'react' else 'Python'
            if protected and policy == 'locked':
                status = 'قفل روی ظاهر فعلی'
            elif assigned:
                tname = themes_by_id.get(assigned, assigned)
                status = f'{tname} (محدود)' if (protected and policy == 'limited') else tname
            else:
                status = 'تم عمومی'
            item = QListWidgetItem(f'{title} [{kind_badge}] — {status}')
            item.setData(Qt.UserRole, key)
            self.sections_list.addItem(item)
        self.sections_list.setCurrentRow(min(cur_row, len(SECTIONS) - 1))
        self.sections_list.blockSignals(False)

    def _on_section_changed(self, _row):
        key = self._current_section_key()
        title, kind, protected = SECTION_MAP[key]
        self._loading = True
        self.section_label.setText(f'{title} ({ "React" if kind == "react" else "پایتون / Qt" })')
        assigned = self.working['section_themes'].get(key, '')
        idx = max(0, self.section_theme_combo.findData(assigned))
        self.section_theme_combo.setCurrentIndex(idx)

        self.policy_combo.setVisible(protected)
        self.policy_row_label.setVisible(protected)
        if protected:
            policy = self.working['section_policies'].get(key, 'locked')
            p_idx = max(0, self.policy_combo.findData(policy))
            self.policy_combo.setCurrentIndex(p_idx)
        self._loading = False
        self._load_editor_from_resolved(key)

    def _load_editor_from_resolved(self, section_key):
        resolved = resolve_section_theme(self.working, section_key)['theme']
        self._draft_colors = dict(resolved['colors'])
        self.theme_name_edit.setText(resolved.get('name', 'تم سفارشی'))
        m_idx = max(0, self.mode_combo.findData(resolved.get('mode', 'light')))
        self.mode_combo.setCurrentIndex(m_idx)
        tok = resolved.get('tokens') or {}
        self.radius_spin.setValue(int(tok.get('radius', 14)))
        self.glass_spin.setValue(int(tok.get('glass_alpha', 84)))
        self.blur_spin.setValue(int(tok.get('glass_blur', 16)))
        sk_idx = max(0, self.skin_combo.findData(tok.get('layout_skin', 'classic')))
        self.skin_combo.setCurrentIndex(sk_idx)
        self.gradient_edit.setText(str(tok.get('bg_gradient', '') or ''))
        for ckey, btn in self._color_buttons.items():
            hx = self._draft_colors.get(ckey, '#FFFFFF')
            btn.setStyleSheet(f'border-left: 16px solid {hx};')
        self._update_preview()

    def _update_preview(self):
        bg = self._draft_colors.get('bg', '#F3F6FA')
        panel = self._draft_colors.get('panel', '#FFFFFF')
        text = self._draft_colors.get('text', '#172B45')
        border = self._draft_colors.get('border', '#C5D1DF')
        accent = self._draft_colors.get('accent', '#066C64')
        rad = self.radius_spin.value()
        self.preview_frame.setStyleSheet(f'QFrame {{ background: {bg}; border: 1px solid {border}; border-radius: {rad}px; }}')
        self.preview_card.setStyleSheet(f'QFrame {{ background: {panel}; border: 1px solid {border}; border-radius: {max(4, rad - 2)}px; }}')
        self.preview_title.setStyleSheet(f'color: {text}; background: transparent; border: 0; font-weight: bold;')
        self.preview_badge.setStyleSheet(f'background: {accent}; color: #FFFFFF; border: 0; border-radius: {max(4, rad - 4)}px; padding: 5px 12px;')

    def _pick_color(self, ckey):
        picked = ColorWheelDialog.choose(self._draft_colors.get(ckey, '#2563EB'), self)
        if picked:
            self._draft_colors[ckey] = picked
            self._color_buttons[ckey].setStyleSheet(f'border-left: 16px solid {picked};')
            self._update_preview()

    def _on_section_theme_picked(self):
        if self._loading:
            return
        key = self._current_section_key()
        tid = self.section_theme_combo.currentData()
        if not tid:
            clear_section_theme(self.working, key)
        else:
            self.working['section_themes'][key] = tid
        self._refresh_sections_list()
        self._load_editor_from_resolved(key)

    def _on_policy_changed(self):
        if self._loading:
            return
        key = self._current_section_key()
        if key in PROTECTED_SECTIONS:
            self.working['section_policies'][key] = self.policy_combo.currentData()
            self._refresh_sections_list()
            self._load_editor_from_resolved(key)

    def _save_custom_theme(self, as_new=True):
        key = self._current_section_key()
        current_tid = self.working['section_themes'].get(key, '')
        is_existing_custom = (not as_new) and current_tid in self.working['custom_themes']
        tid = current_tid if is_existing_custom else f'custom_{uuid.uuid4().hex[:8]}'
        name = self.theme_name_edit.text().strip() or 'تم سفارشی جدید'
        if as_new and current_tid in self.working['custom_themes'] and name == self.working['custom_themes'][current_tid].get('name'):
            name = f'{name} (جدید)'

        norm = normalize_theme({
            'id': tid,
            'name': name,
            'mode': self.mode_combo.currentData(),
            'colors': dict(self._draft_colors),
            'tokens': {
                'radius': self.radius_spin.value(),
                'glass_alpha': self.glass_spin.value(),
                'glass_blur': self.blur_spin.value(),
                'layout_skin': self.skin_combo.currentData(),
                'bg_gradient': self.gradient_edit.text().strip(),
            },
        }, fallback_id=tid)
        self.working['custom_themes'][tid] = norm
        self.working['section_themes'][key] = tid
        self._reload_theme_combos()
        idx = self.section_theme_combo.findData(tid)
        if idx >= 0:
            self._loading = True
            self.section_theme_combo.setCurrentIndex(idx)
            self._loading = False
        self._refresh_sections_list()
        self._load_editor_from_resolved(key)

    def _delete_custom_theme(self):
        key = self._current_section_key()
        tid = self.working['section_themes'].get(key, '')
        if tid not in self.working['custom_themes']:
            QMessageBox.information(self, 'حذف تم', 'تم‌های پایه قابل حذف نیستند؛ فقط تم‌های سفارشی حذف می‌شوند.')
            return
        del self.working['custom_themes'][tid]
        for s_key, s_val in list(self.working['section_themes'].items()):
            if s_val == tid:
                del self.working['section_themes'][s_key]
        self._reload_theme_combos()
        self._refresh_sections_list()
        self._on_section_changed(self.sections_list.currentRow())

    def _apply_bulk(self, include_protected=False):
        tid = self.section_theme_combo.currentData()
        if not tid:
            QMessageBox.information(self, 'انتخاب تم', 'ابتدا یک تم یا تم سفارشی را در بخش انتخاب کنید (یا ذخیره کنید).')
            return
        apply_theme_to_sections(self.working, tid, include_protected=include_protected, protected_policy='limited')
        self._refresh_sections_list()
        self._on_section_changed(self.sections_list.currentRow())

    def _reset_all(self):
        self.working['section_themes'] = {}
        self.working['section_policies'] = {}
        self._reload_theme_combos()
        self._refresh_sections_list()
        self._on_section_changed(self.sections_list.currentRow())

    def _open_import(self):
        dlg = ThemeImportDialog(self)
        if dlg.exec() != QDialog.Accepted or not dlg.parsed:
            return
        imported_themes = dlg.parsed['themes']
        first_id = ''
        for t in imported_themes:
            tid = t['id']
            if tid in {'default', 'emerald_ivory', 'glass_mist', 'violet_modular'}:
                tid = f'custom_{uuid.uuid4().hex[:8]}'
                t['id'] = tid
            self.working['custom_themes'][tid] = t
            if not first_id:
                first_id = tid
        for sec, tref in (dlg.parsed.get('sections') or {}).items():
            self.working['section_themes'][sec] = tref
        if dlg.auto_apply.isChecked() and first_id and not dlg.parsed.get('sections'):
            apply_theme_to_sections(self.working, first_id, include_protected=False)
        elif first_id and not dlg.parsed.get('sections'):
            self.working['section_themes'][self._current_section_key()] = first_id
        self._reload_theme_combos()
        self._refresh_sections_list()
        self._on_section_changed(self.sections_list.currentRow())
        QMessageBox.information(self, 'تم وارد شد', f'{len(imported_themes)} تم با موفقیت خوانده و ذخیره شد. برای اعمال نهایی روی دکمه تایید/ذخیره تنظیمات کلیک کنید.')

    def _export_current(self):
        key = self._current_section_key()
        resolved = resolve_section_theme(self.working, key)['theme']
        text = json.dumps(resolved, ensure_ascii=False, indent=2)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, 'کپی تم', f'کد JSON تم بخش «{SECTION_MAP[key][0]}» در حافظه (Clipboard) کپی شد.')

    def commit_into(self, result_settings):
        """Write studio state back into settings dictionary returned by SettingsDialog."""
        result_settings['custom_themes'] = copy.deepcopy(self.working['custom_themes'])
        result_settings['section_themes'] = dict(self.working['section_themes'])
        result_settings['section_policies'] = dict(self.working['section_policies'])
