"""Public multi-user API tests; no Ollama, paid model, or external network needed."""
import importlib
from fastapi.testclient import TestClient
from sqlalchemy import select


def client_for(tmp_path, monkeypatch, limit=20):
    monkeypatch.setenv('ALANTIS_DB', str(tmp_path / 'public.sqlite'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('ALANTIS_PROVIDER', 'ollama')
    monkeypatch.setenv('ALANTIS_DAILY_LIMIT', str(limit))
    monkeypatch.setenv('ALANTIS_COOKIE_SECURE', 'false')
    module = importlib.reload(importlib.import_module('backend.app'))
    return TestClient(module.app), module


def signup(client, username='testuser', password='LongPassword!2026'):
    response = client.post('/api/auth/register', json={'username': username, 'password': password})
    assert response.status_code == 201, response.text
    assert 'httponly' in response.headers['set-cookie'].lower()
    return response.json()


def auth(client, csrf):
    return {'X-CSRF-Token': csrf}


def test_auth_and_password_protection(tmp_path, monkeypatch):
    client, module = client_for(tmp_path, monkeypatch)
    assert client.get('/').status_code == 200
    assert client.get('/api/conversations').status_code == 401
    registered = signup(client)
    csrf = registered['csrf_token']
    assert client.get('/api/auth/me').json()['authenticated']
    with module.DB() as db:
        u = db.scalar(select(module.User).where(module.User.username == 'testuser'))
        assert u.password_hash != 'LongPassword!2026'
        assert u.password_hash.startswith('$argon2id$')
    assert client.post('/api/conversations', json={}).status_code == 403
    created = client.post('/api/conversations', json={}, headers=auth(client, csrf))
    assert created.status_code == 201
    assert client.post('/api/auth/logout', headers=auth(client, csrf)).status_code == 200
    assert client.get('/api/conversations').status_code == 401
    wrong = client.post('/api/auth/login', json={'username':'testuser','password':'WrongPassword21'})
    assert wrong.status_code == 401
    login = client.post('/api/auth/login', json={'username':'testuser','password':'LongPassword!2026'})
    assert login.status_code == 200
    assert login.json()['csrf_token']


def test_chat_privacy_and_streaming(tmp_path, monkeypatch):
    client, module = client_for(tmp_path, monkeypatch)
    alice = signup(client, 'alice2026')
    csrf_a = alice['csrf_token']
    c = client.post('/api/conversations', json={}, headers=auth(client,csrf_a)).json()['id']
    async def fake_model(messages):
        assert messages[-1]['content'] == 'Hola'
        yield 'Hola '
        yield 'desde ALANTIS.'
    monkeypatch.setattr(module, 'stream_model', fake_model)
    response = client.post(f'/api/conversations/{c}/chat', json={'message':'Hola'}, headers=auth(client,csrf_a))
    assert response.status_code == 200, response.text
    assert '"type": "done"' in response.text
    messages = client.get(f'/api/conversations/{c}').json()['messages']
    assert [m['role'] for m in messages] == ['user','assistant']
    assert messages[-1]['content'] == 'Hola desde ALANTIS.'

    # Another user cannot list, read, edit, delete or chat in Alice's conversation.
    bob = TestClient(module.app)
    csrf_b = signup(bob, 'bob2026')['csrf_token']
    assert bob.get('/api/conversations').json() == []
    assert bob.get(f'/api/conversations/{c}').status_code == 404
    assert bob.patch(f'/api/conversations/{c}', json={'title':'hacked'}, headers=auth(bob,csrf_b)).status_code == 404
    assert bob.delete(f'/api/conversations/{c}', headers=auth(bob,csrf_b)).status_code == 404
    assert bob.post(f'/api/conversations/{c}/chat', json={'message':'HOLA'},headers=auth(bob,csrf_b)).status_code == 404
    assert client.get(f'/api/conversations/{c}').status_code == 200


def test_daily_quota_and_input_validation(tmp_path, monkeypatch):
    client, module = client_for(tmp_path, monkeypatch, limit=2)
    csrf = signup(client)['csrf_token']
    c = client.post('/api/conversations', json={}, headers=auth(client,csrf)).json()['id']
    async def fake_model(messages):
        yield 'Recibido'
    monkeypatch.setattr(module, 'stream_model', fake_model)
    assert client.post(f'/api/conversations/{c}/chat', json={'message':'  '}, headers=auth(client,csrf)).status_code == 422
    for i in range(2):
        r=client.post(f'/api/conversations/{c}/chat', json={'message':f'Pregunta {i}'}, headers=auth(client,csrf))
        assert r.status_code == 200 and '"type": "done"' in r.text
    assert client.get('/api/auth/me').json()['user']['daily_used']==2
    blocked = client.post(f'/api/conversations/{c}/chat', json={'message':'Tercero'},headers=auth(client,csrf))
    assert blocked.status_code == 429


def test_admin_controls_and_account_deletion(tmp_path,monkeypatch):
    client, module = client_for(tmp_path, monkeypatch)
    admin_csrf=signup(client, 'adminuser')['csrf_token']
    user_client=TestClient(module.app)
    user_csrf=signup(user_client, 'ordinary')['csrf_token']
    assert client.get('/api/admin/stats').status_code == 403
    with module.DB() as db:
        u = db.scalar(select(module.User).where(module.User.username=='adminuser'))
        u.is_admin=True
        db.commit()
    assert client.get('/api/admin/stats').json()['users'] == 2
    u = next(x for x in client.get('/api/admin/users').json() if x['username'] == 'ordinary')
    response = client.patch(f"/api/admin/users/{u['id']}",json={'disabled':True},headers=auth(client,admin_csrf))
    assert response.status_code==200
    assert user_client.get('/api/conversations').status_code==403
    client.patch(f"/api/admin/users/{u['id']}", json={'disabled':False}, headers=auth(client,admin_csrf))
    assert user_client.get('/api/conversations').status_code==200
    assert user_client.post('/api/auth/delete-account',json={'password':'LongPassword!2026'},headers=auth(user_client,user_csrf)).status_code==200
    assert user_client.get('/api/conversations').status_code==401
    assert client.get('/api/admin/stats').json()['users']==1


def test_origin_protection(tmp_path, monkeypatch):
    client,_ = client_for(tmp_path, monkeypatch)
    resp=client.post('/api/auth/register',headers={'Origin':'https://attacker.example'},json={'username':'attacktest','password':'LongPassword!2026'})
    assert resp.status_code==403