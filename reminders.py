from datetime import date
from bot.db import supabase
from bot.config import GROUP_ID

REMIND_DAYS = [7, 3, 1, 0]

async def run_reminders(bot):
    today = date.today()
    members = supabase.table("members").select("*").eq("status","active").execute().data
    for m in members:
        left = (date.fromisoformat(m["expire_at"]) - today).days
        if left not in REMIND_DAYS:
            continue
        if not m["dm_available"]:
            continue
        try:
            await bot.send_message(
                m["telegram_user_id"],
                f"⏰ Reminder\n\nYour access expires in *{left} day(s)* "
                f"on *{m['expire_at']}*.\n\nRenew to keep your eBook group access.",
                parse_mode="Markdown"
            )
            supabase.table("reminder_logs").insert({
                "member_id": m["id"],
                "reminder_type": f"{left}d",
                "sent_to": "dm",
                "success": True,
            }).execute()
        except Exception as e:
            supabase.table("reminder_logs").insert({
                "member_id": m["id"],
                "reminder_type": f"{left}d",
                "sent_to": "dm",
                "success": False,
                "error": str(e),
            }).execute()
