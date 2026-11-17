"""Qt implementation of the supplied two-arrow flow button."""
from PySide6.QtCore import QObject,QEvent,QVariantAnimation,QEasingCurve,Qt,QRectF,QPointF,QTimer
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QFont,QFontMetrics,QPixmap,QIcon,QLinearGradient
from PySide6.QtWidgets import QApplication,QPushButton,QToolButton,QWidget,QDialogButtonBox,QMessageBox,QToolTip,QLabel,QCheckBox,QComboBox

FLOW_DURATION_MS=160

def primary(button):
    if not isinstance(button,QPushButton) or not button.text().strip() or button.menu():return False
    if button.objectName() in ('Primary','LoginSubmit') or button.property('flowPrimary') is True:return True
    parent=button.parentWidget()
    if isinstance(parent,QDialogButtonBox):
        ancestor=parent.parentWidget()
        while ancestor:
            if isinstance(ancestor,QMessageBox):return False
            ancestor=ancestor.parentWidget()
        return parent.buttonRole(button) in (QDialogButtonBox.AcceptRole,QDialogButtonBox.YesRole,QDialogButtonBox.ApplyRole)
    return False

def eligible(button):
    return isinstance(button,(QPushButton,QToolButton))

def has_readable_label(button):
    text=button.text().replace('&','').strip()
    if not any(ch.isalpha() for ch in text):return False
    return not (isinstance(button,QToolButton) and button.toolButtonStyle()==Qt.ToolButtonIconOnly and not button.icon().isNull())

def emoji_only(button):
    text=button.text().strip()
    return bool(text) and any(ord(ch)>=0x1f000 for ch in text) and not any(ch.isalnum() for ch in text)

def label_width(button):
    """Measure the same bold font that the flow painter actually renders."""
    font=QFont(button.font());font.setBold(True)
    return QFontMetrics(font).horizontalAdvance(button.text().replace('&',''))

class EmojiMotion(QObject):
    """A subtle gallery-inspired pulse that never changes the control bounds."""
    def __init__(self,button):
        super().__init__(button);self.button=button;self.base=QFont(button.font());self.anim=QVariantAnimation(self);self.anim.setDuration(FLOW_DURATION_MS);self.anim.setEasingCurve(QEasingCurve.OutCubic);self.anim.valueChanged.connect(self.step)
    def animate(self,hover):
        value=self.anim.currentValue()
        if hover and (value is None or float(value)<.01):self.base=QFont(self.button.font())
        self.anim.stop();self.anim.setStartValue(float(value or 0));self.anim.setEndValue(1.0 if hover else 0.0);self.anim.start()
    def step(self,value):
        font=QFont(self.base);point=font.pointSizeF()
        if point>0:font.setPointSizeF(point+min(1.0,float(value)))
        elif font.pixelSize()>0:font.setPixelSize(font.pixelSize()+round(float(value)))
        self.button.setFont(font)

def bezier(progress,x1,y1,x2,y2):
    """Evaluate CSS cubic-bezier by solving the x component."""
    lo,hi=0.0,1.0
    for _ in range(16):
        t=(lo+hi)/2;u=1-t;x=3*u*u*t*x1+3*u*t*t*x2+t*t*t
        if x<progress:lo=t
        else:hi=t
    t=(lo+hi)/2;u=1-t
    return 3*u*u*t*y1+3*u*t*t*y2+t*t*t

def inverse_is_clearer(ink,foreground,base,alpha):
    from appearance import contrast
    a=max(0,min(1,float(alpha)))
    mixed=QColor(round(base.red()*(1-a)+ink.red()*a),round(base.green()*(1-a)+ink.green()*a),round(base.blue()*(1-a)+ink.blue()*a))
    return contrast(foreground.name(),mixed.name())>contrast(ink.name(),mixed.name())

