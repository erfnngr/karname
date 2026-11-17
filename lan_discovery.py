"""Small, signed LAN discovery; only the bundled company's identity is trusted."""
import base64,ctypes,hashlib,ipaddress,json,os,re,secrets,select,socket,ssl,struct,threading,time
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding

PORT=8844
PROTOCOL='karname-lan-v1'
from assistant_model import GEMMA_MODEL

def packed(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def private_ip(value,loopback=False):
    try:
        ip=ipaddress.IPv4Address(value)
        return (loopback and ip.is_loopback) or any(ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))
    except ValueError:return False

def addresses():
    """IPv4 interface addresses, including directed broadcasts, without a scan."""
    result=[]
    if os.name=='nt':
        try:
            api=ctypes.WinDLL('iphlpapi');size=ctypes.c_ulong(0);api.GetIpAddrTable(None,ctypes.byref(size),False)
            buf=ctypes.create_string_buffer(size.value)
            if api.GetIpAddrTable(buf,ctypes.byref(size),False)==0:
                count=struct.unpack_from('=I',buf.raw)[0]
                for i in range(min(count,64)):
                    ip,_,mask,*_=struct.unpack_from('=6I',buf.raw,4+i*24)
                    ip=socket.inet_ntoa(struct.pack('=I',ip));mask=socket.inet_ntoa(struct.pack('=I',mask))
                    if private_ip(ip):
                        net=ipaddress.ip_network(ip+'/'+mask,strict=False)
                        if net.prefixlen<31:result.append((ip,str(net.broadcast_address)))
        except (OSError,ValueError,struct.error):pass
    if not result:
        try:
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                if private_ip(ip):result.append((ip,str(ipaddress.ip_network(ip+'/24',strict=False).broadcast_address)))
        except OSError:pass
    return list(dict.fromkeys(result))

def preferred_address(hint=''):
    ips=[ip for ip,_ in addresses()]
    if hint in ips:return hint
    return next((ip for ip in ips if ip.startswith('192.168.')),next(iter(ips),hint or '127.0.0.1'))

def load_profile(root=None):
    from storage import package_file
    custom=Path(root)/'network-defaults.json' if root else None
    path=custom if custom and custom.is_file() else package_file('data/network-defaults.json')
    # Test and preview folders never reach a production network by accident.
    if os.getenv('TAXCALENDAR_DATA_DIR') and not (custom and custom.is_file()):return None
    try:
        if path.stat().st_size>16384:raise ValueError()
        value=json.loads(path.read_text('utf-8'));cert=x509.load_pem_x509_certificate(value['certificate'].encode('ascii'))
        fingerprint=cert.fingerprint(hashes.SHA256()).hex().upper()
        if value.get('fingerprint')!=fingerprint or not private_ip(value['preferred_ip'],True):raise ValueError()
        if type(value.get('port')) is not int or not 1024<=value['port']<=65535:raise ValueError()
        return value
    except (OSError,ValueError,KeyError,TypeError,UnicodeError):return None

def trust_file(root,profile):
    target=Path(root)/'network-trust'/(profile['fingerprint']+'.pem');raw=profile['certificate'].encode('ascii')
    if not target.is_file() or target.read_bytes()!=raw:
        target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.'+secrets.token_hex(4)+'.tmp');temp.write_bytes(raw);temp.replace(target)
    return str(target)

def is_host(root,profile):
    if not profile:return False
    folder=Path(root)/'company-server'
    try:
        cert=x509.load_pem_x509_certificate((folder/'server-cert.pem').read_bytes())
        return (folder/'server-key.pem').is_file() and cert.fingerprint(hashes.SHA256()).hex().upper()==profile['fingerprint']
    except (OSError,ValueError):return False

_HOST_START_LOCK=threading.Lock()
_HOST_START_TIMES={}

def start_configured_host(root,profile):
    """Restart only this computer's previously enabled and identity-matched host."""
    if not is_host(root,profile):return False
    from network_tools import autohost_enabled,start_autohost
    if not autohost_enabled(root):return False
    try:
        cfg=json.loads((Path(root)/'server-host.json').read_text(encoding='utf-8'))
        if not cfg.get('enabled') or int(cfg.get('port',0))!=int(profile['port']):return False
    except (OSError,ValueError,TypeError,KeyError):return False
    try:
        with socket.create_connection(('127.0.0.1',profile['port']),timeout=.25):return False
    except OSError:pass
    with _HOST_START_LOCK:
        key=str(Path(root).resolve());now=time.monotonic()
        if now-_HOST_START_TIMES.get(key,0)<15:return True
        try:process=start_autohost(root)
        except (OSError,ValueError):return False
        if not process:return False
        _HOST_START_TIMES[key]=now;return True

def resolve_with_autostart(root,profile=None,timeout=1.2):
    profile=profile or load_profile(root)
    if not profile:return resolve(root,profile,timeout)
    started=start_configured_host(root,profile)
    deadline=time.monotonic()+(12 if started else 0)
    while True:
        try:return resolve(root,profile,timeout)
        except Exception:
            if not started or time.monotonic()>=deadline:raise
            time.sleep(.4)

