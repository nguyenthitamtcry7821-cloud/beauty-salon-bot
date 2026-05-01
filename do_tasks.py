"""
do_tasks.py — выполняет все задачи Директора:
1. Создаёт базу «Клиенты» в Notion (если её нет)
2. Патчит notion_db.py: при сохранении визита обновляет счётчик в «Клиентах»
3. Патчит main.py: в выгрузке записей добавляет фильтр по сегодняшней дате
"""

import os, sys, requests, json
from dotenv import load_dotenv

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID  = os.getenv("DATABASE_ID")  # основная БД записей
ENC = "latin-1"

NH = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Content-Type":   "application/json",
    "Notion-Version": "2022-06-28",
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. СОЗДАНИЕ / ПОИСК БАЗЫ «Клиенты»
# ─────────────────────────────────────────────────────────────────────────────

def get_parent_page_id():
    """Берём parent page из основной БД (чтобы создать рядом)."""
    r = requests.get(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}",
        headers=NH, timeout=10
    ).json()
    parent = r.get("parent", {})
    if parent.get("type") == "page_id":
        return parent["page_id"]
    if parent.get("type") == "workspace":
        return None
    return None

def find_clients_db():
    """Ищем базу с title «Клиенты» через search API."""
    r = requests.post(
        "https://api.notion.com/v1/search",
        headers=NH,
        json={"query": "Клиенты", "filter": {"value": "database", "property": "object"}},
        timeout=10
    ).json()
    for item in r.get("results", []):
        titles = item.get("title", [])
        for t in titles:
            if t.get("plain_text", "").strip() == "Клиенты":
                return item["id"]
    return None

def create_clients_db(parent_page_id):
    """Создаём базу «Клиенты» с полями Имя, Телефон, Визиты."""
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "Клиенты"}}],
        "properties": {
            "Имя":     {"title": {}},
            "Телефон": {"phone_number": {}},
            "Визиты":  {"number": {"format": "number"}},
        }
    }
    r = requests.post(
        "https://api.notion.com/v1/databases",
        headers=NH, json=payload, timeout=10
    ).json()
    if "id" in r:
        print(f"[OK] База «Клиенты» создана: {r['id']}")
        return r["id"]
    else:
        print(f"[ERR] Не удалось создать базу: {r}")
        return None

print("=" * 60)
print("ЗАДАЧА 1: База «Клиенты»")
print("=" * 60)

clients_db_id = find_clients_db()
if clients_db_id:
    print(f"[OK] База «Клиенты» уже существует: {clients_db_id}")
else:
    parent_pid = get_parent_page_id()
    if parent_pid:
        clients_db_id = create_clients_db(parent_pid)
    else:
        # Нет parent page — создаём inline в workspace через основную страницу
        # Попробуем через workspace root
        payload = {
            "parent": {"type": "workspace", "workspace": True},
            "title": [{"type": "text", "text": {"content": "Клиенты"}}],
            "properties": {
                "Имя":     {"title": {}},
                "Телефон": {"phone_number": {}},
                "Визиты":  {"number": {"format": "number"}},
            }
        }
        r = requests.post(
            "https://api.notion.com/v1/databases",
            headers=NH, json=payload, timeout=10
        ).json()
        if "id" in r:
            clients_db_id = r["id"]
            print(f"[OK] База «Клиенты» создана в workspace: {clients_db_id}")
        else:
            print(f"[WARN] Не удалось создать в workspace: {r.get('message','')}")
            clients_db_id = None

if not clients_db_id:
    print("[WARN] Продолжаем без CLIENTS_DB_ID — добавьте его в .env вручную после")

# Записываем CLIENTS_DB_ID в .env
if clients_db_id:
    env_path = ".env"
    env_content = open(env_path, "r", encoding="utf-8").read()
    if "CLIENTS_DB_ID" not in env_content:
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f"\nCLIENTS_DB_ID={clients_db_id}\n")
        print(f"[OK] CLIENTS_DB_ID={clients_db_id} добавлен в .env")
    else:
        print("[OK] CLIENTS_DB_ID уже есть в .env")

# ─────────────────────────────────────────────────────────────────────────────
# 2. ПАТЧ notion_db.py — логика счётчика Визиты
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 60)
print("ЗАДАЧА 2: Патч notion_db.py")
print("=" * 60)

