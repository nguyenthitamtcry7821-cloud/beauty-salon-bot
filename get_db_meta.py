import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

NH = {
    "Authorization":  f"Bearer {os.getenv('NOTION_TOKEN')}",
    "Content-Type":   "application/json",
    "Notion-Version": "2022-06-28",
}

def _nreq(method: str, url: str, **kw) -> dict:
    for i in range(5):
        try:
            r = requests.request(method, url, headers=NH, timeout=10, **kw)
            return r.json()
        except Exception as e:
            if i == 4: return {}
            time.sleep(2)
    return {}

db_id = os.getenv('DATABASE_ID')
res = _nreq("GET", f"https://api.notion.com/v1/databases/{db_id}")
import json
print(json.dumps(res, indent=2, ensure_ascii=False))
