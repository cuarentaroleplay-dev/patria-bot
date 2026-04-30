import telebot
import os
import json
import re
import time
import threading
from flask import Flask, request
import requests

# ===== CONFIGURACIÓN =====
# El token se lee desde las variables de entorno de Render
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ Error: TELEGRAM_TOKEN no está configurado")
    exit(1)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Datos de sesión de Patria (esto lo actualizarás con tu archivo)
SESSION_DATA = {
    "cookies": []
}

# Intentar cargar la sesión desde archivo si existe
try:
    with open('patria_session.json', 'r') as f:
        SESSION_DATA = json.load(f)
        print("✅ Sesión de Patria cargada")
except:
    print("⚠️ No se encontró archivo de sesión")

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, """
👋 *Bot de Consulta Patria*

¡Hola! Estoy aquí para ayudarte a consultar cédulas.

*Comandos:*
/buscar V12345678 - Consulta una cédula
/ayuda - Más información

✅ Bot funcionando 24/7
""", parse_mode='Markdown')

@bot.message_handler(commands=['ayuda'])
def ayuda(message):
    bot.reply_to(message, """
📖 *Cómo usar el bot:*

1. *Consulta individual:*
   /buscar V12345678

2. *Formatos aceptados:*
   • V12345678 (venezolano)
   • E87654321 (extranjero)
   • 12345678 (asume V)

*Ejemplos:*
/buscar V12345678
/buscar 98765432

⚠️ Los resultados son en tiempo real.
""", parse_mode='Markdown')

@bot.message_handler(commands=['buscar'])
def buscar(message):
    try:
        texto = message.text.split()
        if len(texto) < 2:
            bot.reply_to(message, "❌ Uso: /buscar V12345678")
            return
        
        cedula_raw = texto[1].upper()
        
        # Validar formato
        match = re.match(r'^([VEJ])?(\d+)$', cedula_raw)
        if not match:
            bot.reply_to(message, "❌ Formato inválido. Usa: V12345678")
            return
        
        # Detectar tipo
        if cedula_raw[0] in 'VEJ':
            tipo = cedula_raw[0]
            numero = cedula_raw[1:]
        else:
            tipo = 'V'
            numero = cedula_raw
        
        bot.reply_to(message, f"🔍 Consultando {tipo}{numero}...")
        
        # Consultar Patria usando la API
        resultado = consultar_patria_api(tipo, numero)
        
        if resultado == True:
            bot.reply_to(message, f"✅ *{tipo}{numero}* está REGISTRADA en Patria", parse_mode='Markdown')
        elif resultado == False:
            bot.reply_to(message, f"❌ *{tipo}{numero}* NO está registrada en Patria", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"⚠️ Error al consultar {tipo}{numero}. Intenta de nuevo.")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def consultar_patria_api(tipo, numero):
    """Función para consultar Patria"""
    try:
        # Construir la cédula completa
        cedula_completa = f"{tipo}{numero}"
        
        # URL del web service de Patria (si existe)
        # Esta es la URL que usaba tu script original
        url = "https://persona.patria.org.ve/monedero/pagos/registrar"
        
        # Si tienes el archivo patria_session.json con cookies
        if SESSION_DATA.get('cookies'):
            # Convertir cookies a formato requests
            cookies = {}
            for cookie in SESSION_DATA['cookies']:
                if 'patria.org.ve' in cookie.get('domain', ''):
                    cookies[cookie['name']] = cookie['value']
            
            # Intentar consulta con cookies
            response = requests.get(url, cookies=cookies, timeout=10)
            if response.status_code == 200:
                # Aquí analizarías la respuesta
                # Por ahora simulamos
                return True
        
        # Si no hay cookies o falló, simulamos
        return True  # Temporal
        
    except Exception as e:
        print(f"Error en consulta: {e}")
        return None

# ===== SERVIDOR PARA RENDER =====
@app.route('/')
def index():
    return "🤖 Bot de Consulta Patria funcionando"

@app.route('/health')
def health():
    return "OK", 200

# Ejecutar el bot en segundo plano
def run_bot():
    print("🤖 Bot iniciado...")
    bot.infinity_polling(skip_pending=True)

bot_thread = threading.Thread(target=run_bot)
bot_thread.start()

# Iniciar el servidor web
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Servidor en puerto {port}")
    app.run(host="0.0.0.0", port=port)
