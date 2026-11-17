"""Native 60fps Nimbus Waterline navigation, Surface Tension theme toggle, hover submenus, and sidebar glass glow."""
import math
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPointF, QRectF, QSize, QTimer, QVariantAnimation, Qt
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QMenu, QToolButton, QWidget


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, float(t)))
    return QColor(
        round(a.red() * (1 - t) + b.red() * t),
        round(a.green() * (1 - t) + b.green() * t),
        round(a.blue() * (1 - t) + b.blue() * t),
        round(a.alpha() * (1 - t) + b.alpha() * t),
    )


def prepare_glass_menu(menu):
    """Ensure QMenu popups are frameless without black DWM boxes while keeping an opaque styled backdrop."""
    if menu is None:
        return
    flags = menu.windowFlags() | Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
    menu.setWindowFlags(flags)
    menu.setAttribute(Qt.WA_TranslucentBackground, True)
    menu.setAttribute(Qt.WA_StyledBackground, True)


class HoverSubmenuController(QObject):
    """Open multi-item nav submenus only on click or after holding hover ~1s, never accidentally on pass-through."""

    def __init__(self, parent=None, buttons=()):
        super().__init__(parent)
        self._buttons = []
        self._active_btn = None
        self._pending_btn = None

        self._open_timer = QTimer(self)
        self._open_timer.setSingleShot(True)
        self._open_timer.setInterval(1000)
        self._open_timer.timeout.connect(self._open_pending)

        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(190)
        self._close_timer.timeout.connect(self._close_if_left)

        for btn in buttons:
            self.register(btn)

    def register(self, btn):
        if btn is None or btn in self._buttons:
            return
        self._buttons.append(btn)
        btn.installEventFilter(self)
        m = btn.menu()
        if m is not None:
            prepare_glass_menu(m)
            m.installEventFilter(self)

    def _popup_pos(self, btn, menu):
        hint = menu.sizeHint()
        # Align RTL drop right under the button (inside screen bounds)
        global_br = btn.mapToGlobal(QPoint(btn.width(), btn.height() + 4))
        x = global_br.x() - hint.width()
        y = global_br.y()
        screen = btn.screen().availableGeometry() if btn.screen() else None
        if screen is not None:
            x = max(screen.left() + 6, min(x, screen.right() - hint.width() - 6))
            if y + hint.height() > screen.bottom() - 6:
                y = btn.mapToGlobal(QPoint(0, 0)).y() - hint.height() - 4
        return QPoint(x, y)

    def _open_pending(self):
        btn = self._pending_btn
        self._pending_btn = None
        if btn is None or not btn.isVisible() or not btn.isEnabled():
            return
        menu = btn.menu()
        if menu is None:
            return
        if not btn.underMouse() and not btn.rect().contains(btn.mapFromGlobal(QCursor.pos())):
            return
        if self._active_btn is not None and self._active_btn is not btn:
            prev_menu = self._active_btn.menu()
            if prev_menu is not None and prev_menu.isVisible():
                prev_menu.hide()
        self._active_btn = btn
        prepare_glass_menu(menu)
        if not menu.isVisible():
            menu.popup(self._popup_pos(btn, menu))

    def _close_if_left(self):
        btn = self._active_btn
        if btn is None:
            return
        menu = btn.menu()
        pos = QCursor.pos()
        over_btn = btn.isVisible() and btn.rect().contains(btn.mapFromGlobal(pos))
        over_menu = menu is not None and menu.isVisible() and menu.rect().contains(menu.mapFromGlobal(pos))
        if over_btn or over_menu:
            return
        if menu is not None and menu.isVisible():
            menu.hide()
        self._active_btn = None

    def eventFilter(self, obj, event):
        kind = event.type()
        if obj in self._buttons:
            menu = obj.menu()
            if menu is not None and kind == QEvent.Enter and obj.isVisible():
                self._close_timer.stop()
                if self._active_btn is obj and menu.isVisible():
                    return False
                self._pending_btn = obj
                self._open_timer.start()
            elif kind == QEvent.MouseButtonPress:
                self._open_timer.stop()
                self._pending_btn = None
            elif menu is not None and kind == QEvent.Leave:
                self._open_timer.stop()
                self._close_timer.start()
        elif isinstance(obj, QMenu):
            if kind == QEvent.Enter:
                self._close_timer.stop()
            elif kind == QEvent.Leave:
                self._close_timer.start()
            elif kind == QEvent.Hide:
                if self._active_btn is not None and self._active_btn.menu() is obj:
                    self._active_btn = None
        return False


