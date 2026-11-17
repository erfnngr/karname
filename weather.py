"""Asynchronous weather data from the configurable keyless API."""
import json, math, os, tempfile, threading, time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urljoin
import requests
from PySide6.QtCore import QObject, Signal, QTimer
from storage import package_file, app_dir

TEHRAN = timezone(timedelta(hours=3, minutes=30))

def is_night_local(dt):
    """Approximate Tehran seasonal nighttime check when upstream payload omits is_day."""
    if dt is None:
        return False
    local = dt.astimezone(TEHRAN) if dt.tzinfo else dt
    doy = local.timetuple().tm_yday
    # Peak summer solstice (~day 172) shifts sunrise earlier (~4.8) & sunset later (~19.4); winter solstice (~5.2 -> ~17.0)
    seasonal = math.sin(2.0 * math.pi * (doy - 80) / 365.25)
    sunrise = 5.95 - 0.95 * seasonal
    sunset = 18.15 + 1.25 * seasonal
    hour_f = local.hour + local.minute / 60.0
    return hour_f < sunrise or hour_f >= sunset


def _apply_day_night(symbol, dt=None, explicit_is_day=None):
    if not isinstance(symbol, dict):
        return symbol
    out = dict(symbol)
    emoji = str(out.get('icon', '') or '')
    if explicit_is_day is not None:
        night = not bool(explicit_is_day)
    elif 'is_day' in out and out.get('is_day') is not None:
        night = not bool(out.get('is_day'))
    elif '🌙' in emoji:
        night = True
    elif dt is not None:
        night = is_night_local(dt)
    else:
        night = False
    out['is_day'] = not night
    if night:
        out['icon'] = '🌙'
    elif '🌙' in emoji:
        out['icon'] = ''
    return out


def weather_kind(symbol, at_time=None):
    if isinstance(symbol, dict):
        code=symbol.get('code'); desc=symbol.get('fa') or 'نامشخص'; emoji=symbol.get('icon','')
        explicit = symbol.get('is_day')
        night = (not bool(explicit)) if explicit is not None else ('🌙' in emoji or is_night_local(at_time))
        if code in (95,96,99): kind='cloud-lightning'
        elif code in (71,73,75,77,85,86): kind='cloud-snow'
        elif code in (51,53,55,56,57,61,63,65,66,67,80,81,82): kind='cloud-rain'
        elif code in (45,48): kind='cloud-fog'
        elif code==0: kind='moon' if night else 'sun'
        elif code in (1,2): kind='cloud-moon' if night else 'cloud-sun'
        else: kind='cloud'
        return kind,desc
    raw=str(symbol or '')
    if 'moon' in raw or 'night' in raw:
        return ('cloud-moon' if 'cloud' in raw else 'moon'), 'شب صاف'
    if 'clear' in raw or 'sun' in raw:
        return ('cloud-sun' if 'partly' in raw or 'cloud' in raw else 'sun'), 'صاف'
    return 'cloud',str(symbol or 'نامشخص')

