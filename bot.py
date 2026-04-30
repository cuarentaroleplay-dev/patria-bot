#!/usr/bin/env python3
"""
Bot de Telegram para consultar cédulas en Patria
Funciona con Playwright y mantiene sesión desde GitHub privado
"""

import telebot
import os
import time
import json
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Token del bot de Telegram (desde variable de entorno)
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ Error: TELEGRAM_TOKEN no está configurado")
    exit(1)

# Inicializar bot
bot = telebot.TeleBot(TOKEN)

# Archivos
SESSION_FILE = "patria_session.json"
LOG_FILE = "bot.log"

# ============================================================
# CONFIGURACIÓN DE GITHUB (para descargar la sesión)
# ============================================================

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "cuarentaroleplay-dev/patria-session"  # ← CAMBIA TU_USUARIO por tu nombre de GitHub
SESSION_URL = f"SESSION_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/patria_session.json"

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def log(mensaje):
    """Guarda mensajes en archivo de log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(f"[{timestamp}] {mensaje}\n")
    except:
        pass
    print(mensaje)

def descargar_sesion():
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.raw"
        }
        
        log(f"🔐 Descargando sesión desde GitHub API...")
        response = requests.get(SESSION_URL, headers=headers)
        
        if response.status_code == 200:
            with open(SESSION_FILE, "w") as f:
                f.write(response.text)
            log("✅ Sesión descargada correctamente desde GitHub")
            return True
        else:
            log(f"⚠️ Error {response.status_code}: {response.text[:100]}")
            return False
    except Exception as e:
        log(f"❌ Error descargando sesión: {e}")
        return False

def sesion_activa():
    """Verifica si el archivo de sesión existe y es válido"""
    if not os.path.exists(SESSION_FILE):
        return False
    
    try:
        with open(SESSION_FILE, 'r') as f:
            data = json.load(f)
            return len(data.get('cookies', [])) > 0
    except:
        return False

def consultar_patria(cedula_completa):
    """
    Consulta una cédula en Patria usando Playwright
    Retorna: "REGISTRADA", "NO_REGISTRADA", "SESION_EXPIRADA" o mensaje de error
    """
    browser = None
    try:
        with sync_playwright() as p:
            # Lanzar navegador (headless = sin interfaz gráfica)
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu']
            )
            
            # Cargar la sesión guardada
            if not os.path.exists(SESSION_FILE):
                return "SESION_NO_CONFIGURADA"
            
            context = browser.new_context(storage_state=SESSION_FILE)
            page = context.new_page()
            
            # Ir a la página de registro de pagos
            page.goto("https://persona.patria.org.ve/monedero/pagos/registrar")
            page.wait_for_load_state("networkidle")
            
            # ===== PASOS DEL SCRIPT ORIGINAL =====
            
            # 1. Seleccionar monedero destino
            page.click('input[type="text"][value="Selecciona el Monedero Destino"]')
            time.sleep(0.3)
            page.click('//span[contains(text(), "Monedero Bolívar Digital (Bs)")]')
            time.sleep(0.3)
            
            # 2. Seleccionar tipo "Cédula"
            page.click('#select2-form_transfer_destination_type_select-container')
            time.sleep(0.3)
            search_field = page.locator('.select2-search__field')
            search_field.fill('cedula')
            time.sleep(0.3)
            page.click('//li[contains(text(), "Otro (Cédula)")]')
            time.sleep(0.3)
            
            # 3. Escribir descripción
            page.fill('#form_transfer_description', "consulta")
            time.sleep(0.2)
            
            # 4. Escribir la cédula y consultar
            cedula_input = page.locator('#form_transfer_identification')
            cedula_input.fill('')
            cedula_input.fill(cedula_completa)
            page.click('#continue')
            
            # 5. Esperar respuesta
            time.sleep(2)
            
            # 6. Verificar resultado
            mensaje_no_registrada = page.locator('div:has-text("La persona no esta registrada")')
            
            browser.close()
            
            if mensaje_no_registrada.count() > 0:
                return "NO_REGISTRADA"
            else:
                return "REGISTRADA"
                
    except Exception as e:
        log(f"Error en consulta: {e}")
        error_str = str(e).lower()
        if "session" in error_str or "storage" in error_str:
            return "SESION_EXPIRADA"
        return f"ERROR: {str(e)[:50]}"
    finally:
        if browser:
            try:
                browser.close()
            except:
                pass

# ============================================================
# COMANDOS DEL BOT
# ============================================================

@bot.message_handler(commands=['start'])
def start(message):
    """Mensaje de bienvenida"""
    bot.reply_to(message, """
🤖 *BOT DE CONSULTA PATRIA*

¡Bot funcionando correctamente!

*Comandos disponibles:*

🔐 *Sesión:*
/estado - Verificar estado de la sesión

🔍 *Consultas:*
/buscar V12345678 - Consultar una cédula

📖 *Ayuda:*
/ayuda - Información detallada

✅ El bot está 24/7
""", parse_mode='Markdown')

@bot.message_handler(commands=['ayuda'])
def ayuda(message):
    """Mensaje de ayuda detallada"""
    bot.reply_to(message, """
📖 *GUÍA DE USO*