class LiquidThemeToggle(QToolButton):
    """Compact Surface-Tension liquid drop Light/Dark switch for the main app bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('LiquidThemeToggle')
        self.setProperty('flowCustomLiquid', True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(62, 30)
        self._dark = False
        self._pos = 0.0  # 0.0 = Light, 1.0 = Dark
        self._hover = 0.0
        self._palette = {}

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on_step)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(140)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_step)

    def sizeHint(self):
        return QSize(62, 30)

    def _on_step(self, value):
        self._pos = float(value)
        self.update()

    def _on_hover_step(self, value):
        self._hover = float(value)
        self.update()

    def set_theme_state(self, dark, palette=None, animate=True):
        target = 1.0 if dark else 0.0
        changed = bool(dark) != self._dark
        self._dark = bool(dark)
        if palette:
            self._palette = dict(palette)
        if not animate or not changed:
            self._anim.stop()
            self._pos = target
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        radius = r.height() / 2.0
        t = max(0.0, min(1.0, self._pos))
        stretch = math.sin(math.pi * t)

        track = QPainterPath()
        track.addRoundedRect(r, radius, radius)

        bg = QLinearGradient(r.topLeft(), r.bottomLeft())
        if t < 0.5:
            bg.setColorAt(0.0, QColor(248, 252, 255, 225))
            bg.setColorAt(1.0, QColor(220, 236, 248, 215))
        else:
            bg.setColorAt(0.0, QColor(15, 34, 54, 232))
            bg.setColorAt(1.0, QColor(9, 24, 40, 242))
        p.save()
        p.setClipPath(track)
        p.fillRect(r, bg)

        if t > 0.02:
            fill_w = max(r.height(), (r.width() - r.height()) * t + r.height())
            fill_rect = QRectF(r.left(), r.top(), fill_w, r.height())
            water = QLinearGradient(fill_rect.left(), fill_rect.top(), fill_rect.right(), fill_rect.bottom())
            accent = QColor(self._palette.get('accent', '#0284C7'))
            water.setColorAt(0.0, QColor(56, 189, 248, round(155 * t)))
            water.setColorAt(1.0, _mix(accent, QColor(20, 184, 166), 0.4))
            water.setColorAt(1.0, QColor(water.stops()[-1][1].red(), water.stops()[-1][1].green(), water.stops()[-1][1].blue(), round(190 * t)))
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, radius, radius)
            p.fillPath(fill_path, water)

        if stretch > 0.22:
            trail_x = r.center().x() + (r.left() + radius - r.center().x()) * 0.35
            trail_r = 2.6 * stretch
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(125, 211, 252, round(170 * stretch)))
            p.drawEllipse(QPointF(trail_x, r.center().y()), trail_r, trail_r * 0.85)
        p.restore()

        rim_alpha = round(145 + 75 * self._hover)
        rim_color = QColor(125, 211, 252, rim_alpha) if self._dark else QColor(15, 23, 42, 48 + round(36 * self._hover))
        p.setPen(QPen(rim_color, 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(track)

        knob_d = r.height() - 5.0
        knob_w = knob_d + 6.5 * max(0.0, stretch)
        travel = r.width() - 5.0 - knob_d
        knob_cx = r.left() + 2.5 + knob_d / 2.0 + travel * t
        knob_rect = QRectF(knob_cx - knob_w / 2.0, r.top() + 2.5, knob_w, knob_d)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(6, 24, 44, 55 if self._dark else 36))
        p.drawRoundedRect(knob_rect.translated(0, 1.2), knob_d / 2.0, knob_d / 2.0)

        drop_grad = QRadialGradient(knob_rect.center() - QPointF(knob_d * 0.16, knob_d * 0.18), knob_w * 0.72)
        if t < 0.5:
            drop_grad.setColorAt(0.0, QColor(255, 255, 255, 252))
            drop_grad.setColorAt(0.75, QColor(224, 244, 255, 245))
            drop_grad.setColorAt(1.0, QColor(168, 222, 248, 235))
        else:
            drop_grad.setColorAt(0.0, QColor(165, 232, 255, 240))
            drop_grad.setColorAt(0.7, QColor(56, 189, 248, 230))
            drop_grad.setColorAt(1.0, QColor(14, 116, 144, 245))
        p.setBrush(drop_grad)
        p.drawRoundedRect(knob_rect, knob_d / 2.0, knob_d / 2.0)

        p.setBrush(QColor(255, 255, 255, 130 if t < 0.5 else 90))
        p.drawEllipse(QPointF(knob_rect.center().x() - knob_w * 0.14, knob_rect.top() + 5.0), knob_w * 0.22, 2.2)

        center = knob_rect.center()
        if t < 0.5:
            sun = QColor(232, 154, 18, round(255 * (1.0 - t * 1.4)))
            p.setPen(QPen(sun, 1.6, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(center, 3.6, 3.6)
            for idx in range(8):
                ang = idx * math.pi / 4.0
                p.drawLine(
                    QPointF(center.x() + math.cos(ang) * 5.2, center.y() + math.sin(ang) * 5.2),
                    QPointF(center.x() + math.cos(ang) * 6.8, center.y() + math.sin(ang) * 6.8),
                )
        else:
            moon = QColor(240, 249, 255, round(255 * ((t - 0.3) / 0.7)))
            p.setPen(Qt.NoPen)
            p.setBrush(moon)
            outer_moon = QPainterPath()
            outer_moon.addEllipse(center, 5.2, 5.2)
            cut = QPainterPath()
            cut.addEllipse(center + QPointF(2.5, -1.8), 4.3, 4.3)
            p.drawPath(outer_moon.subtracted(cut))
        p.end()


def _theme_glass_spec(preset_key, colors, dark):
    """Per-theme frosted glass recipe for main navbar pill and active water drop."""
    accent = QColor(colors.get('accent', '#0284C7'))
    if preset_key == 'violet_modular':
        return {
            'radius_ratio': 0.28,
            'shell_top': QColor(22, 29, 54, 212) if dark else QColor(250, 251, 255, 224),
            'shell_bot': QColor(14, 19, 38, 226) if dark else QColor(232, 237, 250, 205),
            'rim': QColor(141, 166, 255, 85) if dark else QColor(255, 255, 255, 240),
            'drop_a': QColor('#8DA6FF') if dark else QColor('#3958DB'),
            'drop_b': QColor('#4F6EF2') if dark else QColor('#243FAF'),
            'hover': QColor(141, 166, 255, 58) if dark else QColor(43, 74, 203, 36),
            'hover_rim': QColor(141, 166, 255, 115) if dark else QColor(43, 74, 203, 95),
        }
    if preset_key == 'glass_mist':
        return {
            'radius_ratio': 0.5,
            'shell_top': QColor(16, 36, 56, 205) if dark else QColor(248, 252, 255, 218),
            'shell_bot': QColor(10, 24, 40, 218) if dark else QColor(222, 240, 252, 195),
            'rim': QColor(125, 211, 252, 90) if dark else QColor(255, 255, 255, 245),
            'drop_a': QColor('#7DD3FC') if dark else QColor('#0EA5E9'),
            'drop_b': QColor('#38BDF8') if dark else QColor('#0277BD'),
            'hover': QColor(103, 196, 250, 52) if dark else QColor(2, 119, 189, 32),
            'hover_rim': QColor(125, 211, 252, 125) if dark else QColor(2, 119, 189, 95),
        }
    if preset_key == 'emerald_ivory':
        return {
            'radius_ratio': 0.34,
            'shell_top': QColor(12, 34, 26, 220) if dark else QColor(251, 249, 242, 225),
            'shell_bot': QColor(8, 25, 19, 232) if dark else QColor(232, 242, 234, 205),
            'rim': QColor(107, 224, 172, 80) if dark else QColor(15, 91, 66, 65),
            'drop_a': QColor('#6BE0AC') if dark else QColor('#157A58'),
            'drop_b': QColor('#2FA877') if dark else QColor('#0C4D37'),
            'hover': QColor(107, 224, 172, 50) if dark else QColor(15, 91, 66, 34),
            'hover_rim': QColor(107, 224, 172, 115) if dark else QColor(15, 91, 66, 90),
        }
    if preset_key == 'bento_grid':
        return {
            'radius_ratio': 0.5,
            'shell_top': QColor(15, 39, 54, 208) if dark else QColor(246, 253, 255, 216),
            'shell_bot': QColor(10, 29, 42, 220) if dark else QColor(225, 244, 247, 198),
            'rim': QColor(92, 224, 200, 88) if dark else QColor(255, 255, 255, 240),
            'drop_a': QColor('#5CE0C8') if dark else QColor('#0EA5E9'),
            'drop_b': QColor('#0EA5E9') if dark else QColor('#0C8574'),
            'hover': QColor(92, 224, 200, 48) if dark else QColor(12, 133, 116, 34),
            'hover_rim': QColor(92, 224, 200, 120) if dark else QColor(14, 165, 233, 95),
        }
    return {
        'radius_ratio': 0.42,
        'shell_top': QColor(20, 38, 56, 215) if dark else QColor(244, 250, 254, 220),
        'shell_bot': QColor(12, 25, 40, 228) if dark else QColor(224, 239, 248, 200),
        'rim': QColor(125, 211, 252, 80) if dark else QColor(255, 255, 255, 230),
        'drop_a': accent.lighter(118),
        'drop_b': accent,
        'hover': QColor(accent.red(), accent.green(), accent.blue(), 52 if dark else 34),
        'hover_rim': QColor(accent.red(), accent.green(), accent.blue(), 125 if dark else 95),
    }


class LiquidNavBackdrop(QWidget):
    """Draws the theme-customized frosted glass pill, smooth gliding hover bubble, active water drop & click ripple."""

    def __init__(self, host, controller):
        super().__init__(host)
        self.controller = controller
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.lower()

    def paintEvent(self, event):
        ctrl = self.controller
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2.0, 2.0, -2.0, -2.0)
        if r.width() <= 8 or r.height() <= 8:
            p.end()
            return

        spec = _theme_glass_spec(ctrl.preset_key, ctrl.colors, ctrl.dark)
        accent = QColor(ctrl.colors.get('accent', '#0284C7'))
        pill_rad = r.height() * spec['radius_ratio']

        pill = QPainterPath()
        pill.addRoundedRect(r, pill_rad, pill_rad)
        shell_grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        shell_grad.setColorAt(0.0, spec['shell_top'])
        shell_grad.setColorAt(1.0, spec['shell_bot'])
        p.fillPath(pill, shell_grad)
        p.setPen(QPen(spec['rim'], 1.15))
        p.setBrush(Qt.NoBrush)
        p.drawPath(pill)

        # Animated gliding hover glass bubble beneath hovered inactive item
        hr_cur = ctrl.hover_rect_anim
        if hr_cur is not None and not hr_cur.isEmpty() and ctrl.hover_alpha > 0.01:
            hr = hr_cur.adjusted(1.5, 2.5, -1.5, -2.5)
            h_rad = hr.height() * spec['radius_ratio']
            hcolor = QColor(spec['hover'])
            hcolor.setAlpha(round(hcolor.alpha() * ctrl.hover_alpha))
            hrim = QColor(spec['hover_rim'])
            hrim.setAlpha(round(hrim.alpha() * ctrl.hover_alpha))
            p.setPen(QPen(hrim, 1.0))
            p.setBrush(hcolor)
            p.drawRoundedRect(hr, h_rad, h_rad)

        # Stretching animated active water drop
        ar = ctrl.current_rect
        if ar is not None and not ar.isEmpty():
            dr = ar.adjusted(1.0, 2.5, -1.0, -2.5)
            d_rad = dr.height() * spec['radius_ratio']
            if 0.12 < ctrl.jump_progress < 0.88 and ctrl.trail_point is not None:
                splash_a = math.sin(math.pi * ctrl.jump_progress)
                trail = QColor(spec['drop_a'])
                trail.setAlpha(round(135 * splash_a))
                p.setPen(Qt.NoPen)
                p.setBrush(trail)
                rad = 3.5 + 3.0 * splash_a
                p.drawEllipse(ctrl.trail_point, rad * 1.4, rad * 0.85)

            dg = QLinearGradient(dr.topLeft(), dr.bottomRight())
            top_c = QColor(spec['drop_a'])
            top_c.setAlpha(228 if ctrl.dark else 238)
            bot_c = QColor(spec['drop_b'])
            bot_c.setAlpha(242 if ctrl.dark else 248)
            dg.setColorAt(0.0, top_c)
            dg.setColorAt(1.0, bot_c)

            dpath = QPainterPath()
            dpath.addRoundedRect(dr, d_rad, d_rad)
            p.fillPath(dpath, dg)

            glint = QRectF(dr.left() + 8.0, dr.top() + 2.0, max(6.0, dr.width() - 16.0), 3.0)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 95 if ctrl.dark else 135))
            p.drawRoundedRect(glint, 1.5, 1.5)

            p.setPen(QPen(QColor(255, 255, 255, 90 if ctrl.dark else 150), 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(dpath)

        # Expanding circular ripple wave on tap
        if 0.0 < ctrl.ripple_progress < 1.0 and ctrl.ripple_center is not None:
            rp = ctrl.ripple_progress
            ring_r = 8.0 + 36.0 * rp
            ring = QColor(accent)
            ring.setAlpha(round(120 * (1.0 - rp)))
            p.save()
            p.setClipPath(pill)
            p.setPen(QPen(ring, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(ctrl.ripple_center, ring_r, ring_r * 0.65)
            p.restore()
        p.end()


class LiquidNavEffect(QObject):
    """Synchronize main top navigation buttons with theme-matched animated frosted-glass drop & glide hover."""

    def __init__(self, host, buttons):
        super().__init__(host)
        self.host = host
        self.buttons = buttons
        self.colors = {}
        self.dark = False
        self.preset_key = 'default'
        self.current_rect = QRectF()
        self.start_rect = QRectF()
        self.target_rect = QRectF()

        self.hover_rect_anim = QRectF()
        self._hover_start = QRectF()
        self._hover_target = QRectF()
        self.hover_alpha = 0.0

        self.trail_point = None
        self.ripple_center = None
        self.jump_progress = 1.0
        self.ripple_progress = 1.0

        self.backdrop = LiquidNavBackdrop(host, self)
        self.backdrop.setGeometry(host.rect())
        self.backdrop.show()
        self.backdrop.lower()

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(270)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._step_jump)

        self._hover_glide = QVariantAnimation(self)
        self._hover_glide.setDuration(155)
        self._hover_glide.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_glide.valueChanged.connect(self._step_hover)

        self._hover_fade = QVariantAnimation(self)
        self._hover_fade.setDuration(130)
        self._hover_fade.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_fade.valueChanged.connect(self._step_hover_alpha)

        self._ripple = QVariantAnimation(self)
        self._ripple.setDuration(360)
        self._ripple.setEasingCurve(QEasingCurve.OutCubic)
        self._ripple.valueChanged.connect(self._step_ripple)

        host.installEventFilter(self)
        for btn in buttons.values():
            btn.installEventFilter(self)

    def _step_hover(self, value):
        p = float(value)
        sx, sy, sw, sh = self._hover_start.x(), self._hover_start.y(), self._hover_start.width(), self._hover_start.height()
        tx, ty, tw, th = self._hover_target.x(), self._hover_target.y(), self._hover_target.width(), self._hover_target.height()
        self.hover_rect_anim = QRectF(
            sx + (tx - sx) * p,
            sy + (ty - sy) * p,
            sw + (tw - sw) * p,
            sh + (th - sh) * p,
        )
        self.backdrop.update()

    def _step_hover_alpha(self, value):
        self.hover_alpha = float(value)
        self.backdrop.update()

    def eventFilter(self, obj, event):
        kind = event.type()
        if obj is self.host and kind in (QEvent.Resize, QEvent.LayoutRequest):
            self.backdrop.setGeometry(self.host.rect())
            self.backdrop.lower()
            self.sync_active(animate=False)
        elif obj in self.buttons.values():
            if kind == QEvent.Enter and obj.isVisible():
                dest = QRectF(obj.geometry())
                if self.hover_rect_anim.isEmpty() or self.hover_alpha < 0.05:
                    self._hover_start = dest
                    self._hover_target = dest
                    self.hover_rect_anim = dest
                else:
                    self._hover_start = QRectF(self.hover_rect_anim)
                    self._hover_target = dest
                    self._hover_glide.stop()
                    self._hover_glide.setStartValue(0.0)
                    self._hover_glide.setEndValue(1.0)
                    self._hover_glide.start()
                self._hover_fade.stop()
                self._hover_fade.setStartValue(self.hover_alpha)
                self._hover_fade.setEndValue(1.0)
                self._hover_fade.start()
            elif kind == QEvent.Leave:
                self._hover_fade.stop()
                self._hover_fade.setStartValue(self.hover_alpha)
                self._hover_fade.setEndValue(0.0)
                self._hover_fade.start()
            elif kind == QEvent.MouseButtonPress and obj.isVisible():
                self.ripple_center = QPointF(obj.geometry().center())
                self._ripple.stop()
                self._ripple.setStartValue(0.0)
                self._ripple.setEndValue(1.0)
                self._ripple.start()
        return False

    def set_theme(self, colors, dark, preset_key='default'):
        self.colors = dict(colors or {})
        self.dark = bool(dark)
        self.preset_key = preset_key or 'default'
        self.backdrop.update()

    def sync_active(self, animate=True):
        active_btn = next((b for b in self.buttons.values() if b.property('active') and b.isVisible()), None)
        if active_btn is None:
            self.target_rect = QRectF()
            self.current_rect = QRectF()
            self.backdrop.update()
            return
        dest = QRectF(active_btn.geometry())
        if dest.isEmpty():
            return
        if not animate or self.current_rect.isEmpty():
            self._anim.stop()
            self.start_rect = dest
            self.target_rect = dest
            self.current_rect = dest
            self.jump_progress = 1.0
            self.trail_point = None
            self.backdrop.update()
            return
        if abs(dest.x() - self.target_rect.x()) < 1.0 and abs(dest.width() - self.target_rect.width()) < 1.0:
            return
        self.start_rect = QRectF(self.current_rect)
        self.target_rect = dest
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _step_jump(self, value):
        p = float(value)
        self.jump_progress = p
        sx, sw = self.start_rect.x(), self.start_rect.width()
        tx, tw = self.target_rect.x(), self.target_rect.width()
        lead = min(1.0, p * 1.18)
        lag = max(0.0, (p - 0.14) / 0.86)
        going_right = tx >= sx
        if going_right:
            left = sx + (tx - sx) * lag
            right = (sx + sw) + ((tx + tw) - (sx + sw)) * lead
        else:
            left = sx + (tx - sx) * lead
            right = (sx + sw) + ((tx + tw) - (sx + sw)) * lag
        self.current_rect = QRectF(left, self.target_rect.y(), max(24.0, right - left), self.target_rect.height())
        self.trail_point = QPointF(
            self.start_rect.center().x() + (self.target_rect.center().x() - self.start_rect.center().x()) * p * 0.72,
            self.target_rect.center().y(),
        )
        self.backdrop.update()

    def _step_ripple(self, value):
        self.ripple_progress = float(value)
        self.backdrop.update()


class LiquidSidebarBackdrop(QWidget):
    """Paints a gliding vertical frosted-glass highlight & active pill inside sidebar navigation."""

    def __init__(self, host, controller):
        super().__init__(host)
        self.controller = controller
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.lower()

    def paintEvent(self, event):
        ctrl = self.controller
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        accent = QColor(ctrl.colors.get('accent', '#088C7E'))
        is_emerald = ctrl.preset_key == 'emerald_ivory'

        if not ctrl.hover_rect.isEmpty() and ctrl.hover_alpha > 0.01:
            hr = ctrl.hover_rect.adjusted(4, 2, -4, -2)
            fill = QColor('#6BE0AC' if ctrl.dark else '#348E6D') if is_emerald else QColor(accent)
            fill.setAlpha(round(56 * ctrl.hover_alpha))
            rim = QColor(255, 255, 255, round(85 * ctrl.hover_alpha))
            p.setPen(QPen(rim, 1.0))
            p.setBrush(fill)
            p.drawRoundedRect(hr, 10, 10)

        if not ctrl.active_rect.isEmpty():
            ar = ctrl.active_rect.adjusted(4, 2, -4, -2)
            grad = QLinearGradient(ar.topRight(), ar.bottomLeft())
            if is_emerald:
                grad.setColorAt(0.0, QColor(43, 96, 76, 225))
                grad.setColorAt(1.0, QColor(26, 72, 56, 235))
            else:
                grad.setColorAt(0.0, QColor(accent).lighter(115))
                grad.setColorAt(1.0, QColor(accent))
            p.setPen(QPen(QColor(255, 255, 255, 75), 1.0))
            p.setBrush(grad)
            p.drawRoundedRect(ar, 10, 10)
        p.end()


class LiquidSidebarEffect(QObject):
    """Animated gliding hover glass effect for the right sidebar navigation (`default` and `emerald_ivory`)."""

    def __init__(self, host, buttons):
        super().__init__(host)
        self.host = host
        self.buttons = buttons
        self.colors = {}
        self.dark = False
        self.preset_key = 'default'
        self.hover_rect = QRectF()
        self.active_rect = QRectF()
        self._hover_start = QRectF()
        self._hover_target = QRectF()
        self.hover_alpha = 0.0

        self.backdrop = LiquidSidebarBackdrop(host, self)
        self.backdrop.setGeometry(host.rect())
        self.backdrop.show()
        self.backdrop.lower()

        self._glide = QVariantAnimation(self)
        self._glide.setDuration(150)
        self._glide.setEasingCurve(QEasingCurve.OutCubic)
        self._glide.valueChanged.connect(self._step_glide)

        self._fade = QVariantAnimation(self)
        self._fade.setDuration(120)
        self._fade.valueChanged.connect(self._step_fade)

        host.installEventFilter(self)
        for btn in buttons.values():
            btn.installEventFilter(self)

    def _step_glide(self, v):
        p = float(v)
        self.hover_rect = QRectF(
            self._hover_start.x() + (self._hover_target.x() - self._hover_start.x()) * p,
            self._hover_start.y() + (self._hover_target.y() - self._hover_start.y()) * p,
            self._hover_start.width() + (self._hover_target.width() - self._hover_start.width()) * p,
            self._hover_start.height() + (self._hover_target.height() - self._hover_start.height()) * p,
        )
        self.backdrop.update()

    def _step_fade(self, v):
        self.hover_alpha = float(v)
        self.backdrop.update()

    def eventFilter(self, obj, event):
        kind = event.type()
        if obj is self.host and kind in (QEvent.Resize, QEvent.LayoutRequest):
            self.backdrop.setGeometry(self.host.rect())
            self.backdrop.lower()
            self.sync_active()
        elif obj in self.buttons.values():
            if kind == QEvent.Enter and obj.isVisible():
                dest = QRectF(obj.geometry())
                if self.hover_rect.isEmpty() or self.hover_alpha < 0.05:
                    self._hover_start = dest
                    self._hover_target = dest
                    self.hover_rect = dest
                else:
                    self._hover_start = QRectF(self.hover_rect)
                    self._hover_target = dest
                    self._glide.stop()
                    self._glide.setStartValue(0.0)
                    self._glide.setEndValue(1.0)
                    self._glide.start()
                self._fade.stop()
                self._fade.setStartValue(self.hover_alpha)
                self._fade.setEndValue(1.0)
                self._fade.start()
            elif kind == QEvent.Leave:
                self._fade.stop()
                self._fade.setStartValue(self.hover_alpha)
                self._fade.setEndValue(0.0)
                self._fade.start()
        return False

    def set_theme(self, colors, dark, preset_key='default'):
        self.colors = dict(colors or {})
        self.dark = bool(dark)
        self.preset_key = preset_key or 'default'
        self.sync_active()
        self.backdrop.update()

    def sync_active(self):
        active_btn = next((b for b in self.buttons.values() if b.property('active') and b.isVisible()), None)
        self.active_rect = QRectF(active_btn.geometry()) if active_btn is not None else QRectF()
        self.backdrop.update()
