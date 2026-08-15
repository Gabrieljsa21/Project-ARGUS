@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Configuracao do Argus - primeira vez
echo ============================================
echo.

rem Script pensado pra quem nunca abriu um terminal antes - so de duplo clique.
rem SEM acento/emoji em nenhuma linha deste arquivo (nem em comentario rem) de
rem proposito - ja foi o suficiente pra confundir o parser do cmd.exe e quebrar
rem um script assim num teste real (mesma licao do SETUP.bat da GAIA).

set PYTHON_EXE=python

echo [1/4] Verificando se o Python esta instalado...
python --version >nul 2>&1
if errorlevel 1 goto PYTHON_PRECISA_INSTALAR
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo       Encontrado: Python %PYVER%
echo.

for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)
if not "%PYMAJOR%"=="3" goto PYTHON_PRECISA_INSTALAR
if "%PYMINOR%"=="11" goto TEM_PYTHON
if "%PYMINOR%"=="12" goto TEM_PYTHON
if "%PYMINOR%"=="13" goto TEM_PYTHON

:PYTHON_PRECISA_INSTALAR
echo.
echo O Python 3.11, 3.12 ou 3.13 nao foi encontrado neste computador.
echo.
where winget >nul 2>&1
if errorlevel 1 goto PYTHON_SEM_WINGET

echo Instalando o Python 3.12 automaticamente. Pode levar um minuto...
winget install --id Python.Python.3.12 --source winget -e --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto PYTHON_SEM_WINGET

set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_EXE%" goto PYTHON_SEM_WINGET
echo       Python 3.12 instalado com sucesso.
echo.
goto TEM_PYTHON

:PYTHON_SEM_WINGET
echo.
echo ERRO: nao consegui instalar o Python automaticamente neste computador.
echo.
echo Instale o Python manualmente:
echo   1. Acesse https://www.python.org/downloads/
echo   2. IMPORTANTE: na tela de instalacao, marque a caixa
echo      "Add Python to PATH" antes de clicar em Instalar.
echo   3. Depois de instalar, execute este SETUP.bat de novo.
echo.
pause
exit /b 1

:TEM_PYTHON
echo [2/4] Criando o ambiente isolado do Argus (.venv)...
if exist ".venv\Scripts\python.exe" goto VENV_JA_EXISTE
"%PYTHON_EXE%" -m venv .venv
if errorlevel 1 goto ERRO_VENV
echo       Criado com sucesso.
goto VENV_PRONTO

:VENV_JA_EXISTE
echo       Ja existe, pulando esta etapa.
goto VENV_PRONTO

:ERRO_VENV
echo ERRO ao criar o ambiente virtual. Veja a mensagem acima.
pause
exit /b 1

:VENV_PRONTO
echo.

echo [3/4] Instalando as bibliotecas necessarias (pode levar alguns minutos)...
".venv\Scripts\python.exe" -m ensurepip --upgrade --quiet >nul 2>&1
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install --quiet -e .
if errorlevel 1 goto ERRO_PIP
echo       Instalado com sucesso.
echo.
goto PIP_PRONTO

:ERRO_PIP
echo ERRO ao instalar as bibliotecas. Veja a mensagem acima.
pause
exit /b 1

:PIP_PRONTO
echo [4/4] Preparando o arquivo de configuracao (.env)...
if exist ".env" goto ENV_JA_EXISTIA
copy /y ".env.example" ".env" >nul
echo       Criado a partir do modelo.
echo.
goto PRECISA_TOKEN

:ENV_JA_EXISTIA
echo       Arquivo .env ja existe - nao vou sobrescrever suas chaves.
echo.
echo ============================================
echo   Configuracao concluida!
echo ============================================
echo.
echo Agora e so clicar duas vezes em iniciar_argus.bat pra comecar a usar.
echo.
pause
exit /b 0

:PRECISA_TOKEN
echo ============================================
echo   Falta so 1 coisa:
echo ============================================
echo.
echo Voce precisa de um token de API do Jira (seu e-mail + um token,
echo NAO a sua senha). Vou abrir o site pra voce criar o seu, e depois
echo abrir o arquivo .env pra voce colar ele.
echo.
pause

start "" https://id.atlassian.com/manage-profile/security/api-tokens
timeout /t 2 >nul
notepad .env

echo.
echo ============================================
echo   Configuracao concluida!
echo ============================================
echo.
echo Depois de preencher JIRA_EMAIL e JIRA_API_TOKEN e salvar o arquivo,
echo e so clicar duas vezes em iniciar_argus.bat pra comecar a usar.
echo.
echo Dica: de dois cliques em criar_atalho_desktop.vbs pra ganhar um
echo atalho Argus na sua Area de Trabalho.
echo.
pause
