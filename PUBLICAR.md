# Publicación de ALANTIS AI Community — estado real

**Repositorio:** https://github.com/Byl0ke/alantis-ai-community  
**Web pública:** https://alantis-ai-community.onrender.com  
**Servicio Render:** https://dashboard.render.com/web/srv-dbbas2s9v7es73ei2510

## Publicado

- Código v2 en la rama `main` de GitHub; actualizaciones automáticas de Render habilitadas.
- Servidor FastAPI y frontend alojados en Frankfurt en el plan web **free**.
- Solo **vista previa**: `ALANTIS_REGISTRATION_OPEN=false` y cookies HTTPS.

## Pendiente antes de aceptar usuarios

1. Configurar una base PostgreSQL independiente, PERSISTENTE, y colocar `DATABASE_URL` como variable privada en el servicio. **NO** usar SQLite temporal para usuarios.
2. Elegir un proveedor de modelo de IA, definir `ALANTIS_MODEL` y guardar `ALANTIS_API_KEY` como secreto en Render; estos servicios pueden ser de pago.
3. Añadir protecciones antibots, recuperación de cuentas, límites de abuso, políticas de privacidad/uso (RGPD) y copias de seguridad.
4. Hacer pruebas reales de registro, sesión, chat y conservación de mensajes tras un despliegue nuevo. Solo después plantear `ALANTIS_REGISTRATION_OPEN=true`.

**Importante:** el workspace ya tiene una base PostgreSQL `free` dedicada a ALANTIS AI ACADEMY; Render solo permite una por workspace y caduca a los 30 días. No reutilices esa base para este proyecto ni actives el blueprint antiguo que proponía una base de pago. El `render.yaml` actualizado **no crea bases de datos**.

**Nunca subas** `.env`, claves API, tokens, credenciales, bases de datos o datos de usuarios al repositorio. El servicio se publicará automáticamente al hacer `git push` a `main` cuando Render detecte la actualización.
