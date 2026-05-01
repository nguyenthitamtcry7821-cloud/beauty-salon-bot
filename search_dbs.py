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

res = _nreq("POST", "https://api.notion.com/v1/search", json={"filter": {"value": "database", "property": "object"}})
import json
print(json.dumps(res, indent=2, ensure_ascii=False))