NEW_FUNCTIONS = '''

# ────────────────────────────────────────────────────────────────
# БАЗА «КЛИЕНТЫ» — поиск и обновление счётчика визитов
# ────────────────────────────────────────────────────────────────

def _nq_clients(payload: dict) -> list:
    """Запрос к базе Клиентов."""
    cdb = os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return []
    return _nreq(
        "POST",
        f"https://api.notion.com/v1/databases/{cdb}/query",
        json=payload
    ).get("results", [])

def _nc_clients(payload: dict) -> dict:
    """Создание записи в базе Клиентов."""
    cdb = os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return {}
    full_payload = {"parent": {"database_id": cdb}}
    full_payload.update(payload)
    return _nreq("POST", "https://api.notion.com/v1/pages", json=full_payload)

def update_client_visits(phone: str, name: str):
    """
    Ищет клиента по телефону в базе «Клиенты».
    Найден  → прибавляет +1 к полю Визиты.
    Не найден → создаёт новую запись с Визиты = 1.
    """
    try:
        results = _nq_clients({
            "filter": {"property": "Телефон", "phone_number": {"equals": phone}}
        })
        if results:
            pid = results[0]["id"]
            cur = results[0]["properties"].get("Визиты", {}).get("number") or 0
            _nreq("PATCH", f"https://api.notion.com/v1/pages/{pid}",
                  json={"properties": {"Визиты": {"number": cur + 1}}})
            logger.info(f"Клиент {phone}: Визиты {cur} -> {cur + 1}")
        else:
            _nc_clients({"properties": {
                "Имя":     {"title":        [{"text": {"content": name}}]},
                "Телефон": {"phone_number": phone},
                "Визиты":  {"number":       1},
            }})
            logger.info(f"Новый клиент создан: {name} {phone}")
    except Exception as e:
        logger.error(f"Ошибка update_client_visits: {e}")
'''

notion_path = "notion_db.py"
content = open(notion_path, "r", encoding=ENC).read()

# Добавляем import os если его нет
if "import os" not in content:
    content = content.replace("import requests", "import os\nimport requests", 1)
    print("[OK] Добавлен import os")

# Вставляем новые функции ПЕРЕД get_busy_slots (или в конец если нет)
marker = "def get_busy_slots("
if marker in content:
    idx = content.find(marker)
    content = content[:idx] + NEW_FUNCTIONS + "\n" + content[idx:]
    print("[OK] Новые функции вставлены перед get_busy_slots")
else:
    content = content + NEW_FUNCTIONS
    print("[OK] Новые функции добавлены в конец файла")

# Добавляем вызов update_client_visits в save_booking
# Ищем место после save_booking создаёт запись
old_save_end = "    return r.get(\"id\", \"\")"
new_save_end = (
    "    new_id = r.get(\"id\", \"\")\n"
    "    # Обновляем счётчик визитов в базе «Клиенты»\n"
    "    if new_id:\n"
    "        try:\n"
    "            update_client_visits(data.get(\"phone\", \"\"), data.get(\"name\", \"\"))\n"
    "        except Exception as _e:\n"
    "            logger.error(f\"update_client_visits error: {_e}\")\n"
    "    return new_id"
)

if old_save_end in content and "update_client_visits" not in content.split("def save_booking")[1].split("def ")[0]:
    content = content.replace(old_save_end, new_save_end, 1)
    print("[OK] Вызов update_client_visits добавлен в save_booking")
else:
    print("[WARN] update_client_visits уже есть в save_booking или паттерн не найден")

open(notion_path, "w", encoding=ENC).write(content)
print("[OK] notion_db.py сохранён")

# ─────────────────────────────────────────────────────────────────────────────
# 3. ПАТЧ main.py — фильтр «сегодня» в выгрузке admin
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 60)
print("ЗАДАЧА 3: Патч main.py — фильтр по сегодняшней дате")
print("=" * 60)

# Добавляем функцию today_bookings в notion_db и используем её в main.py
# Сначала добавляем в notion_db.py

