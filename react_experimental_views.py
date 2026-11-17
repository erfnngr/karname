"""Mount the redesigned React views directly inside Chat, Assistant, and Tax tabs."""
import os
from PySide6.QtWidgets import QApplication, QStackedLayout, QVBoxLayout, QWidget
from react_design_host import preview_asset_root


def _transfer_layout_to_host(panel):
    old = panel.layout()
    native_host = QWidget(panel)
    host_layout = QVBoxLayout(native_host)
    if old is not None:
        host_layout.setContentsMargins(old.contentsMargins())
        host_layout.setSpacing(old.spacing())
        while old.count():
            item = old.takeAt(0)
            if item.widget() is not None:
                host_layout.addWidget(item.widget())
            elif item.layout() is not None:
                host_layout.addLayout(item.layout())
        QWidget().setLayout(old)
    stack = QStackedLayout(panel)
    stack.setContentsMargins(0, 0, 0, 0)
    stack.addWidget(native_host)
    stack.setCurrentWidget(native_host)
    panel._react_stack = stack
    panel._react_native_host = native_host
    return stack


def _create_widget(kind, root, panel):
    if kind == 'home':
        from react_home_widget import ReactHomeWidget
        return ReactHomeWidget(root, panel, panel)
    if kind == 'calendar':
        from react_calendar_widget import ReactCalendarWidget
        return ReactCalendarWidget(root, panel, getattr(panel, '_karname_owner', panel.window()), panel)
    if kind == 'chat':
        from react_chat_widget import ReactChatWidget
        return ReactChatWidget(root, panel, panel)
    if kind == 'assistant':
        from react_assistant_widget import ReactAssistantWidget
        return ReactAssistantWidget(root, panel, panel)
    from react_tax_widget import ReactTaxWidget
    return ReactTaxWidget(root, panel, panel)


def install_react_views(owner, assets=None):
    """Install React views inside owner.home, owner.calendar_page, owner.chat, owner.ai, and owner.tax_center."""
    if os.getenv('KARNAME_DISABLE_REACT_VIEWS') == '1':
        return False
    if os.getenv('QT_QPA_PLATFORM') == 'offscreen' and os.getenv('KARNAME_FORCE_REACT_VIEWS') != '1':
        return False
    root = preview_asset_root(assets)
    if root is None:
        return False

    if getattr(owner, 'calendar_page', None) is not None:
        owner.calendar_page._karname_owner = owner

    targets = (
        ('home', getattr(owner, 'home', None), 'home.html'),
        ('calendar', getattr(owner, 'calendar_page', None), 'calendar.html'),
        ('chat', getattr(owner, 'chat', None), 'live.html'),
        ('assistant', getattr(owner, 'ai', None), 'assistant.html'),
        ('tax', getattr(owner, 'tax_center', None), 'tax.html'),
    )
    panels = {}
    for kind, panel, entry in targets:
        if panel is None or not (root / entry).is_file():
            continue
        if getattr(panel, '_react_stack', None) is None:
            _transfer_layout_to_host(panel)
        panel._react_kind = kind
        panel.react_view = getattr(panel, 'react_view', None)
        panels[panel] = kind
    if not panels:
        return False

    def ensure_react_view(panel):
        kind = panels.get(panel)
        if not kind:
            return None
        stack = getattr(panel, '_react_stack', None)
        if stack is None:
            return None
        if panel.react_view is not None:
            stack.setCurrentWidget(panel.react_view)
            return panel.react_view
        try:
            view = _create_widget(kind, root, panel)
        except Exception as exc:
            panel._react_error = str(exc)
            stack.setCurrentWidget(panel._react_native_host)
            return None
        stack.addWidget(view)
        stack.setCurrentWidget(view)
        panel.react_view = view
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(view.bridge.close)
        return view

    owner.ensure_react_view = ensure_react_view
    owner.tabs.currentChanged.connect(lambda _=None: ensure_react_view(owner.tabs.currentWidget()))
    ensure_react_view(owner.tabs.currentWidget())
    return True


def install_experimental_views(owner, assets):
    """Backward-compatible entry point forwarding to primary React views."""
    install_react_views(owner, assets)


def install_experimental_navigation(owner, assets):
    """Backward-compatible entry point forwarding to primary React views."""
    install_react_views(owner, assets)
