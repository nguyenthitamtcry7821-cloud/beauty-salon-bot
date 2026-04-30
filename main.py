# main.py
import telebot
from telebot import types
import threading
import time
import logging
import json
from datetime import datetime, date, timedelta

# --- ИМПОРТЫ ИЗ НАШИХ МОДУЛЕЙ ---
from config import (
    API_TOKEN, ADMIN_IDS, MASTERS_CHAT_IDS
)
from notion_db import (
    active_bookings, save_booking, update_booking_status, 
    auto_close_past_bookings, today_bookings,
    get_clients_stats, tomorrow_bookings
)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================
bot = telebot.TeleBot(API_TOKEN)
user_data: dict = {}

# Устанавливаем Menu Button
MINI_APP_URL = "https://6b84660de86de6.lhr.life"
try:
    from telebot.types import MenuButtonWebApp, WebAppInfo
    bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="🚀 Записаться",
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
    )
    logger.info("✅ Menu Button установлена")
except Exception as e:
    logger.warning(f"Menu Button не установлена: {e}")

# ============================================================
# /start
# ============================================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    cid = message.chat.id
    # Предварительная инициализация, если данных еще нет
    if cid not in user_data:
        user_data[cid] = {"name": message.from_user.first_name, "phone": "—"}
    
    bot.send_message(
        cid,
        "👋 *Привет! Добро пожаловать в наш салон!*\n\n"
        "Для записи воспользуйтесь кнопкой в меню 👇",
        parse_mode="Markdown"
    )

# ============================================================
# MINI APP DATA HANDLER
# ============================================================
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        cid = message.chat.id
        
        # Берём name и phone из user_data (если нет — создаём)
        if cid not in user_data:
            user_data[cid] = {
                "name": message.from_user.first_name or "Клиент",
                "phone": "—"
            }
        
        booking_data = {
            "name": user_data[cid].get("name", "Клиент"),
            "phone": user_data[cid].get("phone", "—"),
            "service": data.get("service"),
            "master": data.get("master"),
            "date": data.get("date"),
            "time": data.get("time"),
            "chat_id": cid
        }
        
        # Сохранение в Notion
        booking_id = save_booking(booking_data)
        
        # Уведомление админам
        msg_text = (f"⚠️ *Новая запись (Mini App)!*\n"
                    f"👤 Клиент: {booking_data['name']}\n"
                    f"💆 Услуга: {booking_data['service']}\n"
                    f"✂️ Мастер: {booking_data['master']}\n"
                    f"📅 Время: {booking_data['date']} в {booking_data['time']}")
        
        for admin_id in ADMIN_IDS:
            try: bot.send_message(admin_id, msg_text, parse_mode="Markdown")
            except: pass

        bot.send_message(cid, "✅ Вы успешно записаны!", parse_mode="Markdown")
        logger.info(f"Запись через Mini App создана: {booking_id}")
        
    except Exception as e:
        logger.error(f"Ошибка в handle_web_app_data: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка при сохранении записи.")

# ============================================================
# АДМИН ПАНЕЛЬ И УВЕДОМЛЕНИЯ (Оставляем для работы)
# ============================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("ST::"))
def cb_admin_status(call):
    all_allowed = set(ADMIN_IDS) | set(MASTERS_CHAT_IDS.values())
    if call.message.chat.id not in all_allowed:
        return bot.answer_callback_query(call.id, "🚫 Нет доступа.")
    _, status, pid = call.data.split("::")
    if update_booking_status(pid, status):
        icon = "✅" if status == "Завершено" else "❌"
        bot.edit_message_text(f"{call.message.text}\n\n{icon} *Статус изменен на: {status}*", 
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if message.chat.id not in ADMIN_IDS:
        return bot.send_message(message.chat.id, "🚫 Доступ запрещён.")
    mk = types.InlineKeyboardMarkup()
    mk.add(
        types.InlineKeyboardButton("📊 Статистика",  callback_data="ADM|stats"),
        types.InlineKeyboardButton("👥 CRM",          callback_data="ADM|crm")
    )
    bot.send_message(message.chat.id, "👑 *Админ-панель*", reply_markup=mk, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("ADM|"))
def cb_adm(call):
    cid = call.message.chat.id
    if cid not in ADMIN_IDS: return
    action = call.data.split("|")[1]
    if action == "stats":
        pages = today_bookings()
        lines = [f"*Записи на сегодня:*\n"]
        for page in pages:
            p = page["properties"]
            try:
                t = p['Время']["rich_text"][0]["text"]["content"]
                svc = p['Услуга']["select"]["name"]
                cli = p['Клиент']["title"][0]["text"]["content"]
                lines.append(f"• {t} | {cli} | {svc}")
            except: pass
        bot.edit_message_text("\n".join(lines) if len(lines)>1 else "Нет записей.", cid, call.message.message_id, parse_mode="Markdown")
    elif action == "crm":
        stats = get_clients_stats()
        text = f"👥 *CRM*\nВсего клиентов: {stats['total_clients']}\nВсего визитов: {stats['total_visits']}"
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

# ============================================================
# ФОНОВЫЕ ЗАДАЧИ
# ============================================================
def auto_status_manager():
    while True:
        try: auto_close_past_bookings()
        except: pass
        time.sleep(1800)

if __name__ == "__main__":
    threading.Thread(target=auto_status_manager, daemon=True).start()
    print("🚀 Бот запущен!")
    bot.infinity_polling(skip_pending=True)
