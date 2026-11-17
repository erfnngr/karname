import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_v6_ui as fixture
from appearance import apply_appearance
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

fixture.V6UiTests.setUpClass();t=fixture.V6UiTests();t.setUp()
try:
    t.win.resize(1366,768);t.win.data['settings'].update(theme_preset='emerald_ivory',theme='light');apply_appearance(t.win.data['settings']);t.win.refresh();t.win.sidebar.apply();t.app.processEvents()
    button=t.win.nav_buttons['clients'];QTest.mouseMove(button,button.rect().center());t.app.processEvents()
    t.win.grab().save(str(Path(__file__).resolve().parents[1]/'qa-emerald-hover.png'))
    menu=t.win.calendar_menu;menu.popup(button.mapToGlobal(button.rect().center()));t.app.processEvents();a=menu.actions()[0];QTest.mouseMove(menu,menu.actionGeometry(a).center());t.app.processEvents()
    menu.grab().save(str(Path(__file__).resolve().parents[1]/'qa-emerald-submenu.png'));menu.close()
finally:t.tearDown()
