import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_v6_ui as fixture
from appearance import apply_appearance
from storage import new_event,jformat,today_j

fixture.V6UiTests.setUpClass()
t=fixture.V6UiTests();t.setUp()
try:
    for title,state in [('بررسی فاکتور نمونه','draft'),('آماده‌سازی گزارش نمونه','in_progress'),('ارسال مدارک نمونه','review')]:
        e=new_event('شخصی',title,jformat(today_j()));e['progress_status']=state;t.win.events.append(e)
    t.win.workspace.snapshot={};t.win.workspace.include_local()
    for mode in ('light','dark'):
        t.win.resize(1366,768);t.win.data['settings'].update(theme_preset='glass_mist',theme=mode);apply_appearance(t.win.data['settings']);t.win.tabs.setCurrentWidget(t.win.workspace)
        for index,name in [(0,'list'),(1,'board')]:
            t.win.workspace.pages.setCurrentIndex(index);t.win.workspace.render();t.win.sidebar.apply();t.app.processEvents()
            t.win.grab().save(str(Path(__file__).resolve().parents[1]/('qa-v87-'+name+'-'+mode+'.png')))
finally:t.tearDown()
