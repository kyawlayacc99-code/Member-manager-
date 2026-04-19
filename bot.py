import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Update, BotCommand
from fastapi import FastAPI, Request, HTTPException
from config import BOT_TOKEN, WEBHOOK_URL, CRON_SECRET, ADMIN_USER_ID
import join
import callbacks
import admin                           # ✅ အသစ်ထည့်
from reminders import run_reminders
from reports import build_daily_report

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ✅ Order အရေးကြီး — admin ကို အရင်ထည့်၊ join ကို နောက်မှ
dp.include_router(admin.router)        # commands + /start
dp.include_router(callbacks.router)    # button clicks
dp.include_router(join.router)         # group join events (catch-all နောက်ဆုံး)

app = FastAPI()


@app.on_event("startup")
async def startup():
    await bot.set_webhook(
        f"{WEBHOOK_URL}/webhook",
        allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"],
        drop_pending_updates=True
    )
    await bot.set_my_commands([
        BotCommand(command="start", description="Start / Admin panel"),
        BotCommand(command="status", description="Your membership status"),
        BotCommand(command="members", description="Member list (admin)"),
        BotCommand(command="expiring", description="Expiring soon (admin)"),
        BotCommand(command="expired", description="Expired members (admin)"),
        BotCommand(command="today", description="Today's report (admin)"),
        BotCommand(command="search", description="Search member (admin)"),
        BotCommand(command="extend", description="Extend days (admin)"),
        BotCommand(command="add", description="Add member (admin)"),
        BotCommand(command="help", description="Help"),
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