def parse_forecast(payload, now=None):
    location=payload['location']; offset=int(location.get('utc_offset_seconds',12600)); tz=timezone(timedelta(seconds=offset))
    now=(now or datetime.now(timezone.utc)).astimezone(tz)
    def temperature(value):
        value=float(value)
        if not math.isfinite(value) or not -90<=value<=65: raise ValueError('دمای نامعتبر')
        return value
    def local_datetime(value):
        value=datetime.fromisoformat(value)
        return value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)
    row=payload['current']; when=local_datetime(row['time'])
    if abs((when-now).total_seconds())>6*3600: raise ValueError('اطلاعات به‌روز نیست')
    current_sym=_apply_day_night(row.get('weather',{}),dt=when,explicit_is_day=row.get('is_day'))
    current=dict(temp=temperature(row['temperature']),symbol=current_sym,time=when,humidity=row.get('humidity'),wind=row.get('wind_speed'),feels=row.get('apparent_temperature'))
    meta=payload.get('meta') if isinstance(payload.get('meta'),dict) else {}
    observation=row.get('observation') if isinstance(row.get('observation'),dict) else {}
    source=str(meta.get('current_source') or '')
    if observation and source.startswith('metar:'):
        observed=str(observation.get('observed_at') or meta.get('current_observed_at') or '')
        try:
            if observed:
                timestamp=datetime.fromisoformat(observed.replace('Z','+00:00'))
            else:
                reported_age=float(observation['age_minutes'])
                if not math.isfinite(reported_age) or not 0<=reported_age<=24*60:raise ValueError()
                generated=meta.get('generated_at')
                timestamp=datetime.fromisoformat(str(generated).replace('Z','+00:00')) if generated else now-timedelta(seconds=max(0,min(86400,float(meta.get('cache_age_seconds') or 0))))
                timestamp-=timedelta(minutes=reported_age)
            if timestamp.tzinfo is None:raise ValueError()
            age=(now.astimezone(timezone.utc)-timestamp.astimezone(timezone.utc)).total_seconds()/60
            if not -10<=age<=24*60:raise ValueError()
            current['observation']=dict(station_name=str(observation.get('station_name') or '')[:160],observed_at=timestamp.isoformat())
        except (ValueError,OverflowError,TypeError):pass
    current['model_temperature']=source=='open-meteo'
    hours=[]
    for item in payload.get('hourly',[])[:48]:
        try:
            dt=local_datetime(item['time'])
            if dt>=now.replace(minute=0,second=0,microsecond=0):
                hsym=_apply_day_night(item.get('weather',{}),dt=dt,explicit_is_day=item.get('is_day'))
                hours.append(dict(time=dt,temp=temperature(item['temperature']),symbol=hsym))
        except (ValueError,TypeError,KeyError,OverflowError): continue
    days=[]
    for item in payload.get('daily',[])[:14]:
        try:
            day=datetime.fromisoformat(item['date']).date(); low=temperature(item['temp_min']); high=temperature(item['temp_max'])
            if 0<=(day-now.date()).days<7 and low<=high:days.append(dict(date=day,min=low,max=high,symbol=item.get('weather',{})))
        except (ValueError,TypeError,KeyError,OverflowError):continue
    if not hours or not days:raise ValueError('پیش‌بینی کامل نیست')
    return dict(current=current,hours=hours[:24],days=days[:7],location=location.get('name') or 'تهران',units=payload.get('units',{}))

def parse_backup_forecast(daily,hourly,now=None):
    """Interpolate a three-hourly forecast when the primary service is unavailable."""
    now=(now or datetime.now(timezone.utc)).astimezone(TEHRAN)
    base=datetime.strptime(hourly['init'],'%Y%m%d%H').replace(tzinfo=timezone.utc);points=[];days=[]
    def symbol(raw):
        raw=str(raw or '').lower()
        code=95 if 'ts' in raw or 'thunder' in raw else 71 if 'snow' in raw or 'sleet' in raw else 61 if 'rain' in raw or 'shower' in raw else 45 if 'fog' in raw else 2 if 'pcloudy' in raw or 'mcloudy' in raw else 3 if 'cloudy' in raw else 0
        desc={0:'صاف',2:'نیمه‌ابری',3:'ابری',45:'مه‌آلود',61:'بارانی',71:'برفی',95:'رعدوبرق'}[code]
        return {'code':code,'fa':desc,'icon':'🌙' if 'night' in raw else ''}
    for item in hourly.get('dataseries',[])[:100]:
        try:
            when=(base+timedelta(hours=int(item['timepoint']))).astimezone(TEHRAN);temp=float(item['temp2m'])
            if math.isfinite(temp) and -90<=temp<=65:points.append((when,temp,symbol(item.get('weather'))))
        except (ValueError,KeyError,TypeError,OverflowError):continue
    points.sort(key=lambda row:row[0])
    if not points:raise ValueError('پیش‌بینی پشتیبان موجود نیست')
    closest=min(points,key=lambda row:abs((row[0]-now).total_seconds()))
    if abs((closest[0]-now).total_seconds())>6*3600:raise ValueError('پیش‌بینی پشتیبان قدیمی است')
    for item in daily.get('dataseries',[])[:10]:
        try:
            day=datetime.strptime(str(item['date']),'%Y%m%d').date();low=float(item['temp2m']['min']);high=float(item['temp2m']['max'])
            if 0<=(day-now.date()).days<7 and -90<=low<=high<=65:days.append(dict(date=day,min=low,max=high,symbol=symbol(item.get('weather'))))
        except (ValueError,KeyError,TypeError,OverflowError):continue
    hours=[];first=now.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
    for i in range(24):
        target=first+timedelta(hours=i)
        for left,right in zip(points,points[1:]):
            gap=(right[0]-left[0]).total_seconds()
            if left[0]<=target<=right[0] and 0<gap<=4*3600:
                ratio=(target-left[0]).total_seconds()/gap
                hours.append(dict(time=target,temp=left[1]+(right[1]-left[1])*ratio,symbol=left[2] if ratio<.5 else right[2]));break
    if not days or len(hours)<6:raise ValueError('پیش‌بینی پشتیبان کامل نیست')
    return dict(current=dict(time=closest[0],temp=closest[1],symbol=closest[2]),hours=hours,days=days,location='تهران',units={'temperature':'°C'},estimated=True)