def offer(key,fingerprint,nonce,port,model=GEMMA_MODEL):
    value=dict(protocol=PROTOCOL,identity=fingerprint,nonce=nonce,port=port,model=str(model)[:160])
    signature=key.sign(packed(value),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
    return packed(dict(payload=value,signature=base64.b64encode(signature).decode('ascii')))

def parse_offer(raw,nonce,ip,profile):
    try:
        if len(raw)>4096 or not private_ip(ip,True):raise ValueError()
        value=json.loads(raw);p=value['payload']
        if set(p)!={'protocol','identity','nonce','port','model'} or p['protocol']!=PROTOCOL or p['identity']!=profile['fingerprint'] or p['nonce']!=nonce:raise ValueError()
        if type(p['port']) is not int or not 1024<=p['port']<=65535 or not isinstance(p['model'],str) or len(p['model'])>160:raise ValueError()
        cert=x509.load_pem_x509_certificate(profile['certificate'].encode('ascii'))
        cert.public_key().verify(base64.b64decode(value['signature'],validate=True),packed(p),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
        return dict(url='https://'+ip+':'+str(p['port']),fingerprint=profile['fingerprint'],model=p['model'])
    except Exception:return None

class Responder:
    def __init__(self,cert,key,port,discovery_port=PORT,host='0.0.0.0',model=GEMMA_MODEL):
        cert=x509.load_pem_x509_certificate(Path(cert).read_bytes());self.identity=cert.fingerprint(hashes.SHA256()).hex().upper();self.key=serialization.load_pem_private_key(Path(key).read_bytes(),None)
        if self.key.public_key().public_numbers()!=cert.public_key().public_numbers():raise ValueError('کلید شبکه با گواهی میزبان یکسان نیست.')
        self.port=int(port);self.model=model;self.stopping=threading.Event();self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock.bind((host,discovery_port));self.discovery_port=self.sock.getsockname()[1];self.sock.settimeout(.4);self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        recent={};window=time.monotonic();count=0
        while not self.stopping.is_set():
            try:
                raw,address=self.sock.recvfrom(1024);now=time.monotonic()
                if now-window>5:recent={};count=0;window=now
                if len(raw)>256 or not private_ip(address[0],True) or count>=80 or now-recent.get(address[0],0)<.15:continue
                p=json.loads(raw)
                if set(p)!={'protocol','nonce'} or p['protocol']!=PROTOCOL or not re.fullmatch('[0-9a-f]{32}',str(p['nonce'])):continue
                recent[address[0]]=now;count+=1;self.sock.sendto(offer(self.key,self.identity,p['nonce'],self.port,self.model),address)
            except socket.timeout:continue
            except (OSError,ValueError,TypeError,UnicodeError):continue
    def close(self):
        self.stopping.set();self.sock.close();self.thread.join(timeout=1)

def discover(profile,timeout=1.5,targets=None,discovery_port=PORT):
    nonce=secrets.token_hex(16);request=packed(dict(protocol=PROTOCOL,nonce=nonce));sockets=[];found={};end=time.monotonic()+timeout
    destinations=targets or [(None,profile['preferred_ip'])]+[(ip,broadcast) for ip,broadcast in addresses()]+[(None,'255.255.255.255')]
    try:
        for bind,target in destinations[:12]:
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);sock.bind((bind or '',0));sock.sendto(request,(target,discovery_port));sockets.append(sock)
            except OSError:sock.close()
        while sockets and time.monotonic()<end:
            readable,_,_=select.select(sockets,[],[],max(0,end-time.monotonic()))
            for sock in readable:
                raw,address=sock.recvfrom(4097);value=parse_offer(raw,nonce,address[0],profile)
                if value and len(found)<4:found[value['url']]=value
        return list(found.values())
    finally:
        for sock in sockets:sock.close()

def resolve(root,profile=None,timeout=1.2):
    from org_client import Client
    profile=profile or load_profile(root)
    if not profile:raise ValueError('پیکربندی شبکه شرکت موجود نیست؛ نشانی دستی را انتخاب کنید.')
    certificate=trust_file(root,profile);offers=discover(profile,timeout)
    fallback=dict(url='https://'+profile['preferred_ip']+':'+str(profile['port']),fingerprint=profile['fingerprint'],model=GEMMA_MODEL)
    candidates=offers[:4]+[fallback]
    for candidate in candidates:
        client=Client(candidate['url'],certificate,candidate['fingerprint']);client.timeout=(2,3)
        try:
            status=client.request('status')
            if status.get('initialized') and status.get('secure') and status.get('automatic_network'):
                return dict(candidate,certificate=certificate,identity=profile['fingerprint'])
        except Exception:pass
        finally:client.session.close()
    raise ValueError('میزبان شرکت پیدا نشد؛ روشن‌بودن کامپیوتر میزبان و اتصال به وای‌فای شرکت را بررسی کنید.')
