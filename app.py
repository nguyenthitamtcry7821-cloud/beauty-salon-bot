# app.py
import os
import json
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from telebot import types
import uvicorn
from dotenv import load_dotenv

# Импорты
from notion_db import get_catalog, booked_slots, save_booking, auto_close_past_bookings
from main import bot 
import asyncio

load_dotenv()

app = FastAPI(title="Beauty Salon API")

async def background_worker():
    while True:
        try:
            auto_close_past_bookings()
        except Exception as e:
            print(f"Worker error: {e}")
        await asyncio.sleep(1800)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_worker())
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    print(f"DEBUG WEBHOOK_URL='{webhook_url}'")
    if webhook_url:
        bot.remove_webhook()
        bot.set_webhook(url=f"{webhook_url}/webhook")
        print(f"✅ Webhook: {webhook_url}/webhook")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return FileResponse("webapp/index.html")

@app.get("/api/catalog")
async def fetch_catalog():
    return get_catalog()

@app.get("/api/slots")
async def fetch_slots(date: str = Query(...), master: str = Query("Любой")):
    busy = list(booked_slots(date, master))
    return {"busy": busy}

@app.post("/api/book")
async def book_service(request: Request):
    data = await request.json()
    booking_id = save_booking(data)
    
    msg = f"✅ *Запись подтверждена!*\n\nУслуга: {data['service']}\nДата: {data['date']} в {data['time']}"
    bot.send_message(data['chat_id'], msg, parse_mode="Markdown")
    
    return {"success": True, "booking_id": booking_id}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    if request.headers.get('content-type') == 'application/json':
        json_string = await request.body()
        update = types.Update.de_json(json_string.decode('utf-8'))
        bot.process_new_updates([update])
        return {"status": "ok"}
    return {"status": "error"}

app.mount("/", StaticFiles(directory="webapp", html=True), name="webapp")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
