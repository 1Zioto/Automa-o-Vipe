@echo off
title Vipe Transportes — Bot WhatsApp
color 0A

echo.
echo  ============================================
echo   VIPE TRANSPORTES — BOT WHATSAPP
echo  ============================================
echo.

cd /d "C:\Users\User\Desktop\Bot\bot_vipe_transportes\bot_whatsapp"

echo  Verificando dependencias Node.js...
if not exist "node_modules" (
    echo  Instalando dependencias pela primeira vez...
    npm install
    echo  Instalacao concluida!
    echo.
)

echo  Iniciando Bot WhatsApp...
echo.
node main.js

pause
