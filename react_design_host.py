"""Restricted host primitives for bundled React interfaces.

Not yet connected to the application navigation: the live chat must first
support all existing operations and pass integration tests.
"""
from pathlib import Path
import os, mimetypes
from weakref import WeakKeyDictionary
from PySide6.QtCore import QUrl,QFile,QIODevice
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor,QWebEngineUrlScheme,QWebEngineUrlSchemeHandler,QWebEngineUrlRequestJob

MIME_OVERRIDES={
    '.html':'text/html; charset=utf-8',
    '.js':'application/javascript; charset=utf-8',
    '.mjs':'application/javascript; charset=utf-8',
    '.css':'text/css; charset=utf-8',
    '.svg':'image/svg+xml',
    '.json':'application/json; charset=utf-8',
    '.ttf':'font/ttf',
    '.woff':'font/woff',
    '.woff2':'font/woff2',
    '.png':'image/png',
    '.jpg':'image/jpeg',
    '.jpeg':'image/jpeg',
    '.webp':'image/webp',
}

def preview_asset_root(root=None):
    """Resolve the bundled React asset directory, allowing env override for local preview."""
    if root:
        path=Path(root).resolve()
        if path.is_dir():return path
    env=os.getenv('KARNAME_REACT_PREVIEW_ASSETS','').strip()
    if env:
        path=Path(env).resolve()
        if path.is_dir():return path
    from storage import package_file
    bundled=package_file('web/react-design').resolve()
    return bundled if bundled.is_dir() else None

def register_design_scheme():
    # Must run before QApplication is constructed.
    scheme=QWebEngineUrlScheme(b'karname-design');scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme | QWebEngineUrlScheme.Flag.LocalScheme | QWebEngineUrlScheme.Flag.LocalAccessAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)

def _fallback_asset(relative):
    if relative == 'ocean.png':
        from storage import package_file
        alt = package_file('assets/ocean.png').resolve()
        if alt.is_file():
            return alt
    return None

def scheme_file(url,root):
    if url.scheme()!='karname-design' or url.host()!='app' or url.query() or url.fragment():return None
    try:
        folder=Path(root).resolve();relative=url.path().lstrip('/');target=(folder/relative).resolve()
        if target.is_relative_to(folder) and target.is_file():
            return target
        return _fallback_asset(relative)
    except (ValueError,OSError):return None

class BundledSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self,root,parent=None):super().__init__(parent);self.root=root
    def requestStarted(self,job):
        path=scheme_file(job.requestUrl(),self.root)
        if job.requestMethod()!=b'GET' or not path:job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound);return
        f=QFile(str(path),job)
        if not f.open(QIODevice.OpenModeFlag.ReadOnly):job.fail(QWebEngineUrlRequestJob.Error.RequestFailed);return
        mime=MIME_OVERRIDES.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or 'application/octet-stream';job.reply(mime.encode('ascii'),f)

def bundled_url_allowed(url, root):
    """Allow only bundled files, data images, and Qt's web-channel script."""
    if not isinstance(url,QUrl):url=QUrl(url)
    if url.scheme() == 'qrc':return url.path() == '/qtwebchannel/qwebchannel.js'
    if url.scheme() == 'blob':return url.toString().startswith('blob:karname-design://app/')
    if url.scheme() == 'karname-design':return bool(scheme_file(url,root))
    if url.scheme() == 'data':return url.toString().startswith('data:image/')
    if not url.isLocalFile():return False
    try:
        target=Path(url.toLocalFile()).resolve();folder=Path(root).resolve()
        return (target.is_relative_to(folder) and target.is_file()) or target == _fallback_asset('ocean.png')
    except (ValueError,OSError):return False

class BundledRequestPolicy(QWebEngineUrlRequestInterceptor):
    def __init__(self,root,parent=None):super().__init__(parent);self.root=root
    def interceptRequest(self,info):
        if not bundled_url_allowed(info.requestUrl(),self.root):info.block(True)

class BundledPage(QWebEnginePage):
    def __init__(self,profile,root,parent=None):super().__init__(profile,parent);self.root=root
    def acceptNavigationRequest(self,url,kind,isMainFrame):
        return bool(scheme_file(url,self.root))
    def createWindow(self,windowType):return None

_SHARED_PROFILES = WeakKeyDictionary()


def shared_web_profile(root, parent=None):
    """Return a single cached off-the-record QWebEngineProfile per (app, root) to prevent 5x Chromium overhead."""
    from PySide6.QtWidgets import QApplication
    resolved = str(Path(root).resolve())
    app = QApplication.instance()
    if app is not None:
        by_root = _SHARED_PROFILES.get(app)
        if by_root is None:
            by_root = {}
            _SHARED_PROFILES[app] = by_root
        prof = by_root.get(resolved)
        if prof is not None:
            return prof
        prof = QWebEngineProfile(app)
        by_root[resolved] = prof
    else:
        prof = QWebEngineProfile(parent)
    policy = BundledRequestPolicy(resolved, prof)
    prof.setUrlRequestInterceptor(policy)
    prof._karname_policy = policy
    handler = BundledSchemeHandler(resolved, prof)
    prof.installUrlSchemeHandler(b'karname-design', handler)
    prof._karname_handler = handler
    return prof


