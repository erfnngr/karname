"""Expose only the active appearance palette to embedded views (supporting per-section themes)."""
import json
from PySide6.QtCore import QObject, QTimer, Signal, Slot


class ReactAppearanceBridge(QObject):
    changed = Signal(str)

    def __init__(self, owner, parent=None, section='default', host=None):
        super().__init__(parent)
        self.owner = owner
        self.section = section
        self.host = host
        self.last = ''
        self.timer = QTimer(self)
        self.timer.setInterval(1200)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        from react_design_host import should_poll_section
        host = self.host
        if host is None:
            p = self.parent()
            host = p.view() if hasattr(p, 'view') else p
        if not should_poll_section(self.owner, host):
            return
        self.publish()

    @Slot(result=str)
    def current(self):
        from section_themes import section_appearance_payload
        settings = self.owner.data.get('settings', {})
        return json.dumps(section_appearance_payload(settings, self.section), ensure_ascii=False)

    def publish(self):
        value = self.current()
        if value != self.last:
            self.last = value
            try:
                from PySide6.QtGui import QColor
                parsed = json.loads(value)
                bg = (parsed.get('colors') or {}).get('bg')
                p = self.parent()
                if bg and hasattr(p, 'setBackgroundColor'):
                    p.setBackgroundColor(QColor(bg))
            except Exception:
                pass
            self.changed.emit(value)