content_ndb = open(notion_path, "r", encoding=ENC).read()
today_func = '''

def today_bookings() -> list:
    """Возвращает все записи со статусом 'Запланировано' на сегодня."""
    from datetime import date as _date
    ds = _date.today().strftime("%Y-%m-%d")
    return nq({"filter": {"and": [
        {"property": "Дата записи", "date":   {"equals": ds}},
        {"property": "Статус",      "select": {"equals": "Запланировано"}},
    ]}})
'''

if "def today_bookings" not in content_ndb:
    content_ndb += today_func
    open(notion_path, "w", encoding=ENC).write(content_ndb)
    print("[OK] Функция today_bookings добавлена в notion_db.py")
else:
    print("[OK] today_bookings уже есть в notion_db.py")

# Патчим main.py
main_path = "main.py"
content_main = open(main_path, "r", encoding=ENC).read()

# Добавляем today_bookings в импорт из notion_db
old_import = "    auto_close_past_bookings\n)"
new_import = "    auto_close_past_bookings, today_bookings\n)"

if "today_bookings" not in content_main:
    if old_import in content_main:
        content_main = content_main.replace(old_import, new_import, 1)
        print("[OK] today_bookings добавлена в import из notion_db")
    else:
        print("[WARN] Паттерн импорта не найден точно — ищем по частям")
        content_main = content_main.replace(
            "auto_close_past_bookings\n)",
            "auto_close_past_bookings, today_bookings\n)", 1
        )
else:
    print("[OK] today_bookings уже импортирована в main.py")

# Находим обработчик /admin и добавляем кнопку «Сегодня»
# Ищем callback ADM|stats и добавляем туда вывод today_bookings

old_adm_block = '''@bot.callback_query_handler(func=lambda c: c.data.startswith("ADM|"))'''

adm_handler_new = '''@bot.callback_query_handler(func=lambda c: c.data.startswith("ADM|"))
def cb_adm(call):
    cid = call.message.chat.id
    if cid not in ADMIN_IDS:
        return bot.answer_callback_query(call.id, "Нет доступа.")
    action = call.data.split("|")[1]
    if action == "stats":
        from datetime import date as _today_date
        ds = _today_date.today().strftime("%d.%m.%Y")
        pages = today_bookings()
        if not pages:
            text = f"📋 *Записи на сегодня ({ds}):*\\n\\nЗаписей нет."
        else:
            lines = [f"📋 *Записи на сегодня ({ds}):*\\n"]
            for page in pages:
                p = page["properties"]
                try:
                    t   = p["Время"]["rich_text"][0]["text"]["content"]
                    svc = p["Услуга"]["select"]["name"]
                    mst = p["Мастер"]["select"]["name"]
                    cli = p["Клиент"]["title"][0]["text"]["content"]
                    lines.append(f"• {t} — {cli} | {svc} ({mst})")
                except: pass
            text = "\\n".join(lines)
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
'''

# Проверяем — есть ли уже cb_adm
if "def cb_adm(" not in content_main:
    # Ищем место после cmd_admin
    insert_after = "@bot.message_handler(commands=[\"admin\"])"
    idx = content_main.find(insert_after)
    if idx != -1:
        # Найдём конец этой функции (следующий @bot или # ===)
        # Вставим наш handler ПОСЛЕ функции cmd_admin
        # Ищем следующий блок после cmd_admin
        block_end_marker = "\n# ============"
        next_block = content_main.find(block_end_marker, idx)
        if next_block != -1:
            content_main = (
                content_main[:next_block]
                + "\n" + adm_handler_new
                + content_main[next_block:]
            )
            print("[OK] Обработчик cb_adm добавлен в main.py")
        else:
            content_main += "\n" + adm_handler_new
            print("[OK] Обработчик cb_adm добавлен в конец main.py")
    else:
        content_main += "\n" + adm_handler_new
        print("[OK] Обработчик cb_adm добавлен в конец main.py")
else:
    print("[OK] cb_adm уже существует в main.py")

open(main_path, "w", encoding=ENC).write(content_main)
print("[OK] main.py сохранён")

# ─────────────────────────────────────────────────────────────────────────────
# ИТОГ
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("ВСЕ ЗАДАЧИ ВЫПОЛНЕНЫ")
print("=" * 60)
if clients_db_id:
    print(f"CLIENTS_DB_ID = {clients_db_id}")
print("Перезапуск бота...")
