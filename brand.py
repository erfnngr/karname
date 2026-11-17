"""Brand assets remain unmodified; views scale the supplied originals."""
from PySide6.QtCore import Qt,QSize
from PySide6.QtGui import QPixmap,QIcon,QColor,QPainter,QPen,QImage
from PySide6.QtWidgets import QLabel,QApplication
from storage import package_file
from reminders import group_of

COMPANIES={'مانا':dict(file='mana.jpg',color='#075E70',popup='#D8EFF0'),'آیریا':dict(file='airia.jpg',color='#104B70',popup='#E0EBF6'),'آرکا':dict(file='arka.jpg',color='#104B70',popup='#DDEBF8')}

from company_defaults import company_order
CUSTOM={}
_DARK_LOGOS={}

def register_company(company):
    name=company['name'];color=company.get('color') or '#187C85'
    _DARK_LOGOS.pop(name,None)
    if company.get('logo'):CUSTOM[name]=dict(data=company['logo'],color=color,popup=color)
    elif name in COMPANIES and company.get('color'):CUSTOM[name]=dict(COMPANIES[name],color=color,popup=color)
    elif name not in COMPANIES:CUSTOM[name]=dict(data='',color=color,popup=color)

def company_brand(name):
    name=str(name or '')
    canonical={'mana':'مانا','airia':'آیریا','ایریا':'آیریا','arka':'آرکا'}.get(name.strip().casefold(),name)
    return CUSTOM.get(name) or CUSTOM.get(canonical) or next((v for k,v in COMPANIES.items() if k in canonical),None)

def company_group(name):
    name=str(name or '').strip()
    return None if name in ('','شخصی','__personal__') else name

def dark_variant(pix):
    """Render a light mark on transparent background without changing its source."""
    if pix.isNull():return pix
    pix=pix.scaled(520,520,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    img=pix.toImage().convertToFormat(QImage.Format_RGBA8888)
    w,h=img.width(),img.height()
    if w<=0 or h<=0:return pix
    corners=[img.pixelColor(x,y) for x,y in ((0,0),(w-1,0),(0,h-1),(w-1,h-1))]
    white_bg=all(c.alpha()>220 and min(c.red(),c.green(),c.blue())>225 for c in corners)
    transparent_bg=any(c.alpha()<40 for c in corners)
    if not white_bg and not transparent_bg:return pix
    # Fast C-level tinting via QPainter instead of a 270k-pixel Python loop
    if white_bg:
        from PySide6.QtGui import QImage as _QI
        raw=bytearray(img.constBits())
        stride=img.bytesPerLine()
        # Vectorized lookup for white-to-alpha fade using RGB minimum per 4-byte pixel
        fade=bytes(min(255,max(0,(247-v)*255//105)) for v in range(256))
        for y in range(h):
            row_start=y*stride
            row=raw[row_start:row_start+w*4]
            r=row[0::4];g=row[1::4];b=row[2::4];a=row[3::4]
            new_a=bytes((ai*fade[min(ri,gi,bi)])//255 for ri,gi,bi,ai in zip(r,g,b,a))
            row[3::4]=new_a
            raw[row_start:row_start+w*4]=row
        alpha_img=_QI(bytes(raw),w,h,stride,_QI.Format_RGBA8888).copy()
        masked=QPixmap.fromImage(alpha_img)
    else:
        masked=QPixmap.fromImage(img)
    tinted=QPixmap(masked.size())
    tinted.fill(Qt.transparent)
    p=QPainter(tinted)
    p.drawPixmap(0,0,masked)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(tinted.rect(),QColor(228,245,244))
    p.end()
    return tinted

def company_pixmap(name,dark=False):
    brand=company_brand(name)
    if not brand:return QPixmap()
    if dark and name in _DARK_LOGOS:return _DARK_LOGOS[name]
    if 'data' in brand:
        import base64
        pix=QPixmap()
        if brand['data']:pix.loadFromData(base64.b64decode(brand['data']))
    else:
        pix=QPixmap(str(package_file('assets/'+brand['file'])))
        if brand['file']=='arka.jpg':pix=pix.copy(int(pix.width()*.2),int(pix.height()*.13),int(pix.width()*.75),int(pix.height()*.55))
    if dark:pix=dark_variant(pix);_DARK_LOGOS[name]=pix
    return pix

def gear_icon(color='white'):
    from ui_icons import symbol
    return symbol('settings',color)

def logo(name,size=34):
    app=QApplication.instance();dark=bool(app and app.property('karname_dark'));brand=company_brand(name);w=QLabel();w.setFixedSize(size,size);w.setStyleSheet(('background:transparent;' if dark else 'background:white;')+'border-radius:7px;padding:2px;')
    if name=='کارنامه':
        pix=QPixmap(str(package_file('assets/karname.png')))
        if dark:
            if name not in _DARK_LOGOS:_DARK_LOGOS[name]=dark_variant(pix)
            pix=_DARK_LOGOS[name]
        w.setPixmap(pix.scaled(size-4,size-4,Qt.KeepAspectRatio,Qt.SmoothTransformation));w.setAlignment(Qt.AlignCenter)
    elif brand:w.setPixmap(company_pixmap(name,dark).scaled(size-4,size-4,Qt.KeepAspectRatio,Qt.SmoothTransformation));w.setAlignment(Qt.AlignCenter)
    else:w.setText('●');w.setAlignment(Qt.AlignCenter)
    return w

def event_type(event):
    if group_of(event)=='personal':return 'personal'
    return 'insurance' if 'بیمه' in event.get('category','')+event.get('title','') else 'tax'

def row_colors(event,settings):
    from appearance import palette_for
    palette=palette_for(settings)
    kind=event_type(event);color=QColor(settings['event_'+kind+'_color']);base=QColor(palette['panel']);alpha=settings.get('event_'+kind+'_opacity',18)/100
    bg=QColor(round(base.red()*(1-alpha)+color.red()*alpha),round(base.green()*(1-alpha)+color.green()*alpha),round(base.blue()*(1-alpha)+color.blue()*alpha))
    from appearance import contrast
    fg=palette['text']
    if contrast(fg,bg.name())<4.5:fg=max(('#FFFFFF','#111111'),key=lambda value:contrast(value,bg.name()))
    return bg.name(),fg,color.name()

def popup_style(company,settings):
    result=dict(settings);brand=company_brand(company)
    name=str(company or '').casefold();key='mana' if 'مانا' in name or name=='mana' else 'airia' if 'آیریا' in name or 'ایریا' in name or name=='airia' else 'arka' if 'آرکا' in name or name=='arka' else 'personal'
    result['popup_bg']=settings.get(key+'_popup_color',brand['popup'] if brand else '#EEE5FA')
    if company in CUSTOM:result['popup_bg']=CUSTOM[company]['popup']
    from appearance import contrast
    result['popup_fg']=max(('#132D43','#FFFFFF','#000000'),key=lambda value:contrast(value,result['popup_bg']))
    return result,brand