def should_poll_section(owner, host_widget):
    """Skip background periodic bridge polling on hidden tabs while the main window tabs are visible."""
    if owner is None or host_widget is None:
        return True
    tabs = getattr(owner, 'tabs', None)
    if tabs is not None and tabs.isVisible():
        cur = tabs.currentWidget()
        if cur is None:
            return False
        return bool(host_widget is cur or cur.isAncestorOf(host_widget))
    return True


def sync_page_appearance(page, owner, section='default'):
    """Set QWebEnginePage background and DocumentCreation CSS vars so dark/light themes never flash."""
    if page is None or owner is None:
        return
    try:
        import json
        from PySide6.QtGui import QColor
        from PySide6.QtWebEngineCore import QWebEngineScript
        from section_themes import section_appearance_payload
        settings = owner.data.get('settings', {}) if hasattr(owner, 'data') else {}
        payload = section_appearance_payload(settings, section)
        bg = payload.get('colors', {}).get('bg') or ('#0b1220' if payload.get('dark') else '#f4f7fb')
        page.setBackgroundColor(QColor(bg))
        payload_js = json.dumps(payload, ensure_ascii=False)
        src = (
            "(function(){function applyPre(){try{"
            f"var v={payload_js};var r=document.documentElement;if(!r)return false;var d=!!v.dark;"
            "r.classList.toggle('dark',d);r.style.colorScheme=d?'dark':'light';"
            "var c=v.colors||{};"
            "r.style.setProperty('--color-background',c.bg||(d?'#0b1220':'#f4f7fb'));"
            "r.style.setProperty('--color-foreground',c.text||(d?'#f1f5f9':'#132238'));"
            "r.style.setProperty('--color-card',c.panel||(d?'#141e30':'#ffffff'));"
            "r.style.setProperty('--color-card-foreground',c.text||(d?'#f1f5f9':'#132238'));"
            "r.style.setProperty('--color-popover',c.panel||(d?'#141e30':'#ffffff'));"
            "r.style.setProperty('--color-popover-foreground',c.text||(d?'#f1f5f9':'#132238'));"
            "r.style.setProperty('--color-muted-foreground',c.muted||(d?'#94a3b8':'#64748b'));"
            "r.style.setProperty('--color-border',c.border||(d?'#263449':'#dbe4f0'));"
            "r.style.setProperty('--color-input',c.field||(d?'#182438':'#ffffff'));"
            "r.style.setProperty('--color-muted',c.button||(d?'#1f2d42':'#eef3f8'));"
            "r.style.setProperty('--color-secondary',c.button||(d?'#1f2d42':'#eef3f8'));"
            "r.style.setProperty('--color-secondary-foreground',c.text||(d?'#f1f5f9':'#132238'));"
            "r.style.setProperty('--color-accent',c.hover||(d?'#253650':'#e2ebf5'));"
            "r.style.setProperty('--color-accent-foreground',c.text||(d?'#f1f5f9':'#132238'));"
            "r.style.setProperty('--color-primary',c.accent||'#1b6ca8');"
            "r.style.setProperty('--color-primary-foreground',c.accent_text||'#ffffff');"
            "r.style.setProperty('--glass-bg-subtle',d?'rgba(24, 36, 56, 0.44)':'rgba(255, 255, 255, 0.48)');"
            "if(v.preset)r.setAttribute('data-theme-preset',v.preset);"
            "return true;}catch(e){return false;}}"
            "if(!applyPre()){document.addEventListener('DOMContentLoaded',applyPre,{once:true});}"
            "})();"
        )
        scripts = page.scripts()
        for existing in scripts.find('karname_pretheme'):
            scripts.remove(existing)
        sc = QWebEngineScript()
        sc.setName('karname_pretheme')
        sc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        sc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        sc.setRunsOnSubFrames(False)
        sc.setSourceCode(src)
        scripts.insert(sc)
    except Exception:
        pass


def confirm_download(download,parent=None):
    """Save only after an explicit local file choice, never auto-accept."""
    from PySide6.QtWidgets import QFileDialog
    if not download.url().toString().startswith('blob:karname-design://app/'):
        download.cancel();return
    suggested=Path(download.suggestedFileName().replace('\\','/')).name or 'download'
    path,_=QFileDialog.getSaveFileName(parent,'ذخیره پیوست',suggested)
    if not path:download.cancel();return
    target=Path(path);download.setDownloadDirectory(str(target.parent));download.setDownloadFileName(target.name);download.accept()
