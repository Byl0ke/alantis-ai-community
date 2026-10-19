# ✦ ALANTIS AI — Community Edition 2.0

**Tu plataforma de inteligencia artificial con usuarios y chats privados.** Proyecto completo con frontend responsive negro/dorado y backend FastAPI. Esta versión está lista para **pruebas locales y un despliegue beta controlado**. La **vista previa pública de Render** está desplegada en [alantis-ai-community.onrender.com](https://alantis-ai-community.onrender.com), con el registro CERRADO y sin un proveedor de IA conectado.

## Qué incluye

- Registro de usuarios e inicio/cierre de sesión con nombre de usuario y contraseña.
- Contraseñas protegidas con **Argon2id** (nunca guardadas en texto plano).
- Cookies de sesión `HttpOnly` y `SameSite=Lax`, token anti-CSRF por sesión, protección de origen y cabeceras de seguridad.
- Cada conversación pertenece a su usuario: acceso ajeno bloqueado en todas las operaciones.
- Chat con streaming de respuesta en tiempo real (Ollama local o API compatible con OpenAI).
- Historial, eliminación de conversaciones y cuota diaria configurable (**20 solicitudes/usuario/día** por defecto).
- Panel admin: cantidad de usuarios/conversaciones/mensajes y suspensión/reactivación de cuentas.
- SQLite **solo en local** o PostgreSQL para almacenamiento persistente en servidor.
- `render.yaml`, Docker, Docker Compose, tests automatizados, script de instalación en Windows.
- Mini laboratorio `labs/train_tiny.py` conservado de v1 para estudiar entrenamiento desde cero (no es el modelo del chat).

## 1. Prueba gratuita en tu PC (Windows)

1. Instala [Python 3.11+](https://www.python.org/downloads/) y [Ollama](https://ollama.com/download).
2. Instala o arranca Ollama, y en PowerShell ejecuta `ollama pull llama3.2:3b`.
3. Descomprime el ZIP y ejecuta **`INICIAR_ALANTIS_AI.bat`**.
4. Abre **http://127.0.0.1:8000** y registra una cuenta con contraseña de al menos 10 caracteres.
5. Prueba los chats. El programa almacena cuentas y chats en `data/alantis_public.db` (no en GitHub).

En macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn backend.app:app --reload`.

**Copia `.env.example` a `.env` si quieres personalizar variables.** Todos los archivos `.env`, las bases de datos y claves están ignorados por Git.

## 2. Configurar la IA para visitantes desde Internet

**Ollama en tu PC no puede responder por arte de magia desde un hosting remoto.** Puedes usar una máquina con GPU y Ollama accessible de forma privada al backend, o contratar un proveedor de API compatible con OpenAI. Ejemplo de entorno del servidor (valores ilustrativos):

```env
ALANTIS_PROVIDER=openai
ALANTIS_API_URL=https://api.openai.com/v1
ALANTIS_MODEL=gpt-4o-mini
ALANTIS_API_KEY=CONFIGURA_LA_CLAVE_PRIVADA_EN_TU_HOSTING
ALANTIS_COOKIE_SECURE=true
ALANTIS_REGISTRATION_OPEN=false
ALANTIS_DAILY_LIMIT=20
DATABASE_URL=postgresql://USUARIO:CLAVE@HOST:5432/BASE
```

**Nunca subas `ALANTIS_API_KEY` al repositorio ni la pongas en el frontend.** Cada petición a un modelo alojado de terceros puede tener coste. Las cuotas básicas de esta edición **no sustituyen** presupuestos/límites de facturación del proveedor.

## 3. Subir a tu GitHub — `Byl0ke/alantis-ai-community`

El repositorio principal es **[Byl0ke/alantis-ai-community](https://github.com/Byl0ke/alantis-ai-community)**. Los archivos del proyecto se administran en la rama `main`. No subas las variables secretas ni bases de datos.

Desde Windows: instala [Git](https://git-scm.com/downloads/win), abre la carpeta descomprimida y ejecuta **`SUBIR_A_GITHUB.bat`**. Requiere iniciar sesión en GitHub cuando Git lo solicite y tener configurada tu identidad Git.

También puedes usar terminal:

```bash
git init
git branch -M main
git remote add origin https://github.com/Byl0ke/alantis-ai-community.git
git add .
git commit -m "feat: ALANTIS AI Community 2.0 beta"
git push -u origin main
```

Repositorio oficial: **https://github.com/Byl0ke/alantis-ai-community**. Se publica el **código**, no la web operativa. GitHub Pages no puede ejecutar el backend Python.

## 4. Estado actual en Render (vista previa gratuita)

- **URL pública:** https://alantis-ai-community.onrender.com
- **Servicio:** https://dashboard.render.com/web/srv-dbbas2s9v7es73ei2510
- **Plan:** web service `free`, región Frankfurt, despliegues automáticos desde la rama `main`.
- **Registro:** CERRADO (`ALANTIS_REGISTRATION_OPEN=false`). No deben registrarse usuarios reales en esta fase.
- **Persistencia:** aún NO hay `DATABASE_URL`; el contenedor usa SQLite temporal, que puede perderse en cualquier redeploy o reinicio.
- **IA:** aún NO hay `ALANTIS_API_KEY`; no se pueden enviar chats al proveedor remoto.
- **Coste:** no se ha contratado PostgreSQL ni ninguna API de pago. La vista previa usa la capacidad incluida en Render Free y sigue sus límites de uso.

**No abras registros públicos** sin una base de datos independiente y persistente, configuración de un proveedor de IA, seguridad/antibots, políticas legales y pruebas de extremo a extremo. Render permite una sola base Postgres `free` por espacio de trabajo (ya hay una para la academia), y además caduca tras 30 días. Por eso aquí no se incluye ningún servicio PostgreSQL en `render.yaml`. Si más adelante utilizas una base de datos de un proveedor externo, introduce la URL como variable privada `DATABASE_URL` únicamente en Render. Las claves nunca van a GitHub. Para disponer de una API de IA compatible, configura `ALANTIS_API_KEY` también como secreto del servicio, tras aceptar sus posibles costes.

La web gratuita puede suspenderse tras inactividad y tardar en despertarse. Consulta las condiciones actuales en [Render Free](https://render.com/docs/free).

## 5. Panel administrador

Crea un usuario normal y promociónalo desde una terminal privada con acceso a la base de datos real (ver paso anterior). Luego actualiza sesión o vuelve a entrar. Verás **Administración** en la barra superior. Ningún usuario puede atribuirse el rol de admin desde el navegador.

## 6. Seguridad y lo que falta para abrir a todo el público

Es una **beta funcional**, no un producto auditado para producción. Antes de activar registros reales:

- Implementar verificación de correo electrónico, recuperación de contraseñas y defensa antibots (por ejemplo, CAPTCHA/Turnstile en registro).
- Publicar una política de privacidad, aviso legal, condiciones de uso y un contacto real del responsable; revisar el RGPD si opera en España/UE.
- Añadir rate limiting distribuido con Redis/WAF, alertas por abuso, límites y presupuesto de API a nivel de proveedor, y supervisión de contenido según el uso.
- Contratar base de datos **persistente**, realizar y verificar copias de seguridad, fijar política de retención y procedimientos para exportación/borrado.
- Configurar observabilidad, monitorizar errores y costes, someter a revisión de seguridad, y configurar migraciones de base de datos (Alembic) antes de cambios de esquema.
- Cambiar contraseñas de ejemplo de `docker-compose.yml` si lo usas fuera de localhost.

**La autenticación actual usa nombres de usuario, no correo**. Por tanto, esta beta no envía emails ni permite recuperar contraseñas automáticamente. El usuario puede borrar su cuenta y sus conversaciones desde **Gestionar mi cuenta** (requiere contraseña), con el endpoint `POST /api/auth/delete-account`.

**V1 → V2:** la base local nueva se llama `alantis_public.db`. Los chats de v1 estaban sin propietario y **no se importan automáticamente**, para no hacerlos públicos por error. Conserva una copia de tu base de v1.

## 7. Pruebas

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

El código prueba registro, hash, sesión, CSRF, privacidad entre usuarios, streaming simulado, cuotas, permisos de admin y borrado de cuentas, sin depender de Ollama ni de servicios de pago.

---
**Proyecto ALANTIS AI · Identidad negro / dorado · Version 2.0 beta**