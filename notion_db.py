# notion_db.py — rebuilt with client visits tracking
import os
import requests
import time
import logging
from config import NOTION_TOKEN, DATABASE_ID, LOYALTY

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Заголовки для авторизации в Notion
NH = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Content-Type":   "application/json",
    "Notion-Version": "2022-06-28",
}

def _nreq(method: str, url: str, **kw) -> dict:
    for i in range(3):
        try:
            return requests.request(method, url, headers=NH, timeout=10, **kw).json()
        except requests.exceptions.ConnectionError:
            if i == 2: return {}
            time.sleep(1.5)
    return {}

def nq(payload: dict) -> list:
    return _nreq("POST", f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", json=payload).get("results", [])

def ng(pid: str) -> dict:
    return _nreq("GET", f"https://api.notion.com/v1/pages/{pid}")

def np(pid: str, payload: dict) -> dict:
    return _nreq("PATCH", f"https://api.notion.com/v1/pages/{pid}", json=payload)

def nc(payload: dict) -> dict:
    return _nreq("POST", "https://api.notion.com/v1/pages", json=payload)

def active_bookings(cid) -> list:
    return nq({"filter": {"and": [
        {"property": "Chat ID", "rich_text": {"equals": str(cid)}},
        {"property": "\u0421\u0442\u0430\u0442\u0443\u0441",  "select":    {"equals": "\u0417\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u043e"}},
    ]}})

def booked_slots(date_str: str, master: str) -> set:
    out = set()
    for page in nq({"filter": {"and": [
        {"property": "\u0414\u0430\u0442\u0430 \u0437\u0430\u043f\u0438\u0441\u0438", "date":   {"equals": date_str}},
        {"property": "\u041c\u0430\u0441\u0442\u0435\u0440",      "select": {"equals": master}},
        {"property": "\u0421\u0442\u0430\u0442\u0443\u0441",      "select": {"equals": "\u0417\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u043e"}},
    ]}}):
        try: out.add(page["properties"]["\u0412\u0440\u0435\u043c\u044f"]["rich_text"][0]["text"]["content"])
        except: pass
    return out

def visits_done(cid) -> int:
    return len(nq({"filter": {"and": [
        {"property": "Chat ID", "rich_text": {"equals": str(cid)}},
        {"property": "\u0421\u0442\u0430\u0442\u0443\u0441",  "select":    {"equals": "\u0417\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043e"}},
    ]}}))

def discount(cid) -> int:
    v, d = visits_done(cid), 0
    for t, pct in sorted(LOYALTY.items()):
        if v >= t: d = pct
    return d

def update_booking_status(page_id: str, new_status: str) -> bool:
    try:
        payload = {"properties": {"\u0421\u0442\u0430\u0442\u0443\u0441": {"select": {"name": new_status}}}}
        r = np(page_id, payload)
        if "id" in r:
            logger.info(f"Status of {page_id} changed to {new_status}")
            return True
        else:
            logger.error(f"Notion API error updating status {page_id}: {r}")
            return False
    except Exception as e:
        logger.error(f"Exception updating status {page_id}: {e}")
        return False

def auto_close_past_bookings():
    from datetime import datetime, timedelta
    now = datetime.now()
    ds = now.strftime("%Y-%m-%d")
    query = {
        "filter": {
            "and": [
                {"property": "\u0421\u0442\u0430\u0442\u0443\u0441", "select": {"equals": "\u0417\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u043e"}},
                {"property": "\u0414\u0430\u0442\u0430 \u0437\u0430\u043f\u0438\u0441\u0438", "date": {"on_or_before": ds}}
            ]
        }
    }
    try:
        results = nq(query)
        for page in results:
            pid = page["id"]
            p = page["properties"]
            try:
                p_date = p["\u0414\u0430\u0442\u0430 \u0437\u0430\u043f\u0438\u0441\u0438"]["date"]["start"]
                p_time = p["\u0412\u0440\u0435\u043c\u044f"]["rich_text"][0]["text"]["content"]
                appt_dt = datetime.strptime(f"{p_date} {p_time}", "%Y-%m-%d %H:%M")
                if appt_dt + timedelta(hours=1) < now:
                    update_booking_status(pid, "\u0417\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043e")
                    logger.info(f"Auto-closed booking: {pid}")
            except Exception as ex:
                logger.error(f"Error processing page {pid}: {ex}")
    except Exception as e:
        logger.error(f"Error in auto_close_past_bookings: {e}")


# ─── CLIENTS DB — visit counter ───────────────────────────────────────────────

def _nq_clients(payload: dict) -> list:
    """Query the Clients database."""
    cdb = os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return []
    return _nreq(
        "POST",
        f"https://api.notion.com/v1/databases/{cdb}/query",
        json=payload
    ).get("results", [])

def _nc_clients(payload: dict) -> dict:
    """Create a record in the Clients database."""
    cdb = os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return {}
    full_payload = {"parent": {"database_id": cdb}}
    full_payload.update(payload)
    return _nreq("POST", "https://api.notion.com/v1/pages", json=full_payload)

def update_client_visits(phone: str, name: str):
    """
    Search client by phone in Clients DB.
    Found     -> +1 to Visits counter.
    Not found -> create new record with Visits = 1.
    """
    PROP_PHONE = "\u0422\u0435\u043b\u0435\u0444\u043e\u043d"   # Телефон
    PROP_NAME  = "\u0418\u043c\u044f"                            # Имя
    PROP_VIS   = "\u0412\u0438\u0437\u0438\u0442\u044b"          # Визиты
    try:
        results = _nq_clients({
            "filter": {"property": PROP_PHONE, "phone_number": {"equals": phone}}
        })
        if results:
            pid = results[0]["id"]
            cur = results[0]["properties"].get(PROP_VIS, {}).get("number") or 0
            _nreq("PATCH", f"https://api.notion.com/v1/pages/{pid}",
                  json={"properties": {PROP_VIS: {"number": cur + 1}}})
            logger.info(f"Client {phone}: visits {cur} -> {cur + 1}")
        else:
            _nc_clients({"properties": {
                PROP_NAME:  {"title":        [{"text": {"content": name}}]},
                PROP_PHONE: {"phone_number": phone},
                PROP_VIS:   {"number":       1},
            }})
            logger.info(f"New client created: {name} {phone}")
    except Exception as e:
        logger.error(f"update_client_visits error: {e}")


def save_booking(data: dict, page_id=None) -> str:
    """
    Сохраняет запись в основной БД Notion.
    Для новых записей (page_id=None) обновляет счётчик визитов в базе Клиентов.
    """
    from config import PRICES
    price = PRICES.get(data.get("service", ""), 0)
    props = {
        "\u041a\u043b\u0438\u0435\u043d\u0442":            {"title":        [{"text": {"content": data["name"]}}]},
        "\u0422\u0435\u043b\u0435\u0444\u043e\u043d":         {"phone_number": data["phone"]},
        "\u0423\u0441\u043b\u0443\u0433\u0430":            {"select":       {"name": data["service"]}},
        "\u041c\u0430\u0441\u0442\u0435\u0440":            {"select":       {"name": data["master"]}},
        "\u0414\u0430\u0442\u0430 \u0437\u0430\u043f\u0438\u0441\u0438": {"date":         {"start": data["date"]}},
        "\u0412\u0440\u0435\u043c\u044f":           {"rich_text":    [{"text": {"content": data["time"]}}]},
        "Chat ID":         {"rich_text":    [{"text": {"content": str(data["chat_id"])}}]},
        "\u0421\u0442\u0430\u0442\u0443\u0441":            {"select":       {"name": "\u0417\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u043e"}},
    }
    # Сохраняем цену, если она есть в прайс-листе
    if price:
        props["\u0426\u0435\u043d\u0430"] = {"number": price}
    r = np(page_id, {"properties": props}) if page_id else \
        nc({"parent": {"database_id": DATABASE_ID}, "properties": props})
    new_id = r.get("id", "")
    # Обновляем счётчик визитов в базе Клиентов (только для новых, не переносов)
    if new_id and not page_id:
        try:
            update_client_visits(data.get("phone", ""), data.get("name", ""))
        except Exception as _ce:
            logger.error(f"client_visits err: {_ce}")
    return new_id


def get_busy_slots(date: str, master_name: str) -> set:
    """Returns set of busy time slots for given date and master."""
    return booked_slots(date, master_name)


def today_bookings() -> list:
    """Возвращает все 'Запланировано' записи на сегодня."""
    from datetime import date as _d
    ds = _d.today().strftime("%Y-%m-%d")
    return nq({"filter": {"and": [
        {"property": "\u0414\u0430\u0442\u0430 \u0437\u0430\u043f\u0438\u0441\u0438", "date":   {"equals": ds}},
        {"property": "\u0421\u0442\u0430\u0442\u0443\u0441",      "select": {"equals": "\u0417\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u043e"}},
    ]}})


def tomorrow_bookings() -> list:
    """
    Возвращает все записи со статусом 'Запланировано' на завтра.
    Используется системой Анти-Неявка для рассылки напоминаний.
    Каждый элемент содержит page_id и все нужные поля.
    """
    from datetime import date as _d, timedelta
    ds = (_d.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    pages = nq({"filter": {"and": [
        {"property": "\u0414\u0430\u0442\u0430 \u0437\u0430\u043f\u0438\u0441\u0438", "date":   {"equals": ds}},
        {"property": "\u0421\u0442\u0430\u0442\u0443\u0441",      "select": {"equals": "\u0417\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u043e"}},
    ]}})
    result = []
    for page in pages:
        pid = page["id"]
        p   = page.get("properties", {})
        try:
            chat_id = int(p["Chat ID"]["rich_text"][0]["text"]["content"])
            service = p["\u0423\u0441\u043b\u0443\u0433\u0430"]["select"]["name"]
            master  = p["\u041c\u0430\u0441\u0442\u0435\u0440"]["select"]["name"]
            t_slot  = p["\u0412\u0440\u0435\u043c\u044f"]["rich_text"][0]["text"]["content"]
            client  = p["\u041a\u043b\u0438\u0435\u043d\u0442"]["title"][0]["text"]["content"]
            result.append({
                "page_id": pid,
                "chat_id": chat_id,
                "service": service,
                "master":  master,
                "time":    t_slot,
                "date":    ds,
                "client":  client,
            })
        except Exception as ex:
            logger.warning(f"tomorrow_bookings: skip page {pid}: {ex}")
    return result


# ─── CRM: аналитика клиентов ──────────────────────────────────────────────────

def get_all_clients() -> list:
    """
    Возвращает все записи из базы Клиентов.
    Каждый элемент: dict с ключами name, phone, visits.
    """
    cdb = os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return []
    PROP_PHONE = "\u0422\u0435\u043b\u0435\u0444\u043e\u043d"   # Телефон
    PROP_NAME  = "\u0418\u043c\u044f"                            # Имя
    PROP_VIS   = "\u0412\u0438\u0437\u0438\u0442\u044b"          # Визиты
    results = _nreq(
        "POST",
        f"https://api.notion.com/v1/databases/{cdb}/query",
        json={"sorts": [{"property": PROP_VIS, "direction": "descending"}]}
    ).get("results", [])
    clients = []
    for page in results:
        p = page.get("properties", {})
        try:
            name    = p[PROP_NAME]["title"][0]["text"]["content"]
        except:
            name = "—"
        try:
            phone   = p[PROP_PHONE]["phone_number"] or "—"
        except:
            phone = "—"
        visits  = p.get(PROP_VIS, {}).get("number") or 0
        clients.append({"name": name, "phone": phone, "visits": visits})
    return clients


def get_clients_stats() -> dict:
    """
    Возвращает агрегированную статистику по базе Клиентов:
    total_clients, total_visits, top_clients (список топ-5).
    """
    clients = get_all_clients()
    total_clients = len(clients)
    total_visits  = sum(c["visits"] for c in clients)
    top_clients   = clients[:5]  # уже отсортированы по убыванию визитов
    return {
        "total_clients": total_clients,
        "total_visits":  total_visits,
        "top_clients":   top_clients,
    }


def get_catalog() -> dict:
    """
    Получает все услуги из базы Notion (DATABASE_ID).
    Ожидаемые поля: 'Название' (title), 'Цена' (number), 'Категория' (select).
    """
    results = nq({})  # Получаем все записи из базы
    categories_map = {}

    for page in results:
        props = page.get("properties", {})
        
        # Извлекаем название услуги
        name = ""
        if "Название" in props and props["Название"].get("title") and props["Название"]["title"]:
            name = props["Название"]["title"][0]["text"]["content"]
        elif "Услуга" in props:
            if props["Услуга"].get("select"):
                name = props["Услуга"]["select"]["name"]
            elif props["Услуга"].get("title") and props["Услуга"]["title"]:
                name = props["Услуга"]["title"][0]["text"]["content"]
        
        if not name: continue

        # Извлекаем цену
        price = 0
        if "Цена" in props:
            price = props["Цена"].get("number") or 0
        
        # Извлекаем категорию
        category = "Прочее"
        if "Категория" in props and props["Категория"].get("select"):
            category = props["Категория"]["select"]["name"]

        if category not in categories_map:
            categories_map[category] = []
        
        # Добавляем в категорию, если такой услуги еще нет
        if not any(s["name"] == name for s in categories_map[category]):
            categories_map[category].append({
                "name": name,
                "price": price
            })

    catalog = {"categories": []}
    for cat_name, services in categories_map.items():
        catalog["categories"].append({
            "name": cat_name,
            "services": services
        })
    
    return catalog
    