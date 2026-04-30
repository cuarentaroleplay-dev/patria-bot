import telebot
import os
import time
import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== CONFIGURACIÓN =====
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ Error: TELEGRAM_TOKEN no configurado")
    exit(1)

bot = telebot.TeleBot(TOKEN)
SESSION_FILE = "patria_session.json"

# ===== FUNCIONES =====

def sesion_activa():
    """Verifica si la sesión guardada es válida"""
    if not os.path.exists(SESSION_FILE):
        return False
    return True

def consultar_patria(cedula_completa):
    """Consulta una cédula en Patria"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            if os.path.exists(SESSION_FILE):
                context = browser.new_context(storage_state=SESSION_FILE)
            else:
                context = browser.new_context()
            
            page = context.new_page()
            page.goto("https://persona.patria.org.ve/monedero/pagos/registrar")
            page.wait_for_load_state("networkidle")
            
            # Seleccionar monedero
            page.click('input[type="text"][value="Selecciona el Monedero Destino"]')
            time.sleep(0.3)
            page.click('//span[contains(text(), "Monedero Bolívar Digital (Bs)")]')
            time.sleep(0.3)
            
            # Seleccionar tipo "Cédula"
            page.click('#select2-form_transfer_destination_type_select-container')
            time.sleep(0.3)
            search_field = page.locator('.select2-search__field')
            search_field.fill('cedula')
            time.sleep(0.3)
            page.click('//li[contains(text(), "Otro (Cédula)")]')
            time.sleep(0.3)
            
            # Descripción
            page.fill('#form_transfer_description', "consulta")
            time.sleep(0.2)
            
            # Escribir cédula y consultar
            cedula_input = page.locator('#form_transfer_identification')
            cedula_input.fill('')
            cedula_input.fill(cedula_completa)
            page.click('#continue')
            time.sleep(2)
            
            # Verificar resultado
            mensaje_no_registrada = page.locator('div:has-text("La persona no esta registrada")')
            browser.close()
            
            if mensaje_no_registrada.count() > 0:
                return "NO_REGISTRADA"
            else:
                return "REGISTRADA"
                
    except Exception as e:
        return f"ERROR: {str(e)[:50]}"

# ===== COMANDOS DEL BOT =====

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, """
🤖 *BOT DE CONSULTA PATRIA*

*Comandos:*
/buscar V12345678 - Consultar una cédula
/estado - Verificar sesión
/ayuda - Más información

✅ Bot funcionando 24/7 en Render
""", parse_mode='Markdown')

@bot.message_handler(commands=['ayuda'])
def ayuda(message):
    bot.reply_to(message, """
📖 *Cómo usar:*

1. Consultar una cédula:
   `/buscar V12345678`

2. Formatos válidos:
   V12345678 (venezolano)
   E87654321 (extranjero)

⚠️ *Nota:* La primera vez debes iniciar sesión manualmente en Patria desde tu navegador para generar el archivo de sesión.
""", parse_mode='Markdown')

@bot.message_handler(commands=['estado'])
def estado(message):
    if sesion_activa():
        bot.reply_to(message, "✅ Sesión de Patria ACTIVA\n\nEl bot está listo para consultar")
    else:
        bot.reply_to(message, "❌ Sesión NO configurada\n\nNecesitas generar el archivo patria_session.json")
@bot.message_handler(commands=['buscar'])
def buscar(message):
    try:
        partes = message.text.split()
        if len(partes) < 2:
            bot.reply_to(message, "❌ *Uso:* `/buscar V12345678`", parse_mode='Markdown')
            return
        
        cedula_raw = partes[1].upper()
        
        if cedula_raw[0] in 'VE':
            tipo = cedula_raw[0]
            numero = cedula_raw[1:]
        else:
            tipo = 'V'
            numero = cedula_raw
        
        if not numero.isdigit():
            bot.reply_to(message, "❌ Formato inválido", parse_mode='Markdown')
            return
        
        cedula_completa = f"{tipo}-{numero}"
        
        if not sesion_activa():
            bot.reply_to(message, "⚠️ No hay sesión activa", parse_mode='Markdown')
            return
        
        msg = bot.reply_to(message, f"🔍 Consultando {cedula_completa}...")
        resultado = consultar_patria(cedula_completa)
        
        if resultado == "NO_REGISTRADA":
            bot.edit_message_text(f"❌ {cedula_completa} → NO REGISTRADA", message.chat.id, msg.message_id)
        elif resultado == "REGISTRADA":
            bot.edit_message_text(f"✅ {cedula_completa} → REGISTRADA", message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(f"⚠️ {resultado}", message.chat.id, msg.message_id)
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# ===== INICIO =====
if __name__ == "__main__":
    print("🤖 Bot iniciado en Render...")
    bot.infinity_polling()
