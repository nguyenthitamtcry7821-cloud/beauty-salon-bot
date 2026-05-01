import os
import requests
from dotenv import load_dotenv

load_dotenv()

NH = {
    "Authorization":  f"Bearer {os.getenv('NOTION_TOKEN')}",
    "Content-Type":   "application/json",
    "Notion-Version": "2022-06-28",
}

db_id = os.getenv('DATABASE_ID')
r = requests.get(f"https://api.notion.com/v1/databases/{db_id}", headers=NH)
print(r.json())