*Formato de cédulas:*
• V12345678 (venezolano)
• E87654321 (extranjero)
• 12345678 (se asume V)

*Ejemplos:*
/buscar V12345678
/buscar 98765432

*Resultados posibles:*
✅ REGISTRADA - La persona está en Patria
❌ NO REGISTRADA - La persona NO está en Patria
⚠️ Error - La sesión puede haber expirado

*¿La sesión expiró?*
El administrador debe actualizar el archivo de sesión.
""", parse_mode='Markdown')

@bot.message_handler(commands=['estado'])
def estado(message):
    """Verifica el estado de la sesión de Patria"""
    if sesion_activa():
        # Obtener información del archivo
        try:
            stat = os.stat(SESSION_FILE)
            fecha = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
            bot.reply_to(message, f"✅ *SESION ACTIVA*\n📅 Última actualización: {fecha}", parse_mode='Markdown')
        except:
            bot.reply_to(message, "✅ *SESION ACTIVA*\nEl bot está listo para consultar", parse_mode='Markdown')
    else:
        bot.reply_to(message, """
❌ *SESION NO CONFIGURADA*

El archivo de sesión no está disponible.
El administrador debe configurarlo.
""", parse_mode='Markdown')

@bot.message_handler(commands=['buscar'])
def buscar(message):
    """Consulta una cédula individual"""
    try:
        # Extraer y validar la cédula
        partes = message.text.split()
        if len(partes) < 2:
            bot.reply_to(message, "❌ *Uso correcto:* `/buscar V12345678`", parse_mode='Markdown')
            return
        
        cedula_raw = partes[1].upper()
        
        # Validar formato
        if cedula_raw[0] in 'VE':
            tipo = cedula_raw[0]
            numero = cedula_raw[1:]
        else:
            tipo = 'V'
            numero = cedula_raw
        
        if not numero.isdigit():
            bot.reply_to(message, "❌ *Formato inválido*\nUsa: V12345678 o E87654321", parse_mode='Markdown')
            return
        
        cedula_completa = f"{tipo}-{numero}"
        
        # Verificar sesión antes de consultar
        if not sesion_activa():
            bot.reply_to(message, "⚠️ *No hay sesión activa*\nEl administrador debe configurarla.", parse_mode='Markdown')
            return
        
        # Avisar que comenzó la consulta
        msg = bot.reply_to(message, f"🔍 *Consultando {cedula_completa}...*\n⏳ Un momento, por favor", parse_mode='Markdown')
        
        # Realizar la consulta
        resultado = consultar_patria(cedula_completa)
        
        # Responder según el resultado
        if resultado == "NO_REGISTRADA":
            bot.edit_message_text(f"❌ *{cedula_completa}*\n→ **NO REGISTRADA** en Patria", 
                                 message.chat.id, msg.message_id, parse_mode='Markdown')
        elif resultado == "REGISTRADA":
            bot.edit_message_text(f"✅ *{cedula_completa}*\n→ **REGISTRADA** en Patria", 
                                 message.chat.id, msg.message_id, parse_mode='Markdown')
        elif resultado == "SESION_EXPIRADA":
            bot.edit_message_text(f"⚠️ *Sesión expirada*\n\nEl administrador debe renovar el archivo patria_session.json", 
                                 message.chat.id, msg.message_id, parse_mode='Markdown')
        elif resultado == "SESION_NO_CONFIGURADA":
            bot.edit_message_text(f"⚠️ *Sesión no configurada*\n\nEl administrador debe subir el archivo de sesión", 
                                 message.chat.id, msg.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(f"⚠️ *Error:* {resultado}", 
                                 message.chat.id, msg.message_id)
            
    except Exception as e:
        bot.reply_to(message, f"❌ *Error:* {str(e)[:100]}", parse_mode='Markdown')
        log(f"Error en comando buscar: {e}")

@bot.message_handler(commands=['reload'])
def recargar_sesion(message):
    """Comando para recargar la sesión desde GitHub (solo administrador)"""
    # Solo el administrador puede usar este comando
    ADMIN_ID = os.environ.get("ADMIN_ID", "")
    if ADMIN_ID and str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "❌ Comando solo para administradores")
        return
    
    bot.reply_to(message, "🔄 Recargando sesión desde GitHub...")
    
    if descargar_sesion():
        bot.reply_to(message, "✅ *Sesión recargada correctamente*\n\nYa puedes usar /buscar", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ *Error al recargar la sesión*\nVerifica el repositorio y el token", parse_mode='Markdown')

# ============================================================
# INICIO DEL BOT
# ============================================================

if __name__ == "__main__":
    log("=" * 50)
    log("🤖 BOT DE CONSULTA PATRIA INICIADO")
    log("=" * 50)
    
    # Descargar la sesión desde GitHub al iniciar
    if descargar_sesion():
        log("✅ Sesión cargada correctamente")
    else:
        log("⚠️ No se pudo descargar la sesión. El bot funcionará sin sesión.")
    
    log(f"Sesión activa: {'✅ Sí' if sesion_activa() else '❌ No'}")
    log("=" * 50)
    log("🟢 Bot esperando mensajes...")
    log("=" * 50)
    
    # Iniciar el bot con manejo de errores
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except Exception as e:
            log(f"Error en polling: {e}")
            time.sleep(5)
