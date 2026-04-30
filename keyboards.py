# keyboards.py
from telebot import types
from datetime import date, timedelta
import calendar

# Импортируем настройки и функцию из наших новых файлов
from config import TIME_SLOTS, SPECIALIZATIONS, PRICES
from notion_db import booked_slots

MRU = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
       "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

def get_main_menu():
    """Возвращает клавиатуру главного меню — только нужные кнопки управления записями"""
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🔄 Перенести запись", "❌ Отменить визит")
    m.row("📋 Мои записи", "🎁 Моя скидка")
    m.row("🌟 Портфолио")
    return m

def get_categories_mk():
    """Инлайн-клавиатура выбора направления"""
    mk = types.InlineKeyboardMarkup(row_width=1)
    for cat in SPECIALIZATIONS:
        mk.add(types.InlineKeyboardButton(cat, callback_data=f"CAT|{cat}"))
    mk.row(types.InlineKeyboardButton("🏠 В главное меню", callback_data="MAIN_MENU"))
    return mk

def get_services_mk(cat):
    """Инлайн-клавиатура выбора услуги"""
    mk = types.InlineKeyboardMarkup(row_width=1)
    for s in SPECIALIZATIONS[cat]["services"]:
        p = PRICES.get(s)
        text = f"{s} — {p} руб." if p else s
        mk.add(types.InlineKeyboardButton(text, callback_data=f"SVC|{s}"))
    mk.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="BACK_TO_CAT"))
    mk.row(types.InlineKeyboardButton("🏠 Меню", callback_data="MAIN_MENU"))
    return mk

def get_masters_mk(cat):
    """Инлайн-клавиатура выбора мастера"""
    mk = types.InlineKeyboardMarkup(row_width=2)
    for m in SPECIALIZATIONS[cat]["masters"]:
        mk.add(types.InlineKeyboardButton(m, callback_data=f"MST|{m}"))
    mk.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="BACK_TO_SVC"))
    mk.row(types.InlineKeyboardButton("🏠 Меню", callback_data="MAIN_MENU"))
    return mk

def cal(y, m):
    """Генерирует инлайн-календарь на выбранный месяц и год"""
    mk = types.InlineKeyboardMarkup(row_width=7)
    mk.add(types.InlineKeyboardButton(f"✨ {MRU[m-1]} {y} ✨", callback_data="ign"))
    mk.add(*[types.InlineKeyboardButton(d, callback_data="ign")
             for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]])
    
    today = date.today()
    for week in calendar.monthcalendar(y, m):
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(" ", callback_data="ign"))
            else:
                d = date(y, m, day)
                row.append(types.InlineKeyboardButton(
                    "·" if d < today else str(day),
                    callback_data="ign" if d < today else f"D|{y}|{m}|{day}"))
        mk.add(*row)
        
    prev = date(y, m, 1) - timedelta(days=1)
    nxt  = date(y, m, 28) + timedelta(days=4)
    mk.row(
        types.InlineKeyboardButton("⬅️", callback_data=f"N|{prev.year}|{prev.month}"),
        types.InlineKeyboardButton("➡️", callback_data=f"N|{nxt.year}|{nxt.month}"),
    )
    mk.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="BACK_TO_MST"))
    mk.row(types.InlineKeyboardButton("🏠 Меню", callback_data="MAIN_MENU"))
    return mk

def time_mk(date_str, master):
    """Генерирует клавиатуру со свободными слотами времени"""
    bs = booked_slots(date_str, master)
    mk = types.InlineKeyboardMarkup(row_width=4)
    slots = []
    for s in TIME_SLOTS:
        if s not in bs:  # skip busy slots
            slots.append(types.InlineKeyboardButton(s, callback_data=f"T|{s}"))
    mk.add(*slots)
    mk.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="BACK_TO_CAL"))
    mk.row(types.InlineKeyboardButton("🏠 Меню", callback_data="MAIN_MENU"))
    return mk
