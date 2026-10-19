"""Promote an EXISTING registered user. Run only in private server shell."""
import sys
from sqlalchemy import select
from backend.app import DB, User

if len(sys.argv) != 3 or sys.argv[1] != 'promote-admin':
    print('Uso: python -m backend.manage promote-admin NOMBRE_USUARIO')
    sys.exit(2)
with DB() as db:
    u = db.scalar(select(User).where(User.username == sys.argv[2].strip().lower()))
    if u is None:
        raise SystemExit('Primero registra ese usuario desde la web.')
    u.is_admin = True
    db.commit()
    print(f'Cuenta {u.username} promovida a administrador.')