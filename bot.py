import telebot
import os
import time
import json
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ===== CONFIGURACIÓN =====
ARCHIVO_SESION = "patria_session.json"
URL_SESION = "https://raw.githubusercontent.com/cuarentaroleplay-dev/patria-bot/main/patria_session.json"

def descargar_sesion():
    try:
        response = requests.get(URL_SESION)
        if response.status_code == 200:
            with open(ARCHIVO_SESION, "w") as f:
                f.write(response.text)
            return True
        return False
    except:
        return False

def sesion_activa():
    return os.path.exists(ARCHIVO_SESION)

def consultar_patria(cedula):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(storage_state=ARCHIVO_SESION)
            page = context.new_page()
            
            page.goto("https://persona.patria.org.ve/monedero/pagos/registrar")
            page.wait_for_load_state("networkidle")
            
            page.click('input[type="text"][value="Selecciona el Monedero Destino"]')
            time.sleep(0.3)
            page.click('//span[contains(text(), "Monedero Bolívar Digital (Bs)")]')
            time.sleep(0.3)
            page.click('#select2-form_transfer_destination_type_select-container')
            time.sleep(0.3)
            page.locator('.select2-search__field').fill('cedula')
            time.sleep(0.3)
            page.click('//li[contains(text(), "Otro (Cédula)")]')
            time.sleep(0.3)
            page.fill('#form_transfer_description', "consulta")
            time.sleep(0.2)
            
            page.fill('#form_transfer_identification', cedula)
            page.click('#continue')
            time.sleep(2)
            
            if page.locator('div:has-text("La persona no esta registrada")').count() > 0:
                return "NO_REGISTRADA"
            return "REGISTRADA"
    except:
        return "ERROR"

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🤖 Bot de Consulta Patria activo. Envía /buscar V12345678")

@bot.message_handler(commands=['estado'])
def estado(message):
    if sesion_activa():
        bot.reply_to(message, "✅ Sesión activa. Puedes consultar.")
    else:
        descargar_sesion()
        if sesion_activa():
            bot.reply_to(message, "✅ Sesión descargada. Ya puedes consultar.")
        else:
            bot.reply_to(message, "❌ Error: No se pudo descargar la sesión.")

@bot.message_handler(commands=['buscar'])
def buscar(message):
    try:
        texto = message.text.split()
        if len(texto) < 2:
            bot.reply_to(message, "Uso: /buscar V12345678")
            return
        cedula = texto[1].upper()
        if not cedula[0] in 'VE':
            cedula = 'V' + cedula
        if not sesion_activa():
            descargar_sesion()
        msg = bot.reply_to(message, f"Consultando {cedula}...")
        resultado = consultar_patria(cedula)
        bot.edit_message_text(f"Resultado: {resultado}", message.chat.id, msg.message_id)
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['ayuda'])
def ayuda(message):
    bot.reply_to(message, "Comandos: /buscar V12345678 - /estado")

if __name__ == "__main__":
    descargar_sesion()
    print("Bot iniciado...")
    bot.infinity_polling()
