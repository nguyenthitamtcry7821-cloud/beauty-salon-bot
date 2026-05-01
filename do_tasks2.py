"""
do_tasks2.py — патч с ASCII-only новым кодом (latin-1 совместимый)
"""
import os, requests
from dotenv import load_dotenv

load_dotenv()
NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
DATABASE_ID    = os.getenv("DATABASE_ID")
CLIENTS_DB_ID  = os.getenv("CLIENTS_DB_ID", "")
ENC = "latin-1"

NH = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Content-Type":   "application/json",
    "Notion-Version": "2022-06-28",
}

# ─── Читаем файлы ────────────────────────────────────────────────────────────
notion_path = "notion_db.py"
main_path   = "main.py"

content_ndb  = open(notion_path, "r", encoding=ENC).read()
content_main = open(main_path,   "r", encoding=ENC).read()

# ─── PATCH notion_db.py ──────────────────────────────────────────────────────
print("=== PATCH notion_db.py ===")

# 1. import os
if "import os" not in content_ndb:
    content_ndb = content_ndb.replace("import requests", "import os\nimport requests", 1)
    print("[+] import os")

# 2. Новые функции (ASCII-only строки!)
NEW_NDB = """

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

"""

# Имена полей в latin-1 байтах (как они есть в файле)
# Поля нашей базы Clients — ASCII: "Imya", "Telefon", "Vizity"
# НО мы используем ASCII-совместимое — пишем прямо байтами через escape

NEW_UPDATE_FUNC = (
    "def update_client_visits(phone: str, name: str):\n"
    "    try:\n"
    "        prop_phone = '\\u0422\\u0435\\u043b\\u0435\\u0444\\u043e\\u043d'\n"
    "        prop_name  = '\\u0418\\u043c\\u044f'\n"
    "        prop_vis   = '\\u0412\\u0438\\u0437\\u0438\\u0442\\u044b'\n"
    "        results = _nq_clients({'filter': {'property': prop_phone, 'phone_number': {'equals': phone}}})\n"
    "        if results:\n"
    "            pid = results[0]['id']\n"
    "            cur = results[0]['properties'].get(prop_vis, {}).get('number') or 0\n"
    "            _nreq('PATCH', f'https://api.notion.com/v1/pages/{pid}',\n"
    "                  json={'properties': {prop_vis: {'number': cur + 1}}})\n"
    "            logger.info(f'Client {phone}: visits {cur} -> {cur + 1}')\n"
    "        else:\n"
    "            _nc_clients({'properties': {\n"
    "                prop_name:  {'title':        [{'text': {'content': name}}]},\n"
    "                prop_phone: {'phone_number': phone},\n"
    "                prop_vis:   {'number':       1},\n"
    "            }})\n"
    "            logger.info(f'New client created: {name} {phone}')\n"
    "    except Exception as e:\n"
    "        logger.error(f'update_client_visits error: {e}')\n"
)

marker = "def get_busy_slots("
if "def update_client_visits" not in content_ndb:
    if marker in content_ndb:
        idx = content_ndb.find(marker)
        content_ndb = content_ndb[:idx] + NEW_NDB + NEW_UPDATE_FUNC + "\n\n" + content_ndb[idx:]
    else:
        content_ndb = content_ndb + NEW_NDB + NEW_UPDATE_FUNC
    print("[+] update_client_visits + helpers added")
else:
    print("[=] update_client_visits already present")

# 3. Вызов в save_booking
old_ret = '    return r.get("id", "")'
new_ret = (
    '    new_id = r.get("id", "")\n'
    '    if new_id and not page_id:  # only on new booking, not reschedule\n'
    '        try:\n'
    '            update_client_visits(data.get("phone", ""), data.get("name", ""))\n'
    '        except Exception as _ce:\n'
    '            logger.error(f"client_visits err: {_ce}")\n'
    '    return new_id'
)

save_block = content_ndb.split("def save_booking(")[1].split("\ndef ")[0] if "def save_booking(" in content_ndb else ""
if "update_client_visits" not in save_block:
    content_ndb = content_ndb.replace(old_ret, new_ret, 1)
    print("[+] update_client_visits call injected into save_booking")
