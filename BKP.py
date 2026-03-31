import pyautogui
import time
import subprocess
import pyperclip
from datetime import datetime, timedelta

# Segurança
pyautogui.FAILSAFE = True

# ========= CONFIG =========
URL_SOFIT = "https://sofitview.com.br/#/client/reports/1841"
CAMINHO_MULTAS = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Multas.xlsx"
CAMINHO_CIOT = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\Ciot.xls"
CAMINHO_MANIFESTOS = r"C:\Users\User\Desktop\Bot\bot_vipe_transportes\Relatórios\manifestos.xls"
# ==========================


# =========================
# FUNÇÕES BASE
# =========================
def wait(t=1):
    time.sleep(t)


def write(text):
    pyautogui.write(text, interval=0.05)


def press(key):
    pyautogui.press(key)


def colar(texto):
    pyperclip.copy(texto)
    pyautogui.hotkey('ctrl', 'v')


def limpar_campo():
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('backspace')


def abrir_chrome(url):
    subprocess.Popen(f'start chrome "{url}"', shell=True)


def press_tabs(qtd):
    for _ in range(qtd):
        pyautogui.press("tab")
        time.sleep(0.2)


def fechar_abas(qtd):
    for _ in range(qtd):
        pyautogui.hotkey("ctrl", "w")
        time.sleep(0.5)


# =========================
# BOT 1 - MULTAS
# =========================
def bot_multas():
    print("🚀 Iniciando BOT MULTAS...")

    abrir_chrome(URL_SOFIT)
    wait(5)

    press_tabs(9)
    press("enter")

    wait(5)

    colar(CAMINHO_MULTAS)
    wait(1)

    press("enter")
    press("tab")
    wait(1)
    press("enter")

    wait(3)

    fechar_abas(3)

    print("✅ BOT MULTAS finalizado!")


# =========================
# BOT 2 - CIOT
# =========================
def bot_ciot():
    print("🚀 Iniciando BOT CIOT...")

    abrir_chrome("https://44.aleff.com.br/Login/Index")
    wait(5)

    write("44")
    press('tab')

    write("117.057.066-65")
    press('tab')

    write("635241@Ab")
    press('tab')

    press('enter')
    wait(5)

    abrir_chrome("https://44.aleff.com.br/RGCiotCartaFreteEmitidos/RGCiotCartaFreteEmitidos")
    wait(5)

    data_inicio = (datetime.today() - timedelta(days=31)).strftime("%d/%m/%Y")
    data_fim = datetime.today().strftime("%d/%m/%Y")

    colar(data_inicio)
    press('tab')
    colar(data_fim)

    press_tabs(14)
    press('enter')

    wait(10)

    abrir_chrome("https://44.aleff.com.br/MonitorRelatorio/MonitorRelatorio")
    wait(5)

    press_tabs(17)
    press('enter')

    wait(5)

    limpar_campo()
    colar(CAMINHO_CIOT)

    press('enter')
    press('tab')
    press('enter')

    wait(3)

    fechar_abas(5)

    print("✅ BOT CIOT finalizado!")


# =========================
# BOT 3 - MANIFESTOS
# =========================
def bot_manifestos():
    print("🚀 Iniciando BOT Manifestos...")

    URL_1 = "https://44.aleff.com.br/RelatGestaoEntregaII/RelatGestaoEntregaII"
    URL_2 = "https://44.aleff.com.br/MonitorRelatorio/MonitorRelatorio"

    hoje = datetime.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_mes = primeiro_dia_mes_atual - timedelta(days=1)

    data_inicio = ultimo_mes.replace(day=1).strftime("%d/%m/%Y")
    data_fim = hoje.strftime("%d/%m/%Y")

    print("Data início:", data_inicio)
    print("Data fim:", data_fim)
    abrir_chrome("https://44.aleff.com.br/Login/Index")
    wait(5)

    write("44")
    press('tab')

    write("117.057.066-65")
    press('tab')

    write("635241@Ab")
    press('tab')

    press('enter')
    wait(5)
    abrir_chrome(URL_1)
    wait(7)

    colar(data_inicio)
    press('tab')
    colar(data_fim)

    press_tabs(2)
    press('delete')

    press_tabs(6)
    press('enter')

    wait(5)

    abrir_chrome(URL_2)
    wait(7)

    press_tabs(17)
    press('enter')

    wait(5)

    #limpar_campo()
    colar(CAMINHO_MANIFESTOS)

    press('enter')
    press('tab')
    press('enter')

    wait(3)

    fechar_abas(3)

    print("✅ BOT Manifestos finalizado!")


# =========================
# LOOP PRINCIPAL
# =========================
while True:
    print("\n==============================")
    print("🤖 INICIANDO CICLO COMPLETO")
    print("==============================\n")

    bot_multas()
    wait(5)

    bot_manifestos()
    wait(5)
    
    
    bot_ciot()
    wait(5)

    pyautogui.hotkey("alt", "f4")

    print("\n⏳ Aguardando 30 minutos...")
    time.sleep(60 * 30)