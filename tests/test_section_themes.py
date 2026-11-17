"""Tests for per-section custom themes, safe JSON/CSS import, and protected React section policies."""
import json
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QWidget
from appearance import apply_section_appearances
from section_themes import (
    PROTECTED_SECTIONS,
    apply_theme_to_sections,
    clear_section_theme,
    parse_imported_theme,
    resolve_section_theme,
    section_appearance_payload,
)
from theme_studio_ui import ThemeStudioPanel


class SectionThemeUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_parse_json_theme_and_sanitizes_unsafe_values(self):
        raw = json.dumps({
            'name': 'تم اقیانوسی',
            'mode': 'dark',
            'colors': {
                'bg': '#0b1623',
                'panel': '#122436',
                'text': '#f0f7ff',
                'accent': '#38bdf8',
                'nav': '#08111c',
            },
            'tokens': {
                'radius': 18,
                'glass_alpha': 76,
                'bg_gradient': 'url(https://evil.example/x.png)',
                'vars': {
                    '--card-glow': '#38BDF8',
                    'bad-key': 'expression(1)',
                },
            },
        })
        parsed = parse_imported_theme(raw)
        self.assertEqual(len(parsed['themes']), 1)
        t = parsed['themes'][0]
        self.assertEqual(t['name'], 'تم اقیانوسی')
        self.assertEqual(t['mode'], 'dark')
        self.assertEqual(t['colors']['accent'], '#38BDF8')
        self.assertEqual(t['tokens']['radius'], 18)
        self.assertEqual(t['tokens']['glass_alpha'], 76)
        self.assertEqual(t['tokens']['bg_gradient'], '')
        self.assertEqual(t['tokens']['vars'], {'--card-glow': '#38BDF8'})

    def test_parse_css_variables_block(self):
        css = """
        :root {
            --color-background: #faf5ff;
            --color-card: #ffffff;
            --color-foreground: #2e1065;
            --color-primary: #7c3aed;
            --radius: 20px;
            --home-bg: linear-gradient(135deg, #f3e8ff 0%, #ede9fe 100%);
        }
        """
        parsed = parse_imported_theme(css, fallback_name='بنفش CSS')
        t = parsed['themes'][0]
        self.assertEqual(t['name'], 'بنفش CSS')
        self.assertEqual(t['mode'], 'light')
        self.assertEqual(t['colors']['bg'], '#FAF5FF')
        self.assertEqual(t['colors']['accent'], '#7C3AED')
        self.assertEqual(t['tokens']['radius'], 20)
        self.assertIn('linear-gradient', t['tokens']['bg_gradient'])

    def test_bulk_apply_skips_protected_sections_and_limited_only_updates_accent(self):
        settings = {
            'theme': 'light',
            'theme_preset': 'default',
            'custom_themes': {
                'dark_indigo': {
                    'id': 'dark_indigo',
                    'name': 'نیلی تیره',
                    'mode': 'dark',
                    'colors': {
                        'bg': '#0D1321',
                        'panel': '#1D2D44',
                        'text': '#F0EBD8',
                        'accent': '#0284C7',
                    },
                    'tokens': {'radius': 20, 'glass_alpha': 80},
                }
            },
        }
        apply_theme_to_sections(settings, 'dark_indigo', include_protected=False)

        home_res = resolve_section_theme(settings, 'home')
        self.assertTrue(home_res['overridden'])
        self.assertEqual(home_res['theme']['mode'], 'dark')
        self.assertEqual(home_res['theme']['colors']['bg'], '#0D1321')

        # Protected sections stay untouched when include_protected=False
        for sec in PROTECTED_SECTIONS:
            res = resolve_section_theme(settings, sec)
            self.assertFalse(res['overridden'])
            self.assertEqual(res['policy'], 'locked')

        # Limited mode on tax preserves light base panel/bg and updates only accent
        settings['section_themes']['tax'] = 'dark_indigo'
        settings['section_policies']['tax'] = 'limited'
        tax_payload = section_appearance_payload(settings, 'tax')
        self.assertFalse(tax_payload['dark'])
        self.assertNotEqual(tax_payload['colors']['bg'], '#0D1321')
        self.assertEqual(tax_payload['colors']['accent'], '#0284C7')

        clear_section_theme(settings, 'home')
        self.assertFalse(resolve_section_theme(settings, 'home')['overridden'])

    def test_studio_panel_and_python_section_qss_application(self):
        class DummyOwner:
            def __init__(self):
                self.data = {
                    'settings': {
                        'theme': 'light',
                        'theme_preset': 'default',
                        'font_family': 'Vazirmatn',
                        'font_size': 13,
                        'density': 'comfortable',
                    }
                }
                self.workspace = QWidget()
                self.clients = QWidget()

        owner = DummyOwner()
        panel = ThemeStudioPanel(owner, owner.data['settings'])
        panel.working['custom_themes']['ocean'] = {
            'id': 'ocean',
            'name': 'اقیانوس',
            'mode': 'light',
            'colors': {'bg': '#EEF6FF', 'panel': '#FFFFFF', 'text': '#0F172A', 'accent': '#0284C7'},
            'tokens': {'radius': 16},
        }
        apply_theme_to_sections(panel.working, 'ocean', include_protected=False)
        committed = dict(owner.data['settings'])
        panel.commit_into(committed)
        owner.data['settings'] = committed

        apply_section_appearances(owner)
        self.assertIn('#EEF6FF', owner.workspace.styleSheet())
        self.assertIn('border-radius:16px', owner.workspace.styleSheet())

        clear_section_theme(owner.data['settings'], 'workspace')
        apply_section_appearances(owner)
        self.assertEqual(owner.workspace.styleSheet(), '')
        owner.workspace.deleteLater()
        owner.clients.deleteLater()
        panel.deleteLater()


if __name__ == '__main__':
    unittest.main(verbosity=2)
