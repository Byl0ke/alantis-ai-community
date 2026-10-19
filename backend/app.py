"""ALANTIS AI Community - public multi-user FastAPI chat (v2).

Security: password hashes (Argon2id), opaque hashed sessions + HttpOnly cookie,
per-session CSRF tokens, ownership checks, basic IP rate limiting, daily quotas,
HTTPS-friendly deployment and server-side model API key handling.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncIterator
from uuid import uuid4

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, delete, func, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
STATIC_DIR = ROOT / 'frontend'
raw_db = os.getenv('DATABASE_URL', '')
if raw_db.startswith('postgres://'):
    raw_db = 'postgresql://' + raw_db[len('postgres://'):]
if not raw_db:
    local_db = Path(os.getenv('ALANTIS_DB', str(ROOT / 'data' / 'alantis_public.db'))).resolve()
    local_db.parent.mkdir(parents=True, exist_ok=True)
    raw_db = 'sqlite:///' + str(local_db)
engine = create_engine(raw_db, pool_pre_ping=True, connect_args={'check_same_thread': False} if raw_db.startswith('sqlite:') else {})
DB = sessionmaker(bind=engine, expire_on_commit=False)

PROVIDER = os.getenv('ALANTIS_PROVIDER', 'ollama').lower()
if PROVIDER not in ('ollama', 'openai'):
    raise RuntimeError('ALANTIS_PROVIDER debe ser ollama u openai')
MODEL = os.getenv('ALANTIS_MODEL', 'llama3.2:3b' if PROVIDER == 'ollama' else 'gpt-4o-mini')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
AI_API_URL = os.getenv('ALANTIS_API_URL', 'https://api.openai.com/v1').rstrip('/')
AI_API_KEY = os.getenv('ALANTIS_API_KEY', '')
IS_SECURE = os.getenv('ALANTIS_COOKIE_SECURE', 'false').lower() == 'true'
ALLOW_REGISTER = os.getenv('ALANTIS_REGISTRATION_OPEN', 'true').lower() == 'true'
DAILY_LIMIT = max(1, int(os.getenv('ALANTIS_DAILY_LIMIT', '20')))
MAX_CHARS = max(100, min(int(os.getenv('ALANTIS_MAX_CHARS', '4000')), 12000))
SESSION_DAYS = 7
COOKIE = 'alantis_session'
DEFAULT_SYSTEM = ('Eres ALANTIS AI, un asistente de inteligencia artificial amable y profesional. '
                  'Responde en el idioma del usuario, con claridad, sin inventar conocimientos ni capacidades.')
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(250))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    quota_day: Mapped[str] = mapped_column(String(10), default='')
    quota_used: Mapped[int] = mapped_column(Integer, default=0)
    conversations: Mapped[list[Conversation]] = relationship(back_populates='owner', cascade='all,delete-orphan')
    sessions: Mapped[list[LoginSession]] = relationship(back_populates='user', cascade='all,delete-orphan')

class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates='sessions')

class Conversation(Base):
    __tablename__ = 'conversations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(120), default='Nueva conversación')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    owner: Mapped[User] = relationship(back_populates='conversations')
    messages: Mapped[list[Message]] = relationship(back_populates='conversation', cascade='all,delete-orphan')

class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    conversation: Mapped[Conversation] = relationship(back_populates='messages')

Base.metadata.create_all(engine)
app = FastAPI(title='ALANTIS AI Community', version='2.0.0', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

# A simple single-process throttle. For serious public traffic use Redis / WAF.
_buckets: dict[str, deque[float]] = defaultdict(deque)
_bucket_lock = threading.Lock()

def throttle(request: Request, action: str, limit: int, seconds: int):
    ip = request.client.host if request.client else 'unknown'
    key = f'{action}:{ip}'
    current = time.monotonic()
    with _bucket_lock:
        queue = _buckets[key]
        while queue and current - queue[0] > seconds:
            queue.popleft()
        if len(queue) >= limit:
            raise HTTPException(429, 'Demasiadas solicitudes. Inténtalo más tarde.')
        queue.append(current)
        # Limit memory growth of idle buckets.
        if len(_buckets) > 10000:
            for k in list(_buckets)[:1000]:
                if not _buckets[k] or current - _buckets[k][-1] > 3600:
                    del _buckets[k]

def get_db():
    with DB() as session:
        yield session

def digest(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def timestamp() -> datetime:
    return datetime.now(timezone.utc)

def send_user(user: User) -> dict:
    day = timestamp().date().isoformat()
    return {'id': user.id, 'username': user.username, 'is_admin': user.is_admin,
            'daily_used': user.quota_used if user.quota_day == day else 0,
            'daily_limit': DAILY_LIMIT}

def session_from_request(req: Request, db: Session) -> tuple[User, LoginSession]:
    token = req.cookies.get(COOKIE, '')
    if not token:
        raise HTTPException(401, 'Inicia sesión para continuar.')
    item = db.get(LoginSession, digest(token))
    if item is None or item.expires_at.replace(tzinfo=timezone.utc) <= timestamp():
        raise HTTPException(401, 'Tu sesión ha caducado. Vuelve a iniciar sesión.')
    user = db.get(User, item.user_id)
    if user is None or user.disabled:
        raise HTTPException(403, 'Tu cuenta no está disponible.')
    return user, item

def csrf_check(req: Request, auth: tuple[User, LoginSession]):
    if not hmac.compare_digest(req.headers.get('X-CSRF-Token', ''), auth[1].csrf):
        raise HTTPException(403, 'Token CSRF inválido. Actualiza la página.')

def authenticate(req: Request, db: Session = Depends(get_db)):
    return session_from_request(req, db)

def origin_check(req: Request):
    # Browsers send Origin for JSON POST. Match it to Host to prevent cross-origin login CSRF.
    origin = req.headers.get('origin')
    if origin:
        from urllib.parse import urlsplit
        host = req.headers.get('host', '')
        parsed = urlsplit(origin)
        if parsed.netloc.lower() != host.lower() or parsed.scheme not in ('http', 'https'):
            raise HTTPException(403, 'Origen no permitido.')

def create_login(response: Response, db: Session, user: User) -> str:
    secret = secrets.token_urlsafe(40)
    csrf = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=digest(secret), user_id=user.id,
                        csrf=csrf, expires_at=timestamp() + timedelta(days=SESSION_DAYS)))
    db.commit()
    response.set_cookie(COOKIE, secret, max_age=SESSION_DAYS * 86400,
                        httponly=True, secure=IS_SECURE, samesite='lax', path='/')
    return csrf

def owned_conversation(db: Session, uid: str, conversation_id: str) -> Conversation:
    c = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.owner_id == uid))
    if c is None:
        raise HTTPException(404, 'Conversación no encontrada.')
    return c

@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if IS_SECURE:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.get('/')
def home():
    return FileResponse(STATIC_DIR / 'index.html')

@app.get('/api/health')
def health():
    return {'app': 'ok', 'provider': PROVIDER, 'model': MODEL}

@app.get('/api/config')
def config():
    return {'registration_open': ALLOW_REGISTER, 'provider': PROVIDER,
            'model': MODEL, 'max_chars': MAX_CHARS}

class AuthBody(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=10, max_length=128)

@app.post('/api/auth/register', status_code=201)
def register(body: AuthBody, request: Request, response: Response, db: Session = Depends(get_db)):
    origin_check(request)
    throttle(request, 'register', 4, 3600)
    if not ALLOW_REGISTER:
        raise HTTPException(403, 'El registro está cerrado por el administrador.')
    name = body.username.strip().lower()
    if not USERNAME_RE.fullmatch(name):
        raise HTTPException(422, 'Usuario: 3 a 32 caracteres, letras, números o guion bajo.')
    if db.scalar(select(User.id).where(User.username == name)):
        raise HTTPException(409, 'Ese nombre de usuario ya está ocupado.')
    user = User(id=str(uuid4()), username=name,
                password_hash=password_hasher.hash(body.password), quota_day='', quota_used=0)
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, 'Ese usuario ya está registrado.')
    return {'user': send_user(user), 'csrf_token': create_login(response, db, user)}

@app.post('/api/auth/login')
def login(body: AuthBody, request: Request, response: Response, db: Session = Depends(get_db)):
    origin_check(request)
    throttle(request, 'login', 8, 300)
    user = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    if not user:
        raise HTTPException(401, 'Usuario o contraseña incorrectos.')
    try:
        password_hasher.verify(user.password_hash, body.password)
    except (VerificationError, InvalidHashError):
        raise HTTPException(401, 'Usuario o contraseña incorrectos.')
    if user.disabled:
        raise HTTPException(403, 'Cuenta deshabilitada.')
    return {'user': send_user(user), 'csrf_token': create_login(response, db, user)}

@app.get('/api/auth/me')
def whoami(request: Request, db: Session = Depends(get_db)):
    try:
        user, item = session_from_request(request, db)
    except HTTPException:
        return {'authenticated': False}
    return {'authenticated': True, 'user': send_user(user), 'csrf_token': item.csrf}

@app.post('/api/auth/logout')
def logout(request: Request, response: Response, db: Session = Depends(get_db), auth=Depends(authenticate)):
    csrf_check(request, auth)
    db.delete(auth[1])
    db.commit()
    response.delete_cookie(COOKIE, path='/')
    return {'ok': True}

class DeleteAccount(BaseModel):
    password: str

@app.post('/api/auth/delete-account')
def delete_account(body: DeleteAccount, request: Request, response: Response,
                   db: Session = Depends(get_db), auth=Depends(authenticate)):
    csrf_check(request, auth)
    user, _ = auth
    try:
        password_hasher.verify(user.password_hash, body.password)
    except (VerificationError, InvalidHashError):
        raise HTTPException(403, 'Contraseña incorrecta.')
    db.delete(user)
    db.commit()
    response.delete_cookie(COOKIE, path='/')
    return {'ok': True}

class NewConversation(BaseModel):
    title: str = Field(default='Nueva conversación', min_length=1, max_length=120)

class RenameConversation(BaseModel):
    title: str = Field(min_length=1, max_length=120)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_CHARS)

@app.get('/api/conversations')
def conversations(db: Session = Depends(get_db), auth=Depends(authenticate)):
    user, _ = auth
    rows = db.scalars(select(Conversation).where(Conversation.owner_id == user.id)
                      .order_by(Conversation.updated_at.desc()).limit(100)).all()
    return [{'id': c.id, 'title': c.title, 'updated_at': c.updated_at.isoformat()} for c in rows]

@app.post('/api/conversations', status_code=201)
def create_conversation(body: NewConversation, request: Request,
                        db: Session = Depends(get_db), auth=Depends(authenticate)):
    csrf_check(request, auth)
    throttle(request, 'newchat', 40, 60)
    uid = auth[0].id
    if (db.scalar(select(func.count(Conversation.id)).where(Conversation.owner_id == uid)) or 0) >= 100:
        raise HTTPException(429, 'Máximo de 100 conversaciones. Borra alguna para continuar.')
    c = Conversation(id=str(uuid4()), owner_id=uid, title=body.title.strip() or 'Nueva conversación')
    db.add(c)
    db.commit()
    return {'id': c.id, 'title': c.title, 'updated_at': c.updated_at.isoformat()}

@app.get('/api/conversations/{conversation_id}')
def read_conversation(conversation_id: str, db: Session = Depends(get_db), auth=Depends(authenticate)):
    c = owned_conversation(db, auth[0].id, conversation_id)
    rows = db.scalars(select(Message).where(Message.conversation_id == c.id).order_by(Message.id)).all()
    return {'id': c.id, 'title': c.title,
            'messages': [{'id': m.id, 'role': m.role, 'content': m.content} for m in rows]}

@app.patch('/api/conversations/{conversation_id}')
def rename_conversation(conversation_id: str, body: RenameConversation, request: Request,
                        db: Session = Depends(get_db), auth=Depends(authenticate)):
    csrf_check(request, auth)
    c = owned_conversation(db, auth[0].id, conversation_id)
    c.title = body.title.strip() or 'Nueva conversación'
    c.updated_at = timestamp()
    db.commit()
    return {'id': c.id, 'title': c.title}

@app.delete('/api/conversations/{conversation_id}', status_code=204)
def remove_conversation(conversation_id: str, request: Request,
                        db: Session = Depends(get_db), auth=Depends(authenticate)):
    csrf_check(request, auth)
    c = owned_conversation(db, auth[0].id, conversation_id)
    db.delete(c)
    db.commit()
    return Response(status_code=204)

async def stream_model(messages: list[dict]) -> AsyncIterator[str]:
    timeout = httpx.Timeout(connect=10, read=100, write=20, pool=10)
    if PROVIDER == 'ollama':
        url = f'{OLLAMA_URL}/api/chat'
        payload = {'model': MODEL, 'messages': messages, 'stream': True,
                   'options': {'num_predict': 1000}}
        headers = {}
    else:
        if not AI_API_KEY:
            raise RuntimeError('Falta ALANTIS_API_KEY en el servidor.')
        url = f'{AI_API_URL}/chat/completions'
        payload = {'model': MODEL, 'messages': messages, 'stream': True, 'max_tokens': 1000}
        headers = {'Authorization': f'Bearer {AI_API_KEY}'}
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream('POST', url, json=payload, headers=headers) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.strip():
                    continue
                if PROVIDER == 'ollama':
                    data = json.loads(line)
                    if data.get('error'):
                        raise RuntimeError('El proveedor de IA devolvió un error.')
                    chunk = data.get('message', {}).get('content', '')
                else:
                    if not line.startswith('data: '):
                        continue
                    raw = line[6:]
                    if raw == '[DONE]':
                        break
                    data = json.loads(raw)
                    chunk = (data.get('choices') or [{}])[0].get('delta', {}).get('content') or ''
                if chunk:
                    yield chunk

def sse(event: dict) -> str:
    return 'data: ' + json.dumps(event, ensure_ascii=False) + '\n\n'

def reserve_quota(db: Session, uid: str) -> tuple[int, int]:
    day = timestamp().date().isoformat()
    db.execute(update(User).where(User.id == uid, User.quota_day != day)
               .values(quota_day=day, quota_used=0))
    db.flush()
    result = db.execute(update(User).where(User.id == uid, User.quota_day == day,
                                           User.quota_used < DAILY_LIMIT)
                        .values(quota_used=User.quota_used + 1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(429, f'Has utilizado tus {DAILY_LIMIT} mensajes de hoy. Vuelve mañana.')
    count = db.scalar(select(User.quota_used).where(User.id == uid))
    db.commit()
    return count, DAILY_LIMIT

@app.post('/api/conversations/{conversation_id}/chat')
async def chat(conversation_id: str, body: ChatRequest, request: Request,
               db: Session = Depends(get_db), auth=Depends(authenticate)):
    csrf_check(request, auth)
    throttle(request, 'chat', 20, 60)
    user = auth[0]
    c = owned_conversation(db, user.id, conversation_id)
    message = body.message.strip()
    if not message:
        raise HTTPException(422, 'Mensaje vacío.')
    if not MODEL or (PROVIDER == 'openai' and not AI_API_KEY):
        raise HTTPException(503, 'El administrador aún no ha configurado el modelo de IA.')
    prior = list(reversed(db.scalars(select(Message).where(Message.conversation_id == c.id)
                                     .order_by(Message.id.desc()).limit(20)).all()))
    used, limit = reserve_quota(db, user.id)
    db.add(Message(conversation_id=c.id, role='user', content=message))
    if c.title == 'Nueva conversación':
        c.title = message[:56] + ('…' if len(message) > 56 else '')
    c.updated_at = timestamp()
    db.commit()
    messages = [{'role': 'system', 'content': DEFAULT_SYSTEM}]
    messages += [{'role': m.role, 'content': m.content} for m in prior]
    messages.append({'role': 'user', 'content': message})

    async def generate():
        result = []
        try:
            async for part in stream_model(messages):
                result.append(part)
                yield sse({'type': 'delta', 'text': part})
            answer = ''.join(result).strip()
            if not answer:
                with DB() as refund_db:
                    refund_db.execute(update(User).where(User.id == user.id, User.quota_day == timestamp().date().isoformat(), User.quota_used > 0).values(quota_used=User.quota_used - 1))
                    refund_db.commit()
                yield sse({'type': 'error', 'error': 'El modelo no generó respuesta.'})
                return
            with DB() as save_db:
                owned_conversation(save_db, user.id, conversation_id)
                save_db.add(Message(conversation_id=conversation_id, role='assistant', content=answer[:50000]))
                save_db.execute(update(Conversation).where(Conversation.id == conversation_id)
                                .values(updated_at=timestamp()))
                save_db.commit()
            yield sse({'type': 'done', 'used': used, 'limit': limit})
        except (httpx.HTTPError, ValueError, RuntimeError):
            if not result:
                with DB() as refund_db:
                    refund_db.execute(update(User).where(User.id == user.id, User.quota_day == timestamp().date().isoformat(), User.quota_used > 0).values(quota_used=User.quota_used - 1))
                    refund_db.commit()
            yield sse({'type': 'error', 'error': 'El proveedor de IA no responde. Inténtalo de nuevo más tarde.'})
    return StreamingResponse(generate(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

@app.get('/api/admin/stats')
def admin_stats(db: Session = Depends(get_db), auth=Depends(authenticate)):
    if not auth[0].is_admin:
        raise HTTPException(403, 'Solo administradores.')
    return {'users': db.scalar(select(func.count(User.id))),
            'conversations': db.scalar(select(func.count(Conversation.id))),
            'messages': db.scalar(select(func.count(Message.id))),
            'requests_today': db.scalar(select(func.sum(User.quota_used)).where(User.quota_day == timestamp().date().isoformat())) or 0}

@app.get('/api/admin/users')
def admin_users(db: Session = Depends(get_db), auth=Depends(authenticate)):
    if not auth[0].is_admin:
        raise HTTPException(403, 'Solo administradores.')
    users = db.scalars(select(User).order_by(User.created_at.desc()).limit(100)).all()
    return [{'id': u.id, 'username': u.username, 'disabled': u.disabled,
             'is_admin': u.is_admin, 'created_at': u.created_at.isoformat()} for u in users]

class UserStatus(BaseModel):
    disabled: bool

@app.patch('/api/admin/users/{user_id}')
def admin_change_user(user_id: str, body: UserStatus, request: Request,
                      db: Session = Depends(get_db), auth=Depends(authenticate)):
    csrf_check(request, auth)
    if not auth[0].is_admin:
        raise HTTPException(403, 'Solo administradores.')
    if user_id == auth[0].id:
        raise HTTPException(403, 'No puedes suspender tu propia cuenta.')
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, 'Usuario no encontrado.')
    if user.is_admin:
        raise HTTPException(403, 'No se pueden modificar otras cuentas administradoras.')
    user.disabled = body.disabled
    db.commit()
    return {'ok': True}