class ShinyOverlay(QWidget):
    """A short, bounded hover animation; idle navigation performs no repaint loop."""
    def __init__(self,button):
        super().__init__(button);self.button=button;self.hover=False;self.setAttribute(Qt.WA_TransparentForMouseEvents);self.setAttribute(Qt.WA_TranslucentBackground);self.setFocusPolicy(Qt.NoFocus);self.setGeometry(button.rect())
        self.base_icon_size=button.iconSize();self.animation=QVariantAnimation(self);self.animation.setDuration(FLOW_DURATION_MS);self.animation.setEasingCurve(QEasingCurve.OutCubic);self.animation.valueChanged.connect(self.step)
    def animate(self,hover):
        self.hover=hover;current=self.animation.currentValue()
        if current is None:current=0.0
        if hover and float(current)<.01:self.base_icon_size=self.button.iconSize()
        self.animation.stop();self.animation.setStartValue(float(current));self.animation.setEndValue(1.0 if hover else 0.0);self.animation.start()
    def step(self,value):
        # Keep the native icon and text layout stationary throughout the shimmer.
        self.update()
    def paintEvent(self,event):
        if not self.button.isEnabled():return
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);r=QRectF(self.rect()).adjusted(1,1,-1,-1)
        if self.button.isDown():r.adjust(r.width()*.025,r.height()*.025,-r.width()*.025,-r.height()*.025)
        shape=QPainterPath();shape.addRoundedRect(r,min(8,r.height()/2),min(8,r.height()/2))
        phase=float(self.animation.currentValue() or 0);center=.25+.5*phase;g=QLinearGradient(r.left(),r.top(),r.right(),r.bottom());colors=QApplication.instance().property('karname_flow_colors') or {};accent=QColor(colors.get('accent','#2675B8'));neutral=QColor(accent);neutral.setAlpha(12);bright=QColor(accent);bright.setAlpha(round(55+125*phase));g.setColorAt(0,neutral);g.setColorAt(max(0,min(1,center-.10)),neutral);g.setColorAt(max(0,min(1,center)),bright);g.setColorAt(max(0,min(1,center+.10)),neutral);g.setColorAt(1,neutral)
        pen=QPen();pen.setBrush(g);pen.setWidthF(1.35 if self.hover else .9);p.setPen(pen);p.setBrush(Qt.NoBrush);p.drawPath(shape)
        if self.hover and not self.button.icon().isNull():
            # Keep the moving highlight outside the glyphs and labels.
            highlight=QColor(accent);highlight.setAlpha(150);pen=QPen(highlight,1.4);pen.setCapStyle(Qt.RoundCap);p.setPen(pen)
            if not has_readable_label(self.button):
                radius=max(2,min(r.width(),r.height())/2-3);p.drawArc(QRectF(r.center().x()-radius,r.center().y()-radius,2*radius,2*radius),int(phase*360*16),70*16)
            else:
                travel=max(0,r.width()-16);x=r.left()+8+travel*phase;p.drawLine(QPointF(x,r.top()+1),QPointF(min(r.right()-3,x+5),r.top()+1))
        p.end()

class FlowOverlay(QWidget):
    """Animate compact, icon and menu buttons without changing their geometry."""
    def __init__(self,button):
        super().__init__(button);self.button=button;self.setAttribute(Qt.WA_TransparentForMouseEvents);self.setAttribute(Qt.WA_TranslucentBackground);self.setFocusPolicy(Qt.NoFocus)
        self.animation=QVariantAnimation(self);self.animation.setDuration(FLOW_DURATION_MS);self.animation.setEasingCurve(QEasingCurve.Linear);self.animation.valueChanged.connect(self.update);self.animation.finished.connect(self.hide_if_finished);self.setGeometry(button.rect());self.hide()
    def animate(self,to):
        current=self.animation.currentValue()
        if current is None:current=0.0
        self.animation.stop();self.animation.setStartValue(float(current));self.animation.setEndValue(float(to))
        if to:self.setGeometry(self.button.rect());self.show();self.raise_()
        self.animation.start()
    def hide_if_finished(self):
        if float(self.animation.currentValue() or 0)<.001:self.hide()
    def paintEvent(self,event):
        if not self.button.isEnabled():return
        progress=float(self.animation.currentValue() or 0)
        if progress<=.001:return
        colors=QApplication.instance().property('karname_flow_colors') or {};ink=QColor(colors.get('accent','#2675B8'));ink.setAlpha(round(140*progress))
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);r=QRectF(self.rect()).adjusted(1,1,-1,-1);radius=min(8,r.height()/2);shape=QPainterPath();shape.addRoundedRect(r,radius,radius)
        if self.button.text().strip() and r.width()>=80 and r.height()>=28:
            # Preserve the button's original text, icon and font; a light
            # frosted glass expanding highlight provides subtle motion across all sections.
            amount=bezier(progress,.19,1,.22,1);circle=QPainterPath();diameter=(r.width()**2+r.height()**2)**.5*amount;circle.addEllipse(r.center(),diameter/2,diameter/2);tint=QColor(colors.get('accent','#2675B8'));tint.setAlpha(round(36*progress));p.save();p.setClipPath(shape);p.fillPath(circle,tint)
            sheen=QLinearGradient(r.topLeft(),r.bottomLeft());sheen.setColorAt(0.0,QColor(255,255,255,round(55*progress)));sheen.setColorAt(0.45,QColor(255,255,255,0));p.fillRect(r,sheen);p.restore()
        p.setBrush(Qt.NoBrush);p.setPen(QPen(ink,1.2));p.drawPath(shape);p.end()

