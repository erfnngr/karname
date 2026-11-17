"""Lightweight vector Birthday Celebration overlay for the birthday person."""
import math
import random
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QPushButton, QWidget


class BirthdayCelebrationOverlay(QWidget):
    """Non-blocking animated birthday celebration overlay: balloons, side confetti, 5s greeting, and clickable candle cake."""

    closed = Signal()

    BALLOON_COLORS = (
        '#0EA5E9', '#10B981', '#F59E0B', '#EC4899', '#38BDF8', '#34D399', '#FB7185'
    )
    CONFETTI_COLORS = (
        '#38BDF8', '#10B981', '#FBBF24', '#F472B6', '#60A5FA', '#2DD4BF', '#F97316'
    )

    def __init__(self, parent, person_name, settings=None, duration_banner_ms=5000):
        super().__init__(parent)
        self.person_name = str(person_name or 'کاربر عزیز').strip()
        self.settings = dict(settings or {})
        self.banner_duration_ms = max(1200, int(duration_banner_ms))
        self.setObjectName('BirthdayCelebrationOverlay')
        self.setLayoutDirection(Qt.RightToLeft)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self._elapsed_ms = 0
        self.phase = 'greeting'  # 'greeting' -> 'cake' -> 'blowing' -> 'done'
        self.flame_lit = True
        self.cake_visible = False
        self._blow_ms = 0
        self._message_opacity = 0.0
        self._cake_opacity = 0.0
        self._cake_progress = 0.0
        self._cake_scale = 0.28
        self._overlay_opacity = 1.0
        self._finish_wait_ms = 0

        self.dismiss_button = QPushButton('✕ بستن', self)
        self.dismiss_button.setObjectName('BirthdayDismissButton')
        self.dismiss_button.setAccessibleName('بستن جشن تولد')
        self.dismiss_button.setCursor(Qt.PointingHandCursor)
        self.dismiss_button.clicked.connect(self.dismiss)

        self.candle_button = QPushButton('', self)
        self.candle_button.setObjectName('BirthdayCandleButton')
        self.candle_button.setAccessibleName('فوت کردن شمع کیک تولد')
        self.candle_button.setToolTip('روی شمع کلیک کنید تا خاموش شود')
        self.candle_button.setCursor(Qt.PointingHandCursor)
        self.candle_button.setStyleSheet('QPushButton#BirthdayCandleButton {background: transparent; border: 0;}')
        self.candle_button.clicked.connect(self.blow_candle)
        self.candle_button.hide()

        self._apply_theme_styles()
        self._seed_particles()

        if parent is not None:
            self.setGeometry(parent.rect())
            parent.installEventFilter(self)

        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._step)
        self._timer.start()
        self.show()
        self.raise_()

    def _apply_theme_styles(self):
        from appearance import palette_for, accent_foreground
        c = palette_for(self.settings)
        dark = self.settings.get('theme') == 'dark'
        fg = accent_foreground(c['accent'])
        bg_btn = 'rgba(15, 29, 44, 215)' if dark else 'rgba(255, 255, 255, 232)'
        self.dismiss_button.setStyleSheet(
            f'QPushButton#BirthdayDismissButton {{background:{bg_btn};color:{c["text"]};border:1px solid {c["border"]};border-radius:14px;padding:6px 14px;font-weight:bold;}}'
            f'QPushButton#BirthdayDismissButton:hover {{background:{c["accent"]};color:{fg};border-color:{c["accent"]};}}'
        )

    def _seed_particles(self):
        rng = random.Random(2026)
        w = max(800, self.width())
        h = max(520, self.height())
        self._balloons = []
        # Launch larger, higher-volume balloons from bottom-left, bottom-center, and bottom-right
        for i in range(34):
            lane = i % 3
            if lane == 0:
                x_pos = rng.uniform(0.03, 0.26) * w
            elif lane == 1:
                x_pos = rng.uniform(0.74, 0.97) * w
            else:
                x_pos = rng.uniform(0.22, 0.78) * w
            rx = rng.uniform(28, 45)
            ry = rx * rng.uniform(1.24, 1.36)
            self._balloons.append({
                'x': x_pos,
                'y': h + 70 + rng.uniform(0, h * 0.58),
                'vy': rng.uniform(125, 205),
                'sway_amp': rng.uniform(10, 26),
                'sway_freq': rng.uniform(1.2, 2.5),
                'phase': rng.uniform(0, math.tau),
                'rx': rx,
                'ry': ry,
                'color': self.BALLOON_COLORS[i % len(self.BALLOON_COLORS)],
            })

        self._confetti = []
        for i in range(72):
            origin = i % 3
            if origin == 0:
                start_x = -8.0
                start_y = h * rng.uniform(0.45, 0.92)
                vx = rng.uniform(240, 520)
                vy = rng.uniform(-480, -210)
            elif origin == 1:
                start_x = float(w + 8)
                start_y = h * rng.uniform(0.45, 0.92)
                vx = -rng.uniform(240, 520)
                vy = rng.uniform(-480, -210)
            else:
                start_x = w * rng.uniform(0.12, 0.88)
                start_y = float(h + 8)
                vx = rng.uniform(-160, 160)
                vy = rng.uniform(-640, -340)
            self._confetti.append({
                'x': start_x,
                'y': start_y,
                'vx': vx,
                'vy': vy,
                'w': rng.uniform(8, 15),
                'h': rng.uniform(5, 9),
                'angle': rng.uniform(0, 360),
                'spin': rng.uniform(-240, 240),
                'color': self.CONFETTI_COLORS[i % len(self.CONFETTI_COLORS)],
            })

        self._smoke = []

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.parentWidget() and event.type() == QEvent.Resize:
            self.setGeometry(obj.rect())
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.dismiss_button.adjustSize()
        self.dismiss_button.move(18, 18)
        self._layout_candle_hitbox()

    def _cake_center(self):
        return QPointF(self.width() / 2.0, self.height() * 0.56)

    def _layout_candle_hitbox(self):
        c = self._cake_center()
        # Generous accessible hitbox aligned with the larger zoomed-in cake candle
        self.candle_button.setGeometry(int(c.x() - 62), int(c.y() - 205), 124, 150)

    def blow_candle(self):
        """Play blowing animation, extinguish the candle flame, then close smoothly."""
        if self.phase not in ('cake', 'greeting'):
            return
        self.phase = 'blowing'
        self.flame_lit = False
        self.candle_button.setEnabled(False)
        self._blow_ms = 0
        c = self._cake_center()
        self._smoke = [
            {'x': c.x() + i * 2.0 - 3.0, 'y': c.y() - 102.0 - i * 4.0, 'r': 4.0 + i, 'a': 185}
            for i in range(6)
        ]
        self.update()

    def dismiss(self):
        """Dismiss the celebration overlay immediately."""
        if self.phase == 'done':
            return
        self.phase = 'done'
        self._timer.stop()
        parent = self.parentWidget()
        if parent is not None:
            try:
                parent.removeEventFilter(self)
            except Exception:
                pass
        self.hide()
        self.closed.emit()
        self.deleteLater()

    def _step(self):
        dt = 0.02
        self._elapsed_ms += 20
        h = max(400, self.height())

        # Animate rising balloons out of view
        for b in self._balloons:
            b['y'] -= b['vy'] * dt

        # Animate side confetti gravity & drag
        for cf in self._confetti:
            cf['x'] += cf['vx'] * dt
            cf['y'] += cf['vy'] * dt
            cf['vy'] += 420.0 * dt
            cf['vx'] *= 0.992
            cf['angle'] = (cf['angle'] + cf['spin'] * dt) % 360.0

        if self.phase == 'greeting':
            if self._elapsed_ms < 360:
                self._message_opacity = min(1.0, self._elapsed_ms / 360.0)
            elif self._elapsed_ms < self.banner_duration_ms - 650:
                self._message_opacity = 1.0
            else:
                rem = max(0.0, (self.banner_duration_ms - self._elapsed_ms) / 650.0)
                self._message_opacity = max(0.0, min(1.0, rem))
            if self._elapsed_ms >= self.banner_duration_ms:
                self.phase = 'cake'
                self.cake_visible = True
                self._message_opacity = 0.0
                self._cake_opacity = 0.0
                self._cake_progress = 0.0
                self._cake_scale = 0.28
                self._layout_candle_hitbox()
                self.candle_button.show()
                self.candle_button.raise_()
                self.dismiss_button.raise_()

        elif self.phase == 'cake':
            self._cake_opacity = min(1.0, self._cake_opacity + dt * 2.4)
            self._cake_progress = min(1.0, self._cake_progress + dt * 1.45)
            ease = 1.0 - (1.0 - self._cake_progress) ** 3
            self._cake_scale = 0.28 + 0.72 * ease
            self._layout_candle_hitbox()

        elif self.phase == 'blowing':
            self._blow_ms += 20
            for puff in self._smoke:
                puff['y'] -= 42.0 * dt
                puff['x'] += math.sin(self._blow_ms * 0.015 + puff['r']) * 18.0 * dt
                puff['r'] += 6.5 * dt
                puff['a'] = max(0.0, puff['a'] - 170.0 * dt)
            if self._blow_ms >= 950:
                self._overlay_opacity = max(0.0, 1.0 - (self._blow_ms - 950) / 450.0)
            if self._blow_ms >= 1400:
                self.dismiss()
                return

        # Keep CPU minimal once particles settle and cake sits idle (only flame flickers gently)
        self.update()

    def paintEvent(self, event):
        from appearance import palette_for
        c = palette_for(self.settings)
        dark = self.settings.get('theme') == 'dark'

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self._overlay_opacity)

        # Gentle dimming veil so text and cake remain readable in every theme without blocking visuals
        p.fillRect(self.rect(), QColor(6, 14, 24, 95 if dark else 58))

        # Draw confetti behind greeting / cake
        for cf in self._confetti:
            if cf['y'] > self.height() + 30:
                continue
            p.save()
            p.translate(cf['x'], cf['y'])
            p.rotate(cf['angle'])
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(cf['color']))
            p.drawRoundedRect(QRectF(-cf['w'] / 2, -cf['h'] / 2, cf['w'], cf['h']), 1.5, 1.5)
            p.restore()

        # Draw rising balloons with fuller volume, knot, string & glossy highlight
        t_sec = self._elapsed_ms / 1000.0
        for b in self._balloons:
            if b['y'] < -150:
                continue
            bx = b['x'] + math.sin(t_sec * b['sway_freq'] + b['phase']) * b['sway_amp']
            by = b['y']
            rx, ry = b['rx'], b['ry']

            p.setPen(QPen(QColor(225, 236, 248, 175), 1.4))
            string_path = QPainterPath()
            string_path.moveTo(bx, by + ry + 3)
            string_path.cubicTo(bx - 8, by + ry + 22, bx + 8, by + ry + 42, bx, by + ry + 64)
            p.drawPath(string_path)

            col = QColor(b['color'])
            grad = QRadialGradient(bx - rx * 0.32, by - ry * 0.36, max(rx, ry) * 1.55)
            grad.setColorAt(0.0, col.lighter(155))
            grad.setColorAt(0.55, col)
            grad.setColorAt(1.0, col.darker(135))
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            p.drawEllipse(QPointF(bx, by), rx, ry)

            knot = QPainterPath()
            knot.moveTo(bx - rx * 0.14, by + ry - 1)
            knot.lineTo(bx + rx * 0.14, by + ry - 1)
            knot.lineTo(bx, by + ry + 7)
            knot.closeSubpath()
            p.setBrush(col.darker(120))
            p.drawPath(knot)

            p.setBrush(QColor(255, 255, 255, 130))
            p.drawEllipse(QPointF(bx - rx * 0.33, by - ry * 0.38), rx * 0.24, ry * 0.17)

        # Greeting Banner (first ~5 seconds)
        if self._message_opacity > 0.01:
            p.save()
            p.setOpacity(self._overlay_opacity * self._message_opacity)
            cw = min(560.0, max(320.0, self.width() * 0.56))
            ch = 148.0
            card = QRectF((self.width() - cw) / 2.0, (self.height() - ch) / 2.0, cw, ch)
            path = QPainterPath()
            path.addRoundedRect(card, 24, 24)
            bg_grad = QLinearGradient(card.topLeft(), card.bottomRight())
            if dark:
                bg_grad.setColorAt(0.0, QColor(14, 34, 52, 236))
                bg_grad.setColorAt(1.0, QColor(11, 44, 50, 232))
            else:
                bg_grad.setColorAt(0.0, QColor(255, 255, 255, 244))
                bg_grad.setColorAt(1.0, QColor(235, 248, 253, 242))
            p.fillPath(path, bg_grad)
            p.setPen(QPen(QColor(c['accent']), 2.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

            title_font = self.font()
            title_font.setBold(True)
            title_font.setPixelSize(max(20, min(28, int(cw * 0.055))))
            p.setFont(title_font)
            p.setPen(QColor(c['text']))
            p.drawText(
                card.adjusted(22, 20, -22, -48),
                Qt.AlignCenter | Qt.TextWordWrap,
                f'تولدت مبارک، {self.person_name}!',
            )

            sub_font = self.font()
            sub_font.setBold(False)
            sub_font.setPixelSize(13)
            p.setFont(sub_font)
            p.setPen(QColor(c['muted']))
            p.drawText(
                card.adjusted(22, 88, -22, -16),
                Qt.AlignCenter,
                'برایتان سالی سرشار از آرامش و موفقیت آرزو می‌کنیم',
            )
            p.restore()

        # Birthday Cake with Zoom-In Approach + Clickable Lit Candle (Phase 2 & Blowing)
        if self.phase in ('cake', 'blowing') and self._cake_opacity > 0.01:
            p.save()
            p.setOpacity(self._overlay_opacity * self._cake_opacity)
            center = self._cake_center()
            scale_total = 1.42 * max(0.28, getattr(self, '_cake_scale', 1.0))
            p.translate(center)
            p.scale(scale_total, scale_total)
            p.translate(-center)
            panel = QRectF(center.x() - 180, center.y() - 175, 360, 295)
            panel_path = QPainterPath()
            panel_path.addRoundedRect(panel, 26, 26)
            p.fillPath(
                panel_path,
                QColor(15, 33, 50, 238) if dark else QColor(255, 255, 255, 245),
            )
            p.setPen(QPen(QColor(c['accent']), 1.8))
            p.drawPath(panel_path)

            # Cake plate
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c['border']))
            p.drawRoundedRect(QRectF(center.x() - 108, center.y() + 44, 216, 12), 6, 6)

            # Bottom tier
            tier1 = QRectF(center.x() - 88, center.y() - 6, 176, 52)
            p.setBrush(QColor('#38BDF8' if dark else '#7DD3FC'))
            p.drawRoundedRect(tier1, 14, 14)

            # Top tier
            tier2 = QRectF(center.x() - 62, center.y() - 50, 124, 46)
            p.setBrush(QColor('#10B981' if dark else '#6EE7B7'))
            p.drawRoundedRect(tier2, 12, 12)

            # Cream frosting scallops on top tier
            p.setBrush(QColor('#F8FAFC'))
            for i in range(6):
                fx = tier2.left() + 10 + i * 20.5
                p.drawEllipse(QPointF(fx, tier2.top() + 8), 11, 8)
            p.drawRoundedRect(QRectF(tier2.left(), tier2.top(), tier2.width(), 10), 6, 6)

            # Candle body
            candle = QRectF(center.x() - 7, center.y() - 94, 14, 45)
            p.setBrush(QColor('#FEF3C7'))
            p.drawRoundedRect(candle, 4, 4)
            p.setBrush(QColor('#F59E0B'))
            p.drawRect(QRectF(candle.left(), candle.top() + 12, candle.width(), 5))
            p.drawRect(QRectF(candle.left(), candle.top() + 26, candle.width(), 5))

            # Wick
            p.setPen(QPen(QColor('#475569'), 2.0))
            p.drawLine(QPointF(center.x(), candle.top()), QPointF(center.x(), candle.top() - 7))

            # Lit flickering flame OR wind + smoke animation
            if self.flame_lit:
                sway = math.sin(t_sec * 11.0) * 1.6
                halo = QRadialGradient(center.x() + sway, candle.top() - 18, 28)
                halo.setColorAt(0.0, QColor(251, 191, 36, 145))
                halo.setColorAt(1.0, QColor(251, 191, 36, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(halo)
                p.drawEllipse(QPointF(center.x() + sway, candle.top() - 18), 26, 26)

                flame = QPainterPath()
                tip = QPointF(center.x() + sway, candle.top() - 32)
                flame.moveTo(tip)
                flame.cubicTo(center.x() + 11, candle.top() - 16, center.x() + 8, candle.top() - 5, center.x(), candle.top() - 5)
                flame.cubicTo(center.x() - 8, candle.top() - 5, center.x() - 11, candle.top() - 16, tip.x(), tip.y())
                p.setBrush(QColor('#F59E0B'))
                p.drawPath(flame)

                inner = QPainterPath()
                inner.moveTo(center.x() + sway * 0.5, candle.top() - 24)
                inner.cubicTo(center.x() + 5, candle.top() - 14, center.x() + 4, candle.top() - 7, center.x(), candle.top() - 7)
                inner.cubicTo(center.x() - 4, candle.top() - 7, center.x() - 5, candle.top() - 14, center.x() + sway * 0.5, candle.top() - 24)
                p.setBrush(QColor('#FEF08A'))
                p.drawPath(inner)
            else:
                # Blowing breeze lines + rising soft smoke puffs
                if self._blow_ms < 500:
                    breeze = 1.0 - self._blow_ms / 500.0
                    p.setPen(QPen(QColor(125, 211, 252, round(190 * breeze)), 2.2, Qt.SolidLine, Qt.RoundCap))
                    shift = (self._blow_ms / 500.0) * 34.0
                    p.drawLine(QPointF(center.x() - 58 + shift, candle.top() - 18), QPointF(center.x() - 20 + shift, candle.top() - 18))
                    p.drawLine(QPointF(center.x() - 48 + shift, candle.top() - 10), QPointF(center.x() - 12 + shift, candle.top() - 10))
                p.setPen(Qt.NoPen)
                for puff in self._smoke:
                    if puff['a'] <= 1:
                        continue
                    p.setBrush(QColor(203, 213, 225, round(puff['a'])))
                    p.drawEllipse(QPointF(puff['x'], puff['y']), puff['r'], puff['r'] * 0.85)

            prompt_font = self.font()
            prompt_font.setBold(True)
            prompt_font.setPixelSize(14)
            p.setFont(prompt_font)
            p.setPen(QColor(c['text']))
            caption = (
                'روی شمع کلیک کنید تا فوت شود'
                if self.flame_lit
                else f'آرزوت برآورده بشه، {self.person_name}'
            )
            p.drawText(QRectF(panel.left() + 16, center.y() + 68, panel.width() - 32, 38), Qt.AlignCenter, caption)
            p.restore()

        p.end()
