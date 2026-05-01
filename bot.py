import telebot
import os
import time
import json
import re
import requests
from playwright.sync_api import sync_playwright

TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Configuración
SESSION_FILE = "patria_session.json"
URL_SESION = "https://raw.githubusercontent.com/cuarentaroleplay-dev/patria-bot/main/patria_session.json"

def descargar_sesion():
    """Descarga el archivo de sesión"""
    try:
        print(f"Descargando de: {URL_SESION}")
        response = requests.get(URL_SESION, timeout=10)
        if response.status_code == 200:
            with open(SESSION_FILE, "w") as f:
                f.write(response.text)
            print("✅ Sesión descargada")
            
            # Verificar que se guardó bien
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                print(f"Cookies encontradas: {len(data.get('cookies', []))}")
            return True
        else:
            print(f"Error {response.status_code}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def sesion_activa():
    """Verifica si hay sesión"""
    if not os.path.exists(SESSION_FILE):
        return False
    try:
        with open(SESSION_FILE, 'r') as f:
            data = json.load(f)
            return len(data.get('cookies', [])) > 0
    except:
        return False

def consultar_patria(cedula):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(storage_state=SESSION_FILE)
            page = context.new_page()
            
            page.goto("https://persona.patria.org.ve/monedero/pagos/registrar")
            page.wait_for_load_state("networkidle")
            
            # Seleccionar monedero
            page.click('input[type="text"][value="Selecciona el Monedero Destino"]')
            time.sleep(0.3)
            page.click('//span[contains(text(), "Monedero Bolívar Digital (Bs)")]')
            time.sleep(0.3)
            
            # Seleccionar tipo cédula
            page.click('#select2-form_transfer_destination_type_select-container')
            time.sleep(0.3)
            page.locator('.select2-search__field').fill('cedula')
            time.sleep(0.3)
            page.click('//li[contains(text(), "Otro (Cédula)")]')
            time.sleep(0.3)
            
            # Descripción
            page.fill('#form_transfer_description', "consulta")
            time.sleep(0.2)
            
            # Consultar
            page.fill('#form_transfer_identification', cedula)
            page.click('#continue')
            time.sleep(2)
            
            # Resultado
            if page.locator('div:has-text("La persona no esta registrada")').count() > 0:
                return "❌ NO REGISTRADA"
            else:
                return "✅ REGISTRADA"
                
    except Exception as e:
        return f"⚠️ Error: {str(e)[:50]}"

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🤖 Bot de Consulta Patria\n\n/buscar V12345678")

@bot.message_handler(commands=['estado'])
def estado(message):
    if sesion_activa():
        bot.reply_to(message, "✅ SESION ACTIVA - Puedes consultar")
    else:
        bot.reply_to(message, "⚠️ Descargando sesión...")
        if descargar_sesion():
            bot.reply_to(message, "✅ SESION DESCARGADA - Ahora puedes consultar")
        else:
            bot.reply_to(message, "❌ Error: No se pudo descargar la sesión")

@bot.message_handler(commands=['buscar'])
def buscar(message):
    try:
        partes = message.text.split()
        if len(partes) < 2:
            bot.reply_to(message, "Uso: /buscar V12345678")
            return
        
        cedula = partes[1].upper()
        if cedula[0] not in 'VE':
            cedula = 'V' + cedula
        
        # Asegurar sesión
        if not sesion_activa():
            if not descargar_sesion():
                bot.reply_to(message, "❌ No hay sesión activa")
                return
        
        msg = bot.reply_to(message, f"🔍 Consultando {cedula}...")
        resultado = consultar_patria(cedula)
        bot.edit_message_text(f"{cedula}: {resultado}", message.chat.id, msg.message_id)
        
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['ayuda'])
def ayuda(message):
    bot.reply_to(message, "Comandos:\n/buscar V12345678\n/estado")

if __name__ == "__main__":
    print("Iniciando bot...")
    descargar_sesion()
    print(f"Sesión activa: {sesion_activa()}")
    bot.infinity_polling()