def parse_openmeteo(payload, now=None):
    """Normalize model data without presenting it as a station observation."""
    descriptions={0:'صاف',1:'عمدتاً صاف',2:'نیمه‌ابری',3:'ابری',45:'مه‌آلود',48:'مه‌آلود',51:'نم‌نم باران',53:'نم‌نم باران',55:'نم‌نم باران',56:'باران یخ‌زده',57:'باران یخ‌زده',61:'بارانی',63:'بارانی',65:'بارانی',66:'باران یخ‌زده',67:'باران یخ‌زده',71:'برفی',73:'برفی',75:'برفی',77:'برفی',80:'رگبار',81:'رگبار',82:'رگبار',85:'رگبار برف',86:'رگبار برف',95:'رعدوبرق',96:'رعدوبرق',99:'رعدوبرق'}
    def symbol(code, is_day=True):
        code=int(code)
        return {'code':code,'fa':descriptions.get(code,'نامشخص'),'icon':'' if is_day else '🌙'}
    row=payload['current'];hourly=payload['hourly'];daily=payload['daily']
    hourly_days = hourly.get('is_day') or [None] * len(hourly['time'])
    normalized={'location':{'name':'تهران','utc_offset_seconds':payload['utc_offset_seconds']},'units':{'temperature':'°C'},'meta':{'current_source':'open-meteo'},
        'current':{'time':row['time'],'temperature':row['temperature_2m'],'weather':symbol(row['weather_code'],row.get('is_day',1)),'humidity':row.get('relative_humidity_2m'),'wind_speed':row.get('wind_speed_10m'),'apparent_temperature':row.get('apparent_temperature')},
        'hourly':[{'time':t,'temperature':v,'is_day':d,'weather':symbol(c,True if d is None else bool(d))} for t,v,c,d in zip(hourly['time'],hourly['temperature_2m'],hourly['weather_code'],hourly_days) if v is not None and c is not None],
        'daily':[{'date':t,'temp_min':lo,'temp_max':hi,'weather':symbol(c)} for t,lo,hi,c in zip(daily['time'],daily['temperature_2m_min'],daily['temperature_2m_max'],daily['weather_code']) if lo is not None and hi is not None and c is not None]}
    return parse_forecast(normalized,now)

def fetch_openmeteo():
    response=requests.get('https://api.open-meteo.com/v1/forecast',params={'latitude':35.6892,'longitude':51.3890,'current':'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day','hourly':'temperature_2m,weather_code,is_day','daily':'weather_code,temperature_2m_max,temperature_2m_min','forecast_days':7,'timezone':'Asia/Tehran','wind_speed_unit':'kmh'},timeout=(5,10),allow_redirects=False)
    response.raise_for_status()
    if response.is_redirect or len(response.content)>2_000_000:raise ValueError('پاسخ نامعتبر')
    return parse_openmeteo(response.json())

