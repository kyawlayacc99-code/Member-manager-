from datetime import date, timedelta
from db import supabase

def build_daily_report():
    today = date.today()
    d7 = today + timedelta(days=7)

    active = supabase.table("members").select("*").eq("status","active").execute().data

    expired, d1, d3, d7list, safe = [], [], [], [], []
    for m in active:
        exp = date.fromisoformat(m["expire_at"])
        left = (exp - today).days
        if left < 0:   expired.append(m)
        elif left == 0 or left == 1: d1.append(m)
        elif left <= 3: d3.append(m)
        elif left <= 7: d7list.append(m)
        else: safe.append(m)

    def fmt(lst):
        return "\n".join(
            f"• @{m['username'] or m['full_name']} — {m['expire_at']}"
            for m in lst
        ) or "_none_"

    return (
        f"📊 *Daily Report — {today}*\n\n"
        f"❌ *Expired ({len(expired)})*\n{fmt(expired)}\n\n"
        f"🔴 *≤1 day ({len(d1)})*\n{fmt(d1)}\n\n"
        f"🟠 *≤3 days ({len(d3)})*\n{fmt(d3)}\n\n"
        f"🟡 *≤7 days ({len(d7list)})*\n{fmt(d7list)}\n\n"
        f"🟢 *Safe ({len(safe)})*"
    )
