# notion_db.py
import os
import requests
import time
import logging
import json
from config import SPECIALIZATIONS, PRICES

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG FROM ENVIRONMENT ---
NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
DATABASE_ID = os.environ.get('DATABASE_ID')

# Заголовки для авторизации в Notion
NH = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Content-Type":   "application/json",
    "Notion-Version": "2022-06-28",
}

def _nreq(method: str, url: str, **kw) -> dict:
    for i in range(3):
        try:
            resp = requests.request(method, url, headers=NH, timeout=10, **kw)
            return resp.json()
        except Exception:
            if i == 2: return {}
            time.sleep(1.5)
    return {}

def nq(payload: dict) -> list:
    return _nreq("POST", f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", json=payload).get("results", [])

def np(pid: str, payload: dict) -> dict:
    return _nreq("PATCH", f"https://api.notion.com/v1/pages/{pid}", json=payload)

def nc(payload: dict) -> dict:
    return _nreq("POST", "https://api.notion.com/v1/pages", json=payload)

def active_bookings(cid) -> list:
    return nq({"filter": {"and": [
        {"property": "Chat ID", "rich_text": {"equals": str(cid)}},
        {"property": "Статус",  "select":    {"equals": "Запланировано"}},
    ]}})

def booked_slots(date_str: str, master: str) -> set:
    out = set()
    for page in nq({"filter": {"and": [
        {"property": "Дата записи", "date":   {"equals": date_str}},
        {"property": "Мастер",      "select": {"equals": master}},
        {"property": "Статус",      "select": {"equals": "Запланировано"}},
    ]}}):
        try: out.add(page["properties"]["Время"]["rich_text"][0]["text"]["content"])
        except: pass
    return out

def update_booking_status(page_id: str, new_status: str) -> bool:
    try:
        payload = {"properties": {"Статус": {"select": {"name": new_status}}}}
        r = np(page_id, payload)
        return "id" in r
    except Exception as e:
        logger.error(f"update_booking_status error: {e}")
        return False

def save_booking(data: dict, page_id=None) -> str:
    price = PRICES.get(data.get("service", ""), 0)
    props = {
        "Клиент":            {"title":        [{"text": {"content": data["name"]}}]},
        "Телефон":           {"phone_number": data.get("phone", "—")},
        "Услуга":            {"select":       {"name": data["service"]}},
        "Мастер":            {"select":       {"name": data["master"]}},
        "Дата записи":       {"date":         {"start": data["date"]}},
        "Время":             {"rich_text":    [{"text": {"content": data["time"]}}]},
        "Chat ID":           {"rich_text":    [{"text": {"content": str(data["chat_id"])}}]},
        "Статус":            {"select":       {"name": "Запланировано"}},
    }
    if price:
        props["Цена"] = {"number": price}
    
    r = np(page_id, {"properties": props}) if page_id else \
        nc({"parent": {"database_id": DATABASE_ID}, "properties": props})
    new_id = r.get("id", "")
    if new_id and not page_id:  # only on new booking, not reschedule
        try:
            update_client_visits(data.get("phone", ""), data.get("name", ""))
        except Exception as _ce:
            logger.error(f"client_visits err: {_ce}")
    return new_id

def get_catalog() -> dict:
    return {"categories": [
        {"name": "💇‍♀️ Волосы", "services": [{"name": "Стрижка", "price": 1500}, {"name": "Окрашивание", "price": 4000}]},
        {"name": "💅 Ногти", "services": [{"name": "Маникюр", "price": 1200}, {"name": "Педикюр", "price": 1400}]},
        {"name": "💆‍♀️ Косметология", "services": [{"name": "Чистка лица", "price": 2500}, {"name": "Пилинг", "price": 2000}]}
    ]}

def auto_close_past_bookings():
    from datetime import datetime, timedelta
    now = datetime.now()
    ds = now.strftime("%Y-%m-%d")
    query = {
        "filter": {
            "and": [
                {"property": "Статус", "select": {"equals": "Запланировано"}},
                {"property": "Дата записи", "date": {"on_or_before": ds}}
            ]
        }
    }
    results = nq(query)
    for page in results:
        try:
            p_date = page["properties"]["Дата записи"]["date"]["start"]
            p_time = page["properties"]["Время"]["rich_text"][0]["text"]["content"]
            appt_dt = datetime.strptime(f"{p_date} {p_time}", "%Y-%m-%d %H:%M")
            if appt_dt + timedelta(hours=1) < now:
                update_booking_status(page["id"], "Завершено")
        except: pass


# --- Clients DB helpers ---
def _nq_clients(payload: dict) -> list:
    cdb = os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return []
    return _nreq(
        "POST",
        f"https://api.notion.com/v1/databases/{cdb}/query",
        json=payload
    ).get("results", [])

def _nc_clients(payload: dict) -> dict:
    cdb = os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return {}
    full_payload = {"parent": {"database_id": cdb}}
    full_payload.update(payload)
    return _nreq("POST", "https://api.notion.com/v1/pages", json=full_payload)

def update_client_visits(phone: str, name: str):
    try:
        prop_phone = '\u0422\u0435\u043b\u0435\u0444\u043e\u043d'
        prop_name  = '\u0418\u043c\u044f'
        prop_vis   = '\u0412\u0438\u0437\u0438\u0442\u044b'
        results = _nq_clients({'filter': {'property': prop_phone, 'phone_number': {'equals': phone}}})
        if results:
            pid = results[0]['id']
            cur = results[0]['properties'].get(prop_vis, {}).get('number') or 0
            _nreq('PATCH', f'https://api.notion.com/v1/pages/{pid}',
                  json={'properties': {prop_vis: {'number': cur + 1}}})
            logger.info(f'Client {phone}: visits {cur} -> {cur + 1}')
        else:
            _nc_clients({'properties': {
                prop_name:  {'title':        [{'text': {'content': name}}]},
                prop_phone: {'phone_number': phone},
                prop_vis:   {'number':       1},
            }})
            logger.info(f'New client created: {name} {phone}')
    except Exception as e:
        logger.error(f'update_client_visits error: {e}')


def today_bookings() -> list:
    from datetime import date as _d
    ds = _d.today().strftime('%Y-%m-%d')
    prop_date   = '\u0414\u0430\u0442\u0430 \u0437\u0430\u043f\u0438\u0441\u0438'
    prop_status = '\u0421\u0442\u0430\u0442\u0443\u0441'
    prop_val    = '\u0417\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u043e'
    return nq({'filter': {'and': [
        {'property': prop_date,   'date':   {'equals': ds}},
        {'property': prop_status, 'select': {'equals': prop_val}},
    ]}})
