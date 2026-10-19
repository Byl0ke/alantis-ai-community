# Publicar ALANTIS AI Community

**Proyecto:** `Byl0ke/alantis-ai-community`  
**Repositorio:** https://github.com/Byl0ke/alantis-ai-community

1. Crea un repositorio **vacío** desde https://github.com/new?name=alantis-ai-community, con propietario **Byl0ke**. No marques README, gitignore ni licencia.
2. En Windows, instala Git si aún no lo tienes y ejecuta `SUBIR_A_GITHUB.bat` desde la carpeta descomprimida. Si te pide autorización, usa el inicio de sesión de GitHub; nunca pegues una contraseña o token en el código.
3. Comprueba en GitHub que aparecen `backend/`, `frontend/`, `render.yaml` y `README.md`. Los cambios posteriores deben enviarse a `main` con `git add`, `git commit` y `git push`.
4. Para alojar el backend: entra a https://dashboard.render.com/, conecta GitHub y elige **New → Blueprint**, seleccionando este repositorio. **Revisa la factura y el plan de PostgreSQL antes de confirmar**: `render.yaml` incluye un PostgreSQL persistente de pago. Configura `ALANTIS_API_KEY` únicamente como variable privada en Render.
5. La URL `*.onrender.com` será la web pública **solo cuando Render confirme un despliegue correcto**. Deja `ALANTIS_REGISTRATION_OPEN=false` hasta completar medidas de seguridad, privacidad y pruebas con la API real.

**No subir:** `.env`, claves API, credenciales, bases de datos SQLite, datos personales, registros privados. El proyecto ya ignora estos archivos cuando se usa Git correctamente.

**Importante:** GitHub almacena el código; no ejecuta tu aplicación FastAPI con usuarios. Sin backend desplegado, base de datos persistente y modelo IA conectado, el sitio no atenderá conversaciones públicas.