def save_cached(data,checked_at):
    path=app_dir()/'weather-cache.json'
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        serial=dict(data,current=dict(data['current'],time=data['current']['time'].isoformat()),hours=[dict(row,time=row['time'].isoformat()) for row in data['hours']],days=[dict(row,date=row['date'].isoformat()) for row in data['days']])
        fd,name=tempfile.mkstemp(prefix='weather-',suffix='.tmp',dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump({'checked_at':checked_at.isoformat(),'data':serial},f,ensure_ascii=False)
            os.replace(name,path)
        finally:
            if os.path.exists(name):os.unlink(name)
    except (OSError,TypeError,ValueError):pass

def load_cached():
    try:
        raw=json.loads((app_dir()/'weather-cache.json').read_text(encoding='utf-8'));stamp=datetime.fromisoformat(raw['checked_at'])
        if stamp.tzinfo is None:return None,None
        age=(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
        if not 0<=age<=48*3600:return None,None
        data=raw['data'];data['current']['time']=datetime.fromisoformat(data['current']['time'])
        for row in data['hours']:row['time']=datetime.fromisoformat(row['time'])
        for row in data['days']:row['date']=datetime.fromisoformat(row['date']).date()
        if not data['days'] or not data['hours']:return None,None
        return data,stamp
    except (OSError,ValueError,KeyError,TypeError,OverflowError):return None,None

class WeatherService(QObject):
    changed=Signal();done=Signal(object,object,int);comparison_changed=Signal();comparison_done=Signal(object,object,int)
    def __init__(self,parent=None):
        super().__init__(parent);self.enabled=False;self.data,self.checked_at=load_cached();self.cached=bool(self.data);self.error='';self.busy=False;self.next_check=0;self.generation=0
        try:self.base_url=json.loads(package_file('data/weather_config.json').read_text(encoding='utf-8'))['base_url'].rstrip('/')
        except (OSError,ValueError,KeyError):self.base_url=''
        self.default_base_url=self.base_url
        self.comparison=None;self.comparison_error='';self.comparison_busy=False;self.comparison_checked=0
        self.done.connect(self._done);self.comparison_done.connect(self._comparison_done);self.timer=QTimer(self);self.timer.setInterval(60*1000);self.timer.timeout.connect(self.refresh);self.timer.start()
    def configure(self,enabled=True,base_url=None):
        self.enabled=bool(enabled)
        if base_url is not None and base_url.rstrip('/')!=self.base_url:
            self.base_url=base_url.rstrip('/');self.next_check=0;self.generation+=1;self.comparison=None;self.comparison_checked=0
        self.refresh()
    def refresh(self):
        if not self.enabled or self.busy or time.time()<self.next_check:return
        self.busy=True;self.error='';self.changed.emit();url=self.base_url;generation=self.generation
        def work():
            try:
                try:
                    parts=urlsplit(url)
                    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:raise ValueError('نشانی سرویس نامعتبر است')
                    response=requests.get(url+'/api/weather',params={'city':'تهران','units':'metric'},timeout=(5,10),allow_redirects=False);response.raise_for_status()
                    if response.is_redirect:raise ValueError('انتقال غیرمنتظره')
                    if len(response.content)>2_000_000:raise ValueError('پاسخ بیش از حد بزرگ است')
                    value=parse_forecast(response.json())
                except (requests.RequestException,ValueError,KeyError,TypeError,OverflowError):
                    try:
                        value=fetch_openmeteo()
                    except (requests.RequestException,ValueError,KeyError,TypeError,OverflowError):
                        def backup(product):
                            result=requests.get('https://www.7timer.info/bin/api.pl',params={'lat':'35.6892','lon':'51.3890','product':product,'output':'json'},timeout=(5,10),allow_redirects=False);result.raise_for_status()
                            if result.is_redirect:
                                target=urljoin(result.url,result.headers.get('Location',''));parts=urlsplit(target)
                                if parts.scheme!='https' or parts.hostname!='www.7timer.info' or parts.username or parts.password:raise ValueError('انتقال نامعتبر')
                                result=requests.get(target,timeout=(5,10),allow_redirects=False);result.raise_for_status()
                                if result.is_redirect:raise ValueError('انتقال مکرر')
                            if len(result.content)>2_000_000:raise ValueError('پاسخ بیش از حد بزرگ است')
                            return result.json()
                        value=parse_backup_forecast(backup('civillight'),backup('civil'))
                error=None
            except Exception:
                value=None;error='دریافت آب‌وهوا ممکن نشد؛ اتصال یا نشانی سرویس را بررسی کنید.'
            try:self.done.emit(value,error,generation)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()
    def _done(self,value,error,generation):
        self.busy=False
        if generation!=self.generation:self.refresh();return
        self.error=error or '';self.next_check=time.time()+(60 if error else 300)
        if value:
            self.data=value;self.checked_at=datetime.now(TEHRAN);self.cached=False;save_cached(value,self.checked_at)
        self.changed.emit()
    def compare(self):
        if self.comparison_busy:return
        if self.comparison and time.time()-self.comparison_checked<300:self.comparison_changed.emit();return
        self.comparison_busy=True;self.comparison_error='';self.comparison_changed.emit();url=self.base_url;generation=self.generation
        def work():
            try:
                parts=urlsplit(url)
                if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:raise ValueError()
                response=requests.get(url+'/api/compare',params={'city':'تهران'},timeout=(5,10),allow_redirects=False);response.raise_for_status()
                if response.is_redirect or len(response.content)>500000:raise ValueError()
                result=response.json();model=float(result['model']['temperature']);observed=float(result['observation']['temperature'])
                if not math.isfinite(model) or not math.isfinite(observed) or not (-90<=model<=65 and -90<=observed<=65):raise ValueError()
                value=dict(model=model,observation=observed,difference=model-observed);error=None
            except (requests.RequestException,ValueError,KeyError,TypeError,OverflowError):value=None;error='مقایسه اکنون در دسترس نیست.'
            try:self.comparison_done.emit(value,error,generation)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()
    def _comparison_done(self,value,error,generation):
        self.comparison_busy=False
        if generation!=self.generation:return
        self.comparison=value;self.comparison_error=error or '';self.comparison_checked=time.time() if value else 0;self.comparison_changed.emit()
