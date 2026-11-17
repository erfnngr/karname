import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_v6_ui as fixture
from appearance import apply_appearance

fixture.V6UiTests.setUpClass()
t=fixture.V6UiTests();t.setUp()
try:
    for key in ('emerald_ivory','glass_mist','violet_modular'):
        for mode in ('light','dark'):
            t.win.resize(1366,768);t.win.data['settings'].update(theme_preset=key,theme=mode);apply_appearance(t.win.data['settings']);t.win.tabs.setCurrentWidget(t.win.home);t.win.refresh();t.win.sidebar.apply();t.app.processEvents()
            t.win.grab().save(str(Path(__file__).resolve().parents[1]/('qa-v86-'+key+'-'+mode+'.png')))
finally:t.tearDown()
