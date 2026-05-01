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
            print(f"Attempt {i+1} failed: {e}")
            if i == 4: return {}
            time.sleep(2)
    return {}

db_id = os.getenv('DATABASE_ID')
print(f"Querying DB: {db_id}")
res = _nreq("POST", f"https://api.notion.com/v1/databases/{db_id}/query", json={"page_size": 5})
print(res)
