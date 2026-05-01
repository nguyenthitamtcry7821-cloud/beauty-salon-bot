"""
rebuild_notion_db.py — полностью перестраивает notion_db.py из project_dump.txt
"""
import re

ENC = "latin-1"

# Читаем оригинал из дампа
dump = open("project_dump.txt", "r", encoding="utf-8").read()
# Вырезаем notion_db.py из дампа (между === notion_db.py === и === main.py ===)
m = re.search(r"=== notion_db\.py \(\d+ chars\) ===\r?\n(.*?)\r?\n=== main\.py", dump, re.DOTALL)
if not m:
    print("ERROR: notion_db not found in dump")
    exit(1)

# Восстанавливаем оригинальный текст (убираем line numbers если есть)
original = m.group(1)
# Убираем артефакты переноса \r
original = original.replace("\r\n", "\n").replace("\r", "\n")

print(f"Original notion_db.py extracted: {len(original)} chars")
print("Functions found:", re.findall(r"def (\w+)\(", original))

# Добавляем новые блоки в конец

NEW_HELPERS = """

# --- Clients DB helpers (auto-added) ---
import os as _os

def _nq_clients(payload: dict) -> list:
    cdb = _os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return []
    return _nreq(
        "POST",
        f"https://api.notion.com/v1/databases/{cdb}/query",
        json=payload
    ).get("results", [])

def _nc_clients(payload: dict) -> dict:
    cdb = _os.environ.get("CLIENTS_DB_ID", "")
    if not cdb:
        return {}
    full_payload = {"parent": {"database_id": cdb}}
    full_payload.update(payload)
    return _nreq("POST", "https://api.notion.com/v1/pages", json=full_payload)

"""

# Поля в unicode escapes (совместимо с latin-1 при записи)
NEW_UPDATE = (
    "def update_client_visits(phone: str, name: str):\n"
    "    prop_phone = '\\u0422\\u0435\\u043b\\u0435\\u0444\\u043e\\u043d'\n"
    "    prop_name  = '\\u0418\\u043c\\u044f'\n"
    "    prop_vis   = '\\u0412\\u0438\\u0437\\u0438\\u0442\\u044b'\n"
    "    try:\n"
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

NEW_TODAY = (
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

# Патчим save_booking в оригинале — добавляем вызов update_client_visits
old_ret = '    return r.get("id", "")'
new_ret = (
    '    new_id = r.get("id", "")\n'
    '    if new_id and not page_id:  # only on new booking\n'
    '        try:\n'
    '            update_client_visits(data.get("phone", ""), data.get("name", ""))\n'
    '        except Exception as _ce:\n'
    '            logger.error(f"client_visits err: {_ce}")\n'
    '    return new_id'
)

if old_ret in original:
    original = original.replace(old_ret, new_ret, 1)
    print("[+] save_booking patched with update_client_visits call")
else:
    print("[WARN] save_booking return pattern not found")

# Убираем сломанную get_busy_slots (старую версию из первого прогона если есть)
# Оставляем только нормальную
if "def get_busy_slots(date: str" in original:
    print("[=] get_busy_slots (clean) already present")
elif "def get_busy_slots(date, master_name):" in original:
    print("[=] get_busy_slots (original) present")

# Собираем финальный файл
final = original + NEW_HELPERS + NEW_UPDATE + NEW_TODAY

# Проверяем что всё влезает в latin-1
try:
    final.encode(ENC)
    print("[OK] Encoding check passed (latin-1)")
except UnicodeEncodeError as e:
    print(f"[ERR] Encoding problem at pos {e.start}: {repr(final[e.start:e.start+20])}")
    # Найдём проблемные символы
    for i, ch in enumerate(final):
        try:
            ch.encode(ENC)
        except:
            print(f"  Bad char at {i}: U+{ord(ch):04X} = {repr(ch)} in context: {repr(final[i-5:i+5])}")
            if i > 100: break

open("notion_db.py", "w", encoding=ENC).write(final)
print(f"[OK] notion_db.py written ({len(final)} chars)")
print("Functions:", re.findall(r"def (\w+)\(", final))
