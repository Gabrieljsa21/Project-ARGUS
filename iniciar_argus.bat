@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

rem Versao "sem console" - o Argus roda em segundo plano (pythonw), sem janela de
rem terminal nenhuma. A janela do widget nao tem borda nem "X" de proposito -
rem pra fechar, clique com o botao direito no icone do Argus na bandeja do sistema.

start "" /B ".venv\Scripts\pythonw.exe" -m argus.app
