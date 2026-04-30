# notion_db.py
import os
import requests
import time
import logging
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG FROM ENVIRONMENT ---
NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
DATABASE_ID = os.environ.get('DATABASE_ID')

# Программа лояльности (визиты: скидка %)
try:
    LOYALTY_RAW = os.environ.get('LOYALTY', '{ "3": 5, "5": 10, "10": 15 }')
    LOYALTY = {int(k): v for k, v in json.loads(LOYALTY_RAW).items()}
except Exception as e:
    logger.warning(f"Error parsing LOYALTY env: {e}. Using defaults.")
    LOYALTY = {3: 5, 5: 10, 10: 15}

# Прайс-лист
try:
    PRICES = json.loads(os.environ.get('PRICES', '{}'))
except Exception as e:
    logger.warning(f"Error parsing PRICES env: {e}. Using empty dict.")
    PRICES = {}

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
    return r.get("id", "")

def get_catalog() -> dict:
    results = nq({})
    categories_map = {}
    for page in results:
        props = page.get("properties", {})
        name = ""
        if "Услуга" in props and props["Услуга"].get("select"):
            name = props["Услуга"]["select"]["name"]
        if not name: continue
        
        price = props.get("Цена", {}).get("number") or 0
        category = "Прочее"
        if "Категория" in props and props["Категория"].get("select"):
            category = props["Категория"]["select"]["name"]

        if category not in categories_map: categories_map[category] = []
        if not any(s["name"] == name for s in categories_map[category]):
            categories_map[category].append({"name": name, "price": price})

    catalog = {"categories": []}
    for cat_name, services in categories_map.items():
        catalog["categories"].append({"name": cat_name, "services": services})
    return catalog

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
