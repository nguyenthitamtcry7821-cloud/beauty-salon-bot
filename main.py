# main.py
import telebot
import json
import logging
import os
from telebot import types
from telebot.types import MenuButtonWebApp, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG FROM ENVIRONMENT ---
API_TOKEN = os.environ.get('API_TOKEN')

try:
    raw_admins = os.environ.get('ADMIN_IDS', '')
    ADMIN_IDS = [int(x.strip()) for x in raw_admins.split(',') if x.strip()]
except:
    ADMIN_IDS = []

try:
    MASTERS_CHAT_IDS = json.loads(os.environ.get('MASTERS_CHAT_IDS', '{}'))
except:
    MASTERS_CHAT_IDS = {}

DOMAIN = os.environ.get("DOMAIN", "")

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(API_TOKEN)

from notion_db import save_booking, update_booking_status

@bot.message_handler(commands=["start"])
def cmd_start(message):
    cid = message.chat.id
    # Устанавливаем кнопку Mini App
    try:
        mk = MenuButtonWebApp(text="🚀 Записаться", web_app=WebAppInfo(url=DOMAIN))
        bot.set_chat_menu_button(cid, mk)
    except: pass
    
    bot.send_message(cid, "👋 *Привет! Добро пожаловать!*\n\nИспользуйте кнопку в меню для записи.", parse_mode="Markdown")

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        web_data = json.loads(message.web_app_data.data)
        cid = message.chat.id
        
        booking_data = {
            "name": message.from_user.first_name or "Клиент",
            "phone": "—",
            "service": web_data.get("service"),
            "master": web_data.get("master", "Любой"),
            "date": web_data.get("date"),
            "time": web_data.get("time"),
            "chat_id": cid
        }
        
        booking_id = save_booking(booking_data)
        bot.send_message(cid, "✅ *Запись подтверждена!*", parse_mode="Markdown")
        
        # Уведомление админам
        admin_msg = (f"🔔 *Новая запись!*\n\n👤 {booking_data['name']}\n💆 {booking_data['service']}\n"
                     f"📅 {booking_data['date']} в {booking_data['time']}\n✂️ {booking_data['master']}")
        
        mk_admin = types.InlineKeyboardMarkup()
        mk_admin.add(
            types.InlineKeyboardButton("✅ Завершить", callback_data=f"ST::Завершено::{booking_id}"),
            types.InlineKeyboardButton("❌ Отменить",   callback_data=f"ST::Отменена::{booking_id}")
        )
        
        for admin_id in ADMIN_IDS:
            try: bot.send_message(admin_id, admin_msg, reply_markup=mk_admin, parse_mode="Markdown")
            except: pass
            
    except Exception as e:
        logger.error(f"Error in handle_web_app_data: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("ST::"))
def cb_admin_status(call):
    allowed_ids = set(ADMIN_IDS) | set(MASTERS_CHAT_IDS.values())
    if call.message.chat.id not in allowed_ids:
        return bot.answer_callback_query(call.id, "🚫 Нет доступа.")
    
    _, status, pid = call.data.split("::")
    if update_booking_status(pid, status):
        icon = "✅" if status == "Завершено" else "❌"
        bot.edit_message_text(f"{call.message.text}\n\n{icon} *Статус: {status}*", 
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.answer_callback_query(call.id)
