import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Update, BotCommand
from fastapi import FastAPI, Request, HTTPException
from config import BOT_TOKEN, WEBHOOK_URL, CRON_SECRET, ADMIN_USER_ID
from bot.handlers import join, callbacks  # + admin, member
from bot.services.reminders import run_reminders
from bot.services.reports import build_daily_report

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
dp.include_router(join.router)
dp.include_router(callbacks.router)
# dp.include_router(admin.router) ...

app = FastAPI()

@app.on_event("startup")
async def startup():
    await bot.set_webhook(
        f"{WEBHOOK_URL}/webhook",
        allowed_updates=["message","callback_query","chat_member","my_chat_member"]
    )
    await bot.set_my_commands([
        BotCommand(command="start", description="Start"),
        BotCommand(command="members", description="Member list"),
        BotCommand(command="expiring", description="Expiring soon"),
        BotCommand(command="today", description="Today report"),
    ])

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/cron/daily")
async def cron_daily(secret: str):
    if secret != CRON_SECRET:
        raise HTTPException(403)
    await run_reminders(bot)
    report = build_daily_report()
    await bot.send_message(ADMIN_USER_ID, report, parse_mode="Markdown")
    return {"ok": True}

@app.get("/")
async def health():
    return {"status": "ok"}