class FlowFilter(QObject):
    def animate(self,button,to):
        anim=getattr(button,'_karname_flow_animation',None)
        if anim is None:
            anim=QVariantAnimation(button);anim.setDuration(FLOW_DURATION_MS);anim.setEasingCurve(QEasingCurve.Linear);anim.valueChanged.connect(button.update);button._karname_flow_animation=anim
        current=anim.currentValue()
        if current is None:current=1.0 if button.underMouse() and not to else 0.0
        anim.stop();anim.setStartValue(float(current));anim.setEndValue(float(to));anim.start()
    def eventFilter(self,obj,event):
        if event.type()==QEvent.ToolTip and ((isinstance(obj,(QLabel,QCheckBox)) and any(c.isalpha() for c in obj.text())) or (isinstance(obj,QComboBox) and bool(obj.currentText().strip()))):
            QToolTip.hideText();return True
        if not eligible(obj):return False
        kind=event.type()
        if kind==QEvent.ToolTip and has_readable_label(obj):
            QToolTip.hideText();return True
        if obj.property('flowNative') is True:return False
        if emoji_only(obj) and obj.icon().isNull():
            motion=getattr(obj,'_karname_emoji_motion',None)
            if kind==QEvent.Enter and obj.isEnabled():
                if motion is None:motion=EmojiMotion(obj);obj._karname_emoji_motion=motion
                motion.animate(True)
            elif kind==QEvent.Leave and motion is not None:motion.animate(False)
            elif kind==QEvent.EnabledChange and motion is not None and not obj.isEnabled():motion.anim.stop();obj.setFont(motion.base)
            return False
        if obj.property('flowShiny') is True:
            if obj.property('flowCustomLiquid') is True:
                return False
            shiny=getattr(obj,'_karname_shiny_overlay',None)
            if kind==QEvent.Show:
                if shiny is None:shiny=ShinyOverlay(obj);obj._karname_shiny_overlay=shiny
                shiny.setGeometry(obj.rect());shiny.show();shiny.raise_()
            elif shiny is not None:
                if kind==QEvent.Resize:shiny.setGeometry(obj.rect())
                elif kind==QEvent.Enter:shiny.animate(True)
                elif kind==QEvent.Leave:shiny.animate(False)
                elif kind==QEvent.EnabledChange and not obj.isEnabled():shiny.animation.stop();obj.setIconSize(shiny.base_icon_size);shiny.hover=False;shiny.update()
                elif kind in (QEvent.EnabledChange,QEvent.MouseButtonPress,QEvent.MouseButtonRelease):shiny.update()
            return False
        if not primary(obj):
            overlay=getattr(obj,'_karname_flow_overlay',None)
            if kind==QEvent.Enter and obj.isEnabled():
                if overlay is None:overlay=FlowOverlay(obj);obj._karname_flow_overlay=overlay
                overlay.animate(1)
            elif kind==QEvent.Leave and overlay is not None:overlay.animate(0)
            elif kind==QEvent.Resize and overlay is not None:overlay.setGeometry(obj.rect())
            elif kind==QEvent.EnabledChange and overlay is not None and not obj.isEnabled():overlay.animation.stop();overlay.hide()
            elif kind in (QEvent.MouseButtonPress,QEvent.MouseButtonRelease) and overlay is not None:overlay.update()
            return False
        if kind in (QEvent.Polish,QEvent.Show) and not obj.testAttribute(Qt.WA_TranslucentBackground):
            obj.setAttribute(Qt.WA_TranslucentBackground,True)
        if kind in (QEvent.Polish,QEvent.Show):
            needed=label_width(obj)+(24 if obj.property('flowCompact') else 96)+(22 if not obj.icon().isNull() else 0)
            if needed>obj.minimumWidth() and obj.maximumWidth()>=needed:obj.setMinimumWidth(needed)
        if kind==QEvent.Enter and obj.isEnabled():self.animate(obj,1)
        elif kind==QEvent.Leave:self.animate(obj,0)
        elif kind in (QEvent.EnabledChange,QEvent.FocusIn,QEvent.FocusOut,QEvent.MouseButtonPress,QEvent.MouseButtonRelease):obj.update()
        elif kind==QEvent.Paint and obj.isEnabled():
            self.paint(obj);return True
        return False
    def paint(self,button):
        app=QApplication.instance();colors=app.property('karname_flow_colors') or {}
        dark=bool(app.property('karname_dark')) and button.objectName()!='LoginSubmit'
        ink=QColor('#FFFFFF' if dark else '#111111');foreground=QColor('#111111' if dark else '#FFFFFF')
        anim=getattr(button,'_karname_flow_animation',None);value=anim.currentValue() if anim else None;progress=max(0.0,min(1.0,float(value))) if value is not None else (1.0 if button.underMouse() else 0.0)
        p=QPainter(button);p.setRenderHint(QPainter.Antialiasing);r=QRectF(button.rect()).adjusted(1,1,-1,-1)
        if button.isDown():r.adjust(r.width()*.025,r.height()*.025,-r.width()*.025,-r.height()*.025)
        edge=bezier(min(1,progress*800/600),.23,1,.32,1);moving=bezier(progress,.34,1.56,.64,1);circle_progress=bezier(progress,.19,1,.22,1);text_progress=bezier(progress,0,0,.58,1)
        radius=min(r.height()/2,100)*(1-edge)+min(12,r.height()/2)*edge;shape=QPainterPath();shape.addRoundedRect(r,radius,radius)
        border=QColor(ink);border.setAlpha(round((.4*(1-edge) if not button.hasFocus() else .9)*255))
        p.setPen(QPen(border,2 if button.hasFocus() else 1.5));p.setBrush(Qt.NoBrush);p.drawPath(shape)
        circle=QPainterPath();diameter=16+((r.width()**2+r.height()**2)**.5+2-16)*circle_progress;circle.addEllipse(QPointF(r.center()),diameter/2,diameter/2)
        p.save();p.setClipPath(shape);fill=QColor(ink);fill.setAlpha(round(255*circle_progress));p.fillPath(circle,fill);p.restore()
        # The original arrows are 16px on the left and right and travel in
        # opposite directions. Keep enough room for text on small controls.
        compact=bool(button.property('flowCompact')) or r.width()<label_width(button)+96
        margin=6 if compact else 44;text_rect=r.adjusted(margin,0,-margin,0)
        if not compact:text_rect.translate(-4+8*text_progress,0)
        rtl=button.layoutDirection()==Qt.RightToLeft
        if not button.icon().isNull() and r.width()>=80:
            icon_size=min(18,int(r.height()-8));x=text_rect.right()-icon_size if rtl else text_rect.left();rect=QRectF(x,r.center().y()-icon_size/2,icon_size,icon_size)
            button.icon().paint(p,rect.toRect(),Qt.AlignCenter);text_rect.adjust(0 if rtl else icon_size+4,0,-icon_size-4 if rtl else 0,0)
        font=button.font();font.setBold(True);p.setFont(font);text=QFontMetrics(font).elidedText(button.text().replace('&',''),Qt.ElideRight,max(0,int(text_rect.width())))
        def label(color):
            p.setPen(color);p.drawText(text_rect,Qt.AlignCenter|Qt.TextSingleLine,text)
        label(ink)
        inverse=inverse_is_clearer(ink,foreground,QColor(colors.get('panel','#FFFFFF')),circle_progress)
        if inverse:
            p.save();p.setClipPath(shape.intersected(circle));label(foreground);p.restore()
        y=r.center().y()
        def arrows(color):
            pen=QPen(color,1.8);pen.setCapStyle(Qt.RoundCap);pen.setJoinStyle(Qt.RoundJoin);p.setPen(pen)
            left=(r.left()-.25*r.width()+8)*(1-moving)+(r.left()+24)*moving
            right=(r.right()-24)*(1-moving)+(r.right()+.25*r.width()-8)*moving
            for x in (left,right):
                p.drawLine(QPointF(x-5,y),QPointF(x+5,y));p.drawLine(QPointF(x+5,y),QPointF(x+1,y-4));p.drawLine(QPointF(x+5,y),QPointF(x+1,y+4))
        if not compact:
            p.save();p.setClipPath(shape);arrows(ink)
            if inverse:p.setClipPath(shape.intersected(circle));arrows(foreground)
            p.restore()
        p.end()

def install(app,colors):
    app.setProperty('karname_flow_colors',colors)
    if not hasattr(app,'_karname_flow_filter'):
        app._karname_flow_filter=FlowFilter(app);app.installEventFilter(app._karname_flow_filter)
