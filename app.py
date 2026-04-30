# app.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from notion_db import get_catalog, booked_slots
import uvicorn

app = FastAPI(title="Beauty Salon API")

# Настройка CORS для работы с Telegram Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/catalog")
async def fetch_catalog():
    """Возвращает каталог услуг из Notion."""
    try:
        return get_catalog()
    except Exception as e:
        return {"error": str(e), "categories": []}

@app.get("/api/slots")
async def fetch_slots(date: str = Query(...), master: str = Query("Любой")):
    """Возвращает список занятых слотов из Notion."""
    try:
        busy = list(booked_slots(date, master))
        return {"busy": busy}
    except Exception as e:
        return {"busy": [], "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