else:
    print("[=] call already in save_booking")

# 4. today_bookings
TODAY_FUNC = (
    "\n\ndef today_bookings() -> list:\n"
    "    from datetime import date as _d\n"
    "    ds = _d.today().strftime('%Y-%m-%d')\n"
    "    prop_date   = '\\u0414\\u0430\\u0442\\u0430 \\u0437\\u0430\\u043f\\u0438\\u0441\\u0438'\n"
    "    prop_status = '\\u0421\\u0442\\u0430\\u0442\\u0443\\u0441'\n"
    "    prop_val    = '\\u0417\\u0430\\u043f\\u043b\\u0430\\u043d\\u0438\\u0440\\u043e\\u0432\\u0430\\u043d\\u043e'\n"
    "    return nq({'filter': {'and': [\n"
    "        {'property': prop_date,   'date':   {'equals': ds}},\n"
    "        {'property': prop_status, 'select': {'equals': prop_val}},\n"
    "    ]}})\n"
)

if "def today_bookings" not in content_ndb:
    content_ndb += TODAY_FUNC
    print("[+] today_bookings added")
else:
    print("[=] today_bookings already present")

open(notion_path, "w", encoding=ENC).write(content_ndb)
print("[OK] notion_db.py saved")

# ─── PATCH main.py ───────────────────────────────────────────────────────────
print()
print("=== PATCH main.py ===")

# 1. Добавляем today_bookings в import
if "today_bookings" not in content_main:
    old_imp = "auto_close_past_bookings\n)"
    new_imp = "auto_close_past_bookings, today_bookings\n)"
    if old_imp in content_main:
        content_main = content_main.replace(old_imp, new_imp, 1)
        print("[+] today_bookings imported")
    else:
        # fallback: ищем строку с auto_close_past_bookings в импорте
        content_main = content_main.replace(
            "auto_close_past_bookings\n)",
            "auto_close_past_bookings, today_bookings\n)", 1
        )
        print("[+] today_bookings import (fallback)")
else:
    print("[=] today_bookings already imported")

# 2. Добавляем callback-обработчик ADM|stats
ADM_CB = """
@bot.callback_query_handler(func=lambda c: c.data.startswith("ADM|"))
def cb_adm(call):
    cid = call.message.chat.id
    if cid not in ADMIN_IDS:
        return bot.answer_callback_query(call.id, "No access.")
    action = call.data.split("|")[1]
    if action == "stats":
        from datetime import date as _td
        ds = _td.today().strftime("%d.%m.%Y")
        pages = today_bookings()
        if not pages:
            text = f"* ({ds}):*\\n\\n."
        else:
            prop_time    = '\\u0412\\u0440\\u0435\\u043c\\u044f'
            prop_service = '\\u0423\\u0441\\u043b\\u0443\\u0433\\u0430'
            prop_master  = '\\u041c\\u0430\\u0441\\u0442\\u0435\\u0440'
            prop_client  = '\\u041a\\u043b\\u0438\\u0435\\u043d\\u0442'
            lines = [f"* ({ds}):*\\n"]
            for page in pages:
                p = page["properties"]
                try:
                    t   = p[prop_time]["rich_text"][0]["text"]["content"]
                    svc = p[prop_service]["select"]["name"]
                    mst = p[prop_master]["select"]["name"]
                    cli = p[prop_client]["title"][0]["text"]["content"]
                    lines.append(f"- {t} | {cli} | {svc} ({mst})")
                except: pass
            text = "\\n".join(lines)
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
"""

if "def cb_adm(" not in content_main:
    # Вставляем перед блоком ЗАПУСК
    launch_marker = 'if __name__ == "__main__":'
    idx = content_main.rfind(launch_marker)
    if idx != -1:
        content_main = content_main[:idx] + ADM_CB + "\n" + content_main[idx:]
        print("[+] cb_adm handler added before __main__")
    else:
        content_main += "\n" + ADM_CB
        print("[+] cb_adm handler added at end")
else:
    print("[=] cb_adm already present")

open(main_path, "w", encoding=ENC).write(content_main)
print("[OK] main.py saved")

print()
print("=== ALL DONE ===")
