@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ==============================================
echo  ALANTIS AI Community - Publicacion GitHub
echo ==============================================
echo.
where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: Primero instala Git para Windows: https://git-scm.com/downloads/win
  pause
  exit /b 1
)
echo Antes de continuar, crea un repositorio VACIO en:
echo https://github.com/new?name=alantis-ai-community
echo Nombre: Byl0ke/alantis-ai-community
echo No anadas README, gitignore ni licencia al crearlo.
echo.
choice /M "Has creado el repositorio vacio en tu cuenta Byl0ke"
if errorlevel 2 exit /b 1
if not exist ".git" (
  git init
  if errorlevel 1 goto :failed
  git branch -M main
  if errorlevel 1 goto :failed
)
git remote get-url origin >nul 2>nul
if errorlevel 1 (
  git remote add origin https://github.com/Byl0ke/alantis-ai-community.git
  if errorlevel 1 goto :failed
) else (
  git remote get-url origin | findstr /I /C:"github.com/Byl0ke/alantis-ai-community" >nul
  if errorlevel 1 (
    echo ERROR: Ya existe un remote 'origin' diferente. No lo modifico.
    pause
    exit /b 1
  )
)
git add .
if errorlevel 1 goto :failed
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "feat: ALANTIS AI Community 2.0 beta"
  if errorlevel 1 (
    echo ERROR: Comprueba que hayas configurado git user.name y user.email.
    goto :failed
  )
)
git push -u origin main
if errorlevel 1 goto :failed
echo.
echo OK: repositorio actualizado: https://github.com/Byl0ke/alantis-ai-community
pause
exit /b 0
:failed
echo.
echo No se ha confirmado la subida. Lee el error que aparece arriba.
pause
exit /b 1