"""Password-encrypted, user-scoped snapshots; no password or session is saved."""
import hashlib,json,os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class OfflineCache:
    MAGIC=b'KARNAME-CACHE-1\0'
    def __init__(self,folder,url,username,password):
        identity=(url.rstrip('/')+'\n'+username.strip().casefold()).encode();self.aad=identity;self.path=Path(folder)/(hashlib.sha256(identity).hexdigest()+'.cache');self.path.parent.mkdir(parents=True,exist_ok=True);self.salt=os.urandom(16)
        if self.path.exists():
            header=self.path.read_bytes()[:len(self.MAGIC)+16]
            if header.startswith(self.MAGIC):self.salt=header[len(self.MAGIC):]
        self.key=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),self.salt,350000,32)
    def save(self,snapshot):
        nonce=os.urandom(12);data=json.dumps(snapshot,ensure_ascii=False).encode();encrypted=AESGCM(self.key).encrypt(nonce,data,self.aad);temp=self.path.with_suffix('.tmp');temp.write_bytes(self.MAGIC+self.salt+nonce+encrypted);os.replace(temp,self.path)
    def load(self):
        raw=self.path.read_bytes();start=len(self.MAGIC)
        if not raw.startswith(self.MAGIC) or len(raw)<start+44:raise ValueError('نسخه آفلاین معتبر نیست.')
        try:return json.loads(AESGCM(self.key).decrypt(raw[start+16:start+28],raw[start+28:],self.aad))
        except Exception as exc:raise ValueError('نسخه آفلاین با این نام کاربری و رمز باز نمی‌شود.') from exc
