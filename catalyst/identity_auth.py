import hashlib, secrets, time, json, os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode
import httpx
from .security import Principal, PolicyEngine

# Backwards-compatible default hash. Prefer setting CATALYST_ADMIN_PASSWORD_SHA256
# in the environment so the password hash is not hard-coded in the repo.
DEFAULT_ADMIN_PASSWORD_SHA256 = "2275db01ef5a425f62b4cadaa7bdf2e978cdcf52420a750381e4508ef52f2eaf"
# Compatibility export retained for integrations that imported the old name.
ADMIN_PASSWORD_SHA256 = DEFAULT_ADMIN_PASSWORD_SHA256

@dataclass(frozen=True)
class AuthResult:
    authenticated: bool
    principal: Principal
    reason: str=''

class IdentityAuthority:
    """Auditable web identity for self-hosted Catalyst.

    Supports API tokens, a Google OAuth sign-in when configured, and a
    creator/admin unlock. The creator password is never stored in plaintext.
    """
    def __init__(self, settings, policy:PolicyEngine):
        self.settings=settings; self.policy=policy
        self.tokens={}
        raw=getattr(settings,'api_tokens',{}) or {}
        if isinstance(raw,dict): self.tokens={str(k):str(v) for k,v in raw.items() if k and v in policy.ROLE_CAPS}
        legacy=getattr(settings,'api_token','')
        if legacy: self.tokens[legacy]='creator'
        self.sessions={}
        self.google_states={}
        # Admin unlock brute-force protections (in-memory; fine for personal single-instance)
        self._admin_unlock_failures={}  # key -> {count:int, window_start:float, locked_until:float}

        # Local user auth (personal / small deployments)
        self._users_path = getattr(settings, 'users_path', '') or os.getenv('CATALYST_USERS_PATH', 'catalyst_data/users.json')
        self._users = self._load_users()

    def _load_users(self):
        path=self._users_path
        try:
            if path and os.path.exists(path):
                with open(path,'r',encoding='utf-8') as f:
                    raw=json.load(f)
                    if isinstance(raw, dict):
                        return raw
        except Exception:
            pass
        return {'users':{}}

    def _save_users(self):
        path=self._users_path
        if not path:
            return
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path,'w',encoding='utf-8') as f:
            json.dump(self._users,f,indent=2)
        try:
            os.chmod(path,0o600)
        except OSError:
            pass

    @staticmethod
    def _pbkdf2(password: str, salt_hex: str, rounds: int = 200_000) -> str:
        salt=bytes.fromhex(salt_hex)
        dk=hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), salt, rounds)
        return dk.hex()

    def create_local_user(self, username: str, password: str):
        username=(username or '').strip()[:64]
        if not username:
            raise ValueError('username is required')
        if username in self._users.get('users', {}):
            raise ValueError('username already exists')
        salt=secrets.token_hex(16)
        pwd_hash=self._pbkdf2(password or '', salt)
        self._users.setdefault('users', {})[username]={
            'salt': salt,
            'hash': pwd_hash,
            'created_at': time.time(),
            'admin': False,
        }
        self._save_users()
        return {'username': username}

    def authenticate_local_user(self, username: str, password: str):
        username=(username or '').strip()[:64]
        row=(self._users.get('users', {}) or {}).get(username)
        if not row:
            return None
        expected=str(row.get('hash',''))
        salt=str(row.get('salt',''))
        if not expected or not salt:
            return None
        digest=self._pbkdf2(password or '', salt)
        if not secrets.compare_digest(digest, expected):
            return None
        # role is guest by default; admin unlock upgrades within the session
        token=secrets.token_urlsafe(48)
        self.sessions[token]={'subject':username,'role':'guest','admin':False,'expires_at':time.time()+86400}
        return token

    def authenticate(self, token:Optional[str], claimed_subject='creator') -> AuthResult:
        token=token or ''
        for candidate,role in self.tokens.items():
            if secrets.compare_digest(token,candidate):
                safe_subject=claimed_subject[:120] if claimed_subject else 'creator'
                return AuthResult(True,Principal(subject=safe_subject,role=role))
        if token:
            session=self.sessions.get(token)
            if session and session['expires_at'] > time.time():
                return AuthResult(True,Principal(subject=session['subject'],role=session['role']))
            if session: self.sessions.pop(token,None)
        return AuthResult(False,Principal(subject='anonymous',role='guest'),'invalid credentials')

    def require_admin(self, token):
        session=self.sessions.get(token or '')
        return bool(session and session.get('role')=='creator' and session.get('admin') and session['expires_at'] > time.time())

    def unlock_admin(self, password:str, subject='creator'):
        now=time.time()
        key=(subject or 'creator')[:120]
        guard=self._admin_unlock_failures.get(key) or {'count':0,'window_start':now,'locked_until':0.0}
        if guard.get('locked_until',0.0) > now:
            return None

        window=getattr(self.settings,'admin_unlock_window_seconds',900)
        max_attempts=getattr(self.settings,'admin_unlock_max_attempts',5)
        lockout=getattr(self.settings,'admin_unlock_lockout_seconds',900)

        # reset window
        if now - guard.get('window_start',now) > window:
            guard={'count':0,'window_start':now,'locked_until':0.0}

        digest=hashlib.sha256((password or '').encode('utf-8')).hexdigest()
        expected=getattr(self.settings,'admin_password_sha256','') or DEFAULT_ADMIN_PASSWORD_SHA256
        if not secrets.compare_digest(digest, expected):
            guard['count']=int(guard.get('count',0))+1
            if guard['count'] >= max_attempts:
                guard['locked_until']=now+lockout
            self._admin_unlock_failures[key]=guard
            return None

        # success -> clear failures
        self._admin_unlock_failures.pop(key,None)
        token=secrets.token_urlsafe(48)
        self.sessions[token]={'subject':subject[:120] or 'creator','role':'creator','admin':True,'expires_at':time.time()+getattr(self.settings,'admin_session_ttl',43200)}
        return token

    def create_google_session(self, subject, email, name):
        token=secrets.token_urlsafe(48)
        display=(name or email or subject or 'Creator')[:120]
        self.sessions[token]={'subject':display,'email':(email or '')[:200],'role':'guest','admin':False,'expires_at':time.time()+86400}
        return token

    def start_google(self, redirect_uri):
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise ValueError('Google sign-in is not configured. Set CATALYST_GOOGLE_CLIENT_ID and CATALYST_GOOGLE_CLIENT_SECRET.')
        state=secrets.token_urlsafe(32); self.google_states[state]={'expires_at':time.time()+600,'redirect_uri':redirect_uri}
        params={'client_id':self.settings.google_client_id,'redirect_uri':redirect_uri,'response_type':'code','scope':'openid email profile','state':state,'access_type':'online','prompt':'select_account'}
        return 'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params)

    def consume_google_callback(self, code, state):
        row=self.google_states.pop(state,None)
        if not row or row['expires_at'] <= time.time(): raise ValueError('Google sign-in state expired or invalid.')
        with httpx.Client(timeout=20) as client:
            token=client.post('https://oauth2.googleapis.com/token',data={'code':code,'client_id':self.settings.google_client_id,'client_secret':self.settings.google_client_secret,'redirect_uri':row['redirect_uri'],'grant_type':'authorization_code'})
            token.raise_for_status(); access=token.json().get('access_token')
            if not access: raise ValueError('Google did not return an access token.')
            profile=client.get('https://openidconnect.googleapis.com/v1/userinfo',headers={'Authorization':f'Bearer {access}'})
            profile.raise_for_status(); data=profile.json()
        email=str(data.get('email','')); domain=getattr(self.settings,'google_allowed_domain','')
        if domain and email.lower().split('@')[-1] != domain.lower().lstrip('@'): raise ValueError('This Google account is outside the configured domain.')
        return self.create_google_session(str(data.get('sub','')),email,str(data.get('name','') or data.get('given_name','')) )

    def logout(self, token):
        if token: self.sessions.pop(token,None)

    def describe(self):
        return {'enabled':bool(self.tokens),'roles':sorted(set(self.tokens.values())),'token_count':len(self.tokens),'google_configured':bool(self.settings.google_client_id and self.settings.google_client_secret),'admin_unlock_available':True}
