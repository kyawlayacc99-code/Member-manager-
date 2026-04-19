from datetime import date, timedelta
from bot.db import supabase

def get_default_plan_days() -> int:
    r = supabase.table("bot_settings").select("value").eq("key","default_plan_days").single().execute()
    return int(r.data["value"])

def upsert_member_on_join(user_id: int, username: str | None, full_name: str):
    existing = supabase.table("members").select("*").eq("telegram_user_id", user_id).execute()
    if existing.data:
        # already exists — just update status if needed
        return existing.data[0], False

    days = get_default_plan_days()
    today = date.today()
    expire = today + timedelta(days=days)
    new = {
        "telegram_user_id": user_id,
        "username": username,
        "full_name": full_name,
        "joined_at": today.isoformat(),
        "expire_at": expire.isoformat(),
        "plan_days": days,
        "status": "active",
    }
    r = supabase.table("members").insert(new).execute()
    return r.data[0], True

def extend_member(member_id: int, days: int, admin_id: int):
    m = supabase.table("members").select("*").eq("id", member_id).single().execute().data
    old_expire = date.fromisoformat(m["expire_at"])
    base = max(old_expire, date.today())   # don't extend from a past date
    new_expire = base + timedelta(days=days)

    supabase.table("members").update({
        "expire_at": new_expire.isoformat(),
        "status": "active",
        "updated_at": "now()"
    }).eq("id", member_id).execute()

    supabase.table("admin_actions").insert({
        "member_id": member_id,
        "action_type": "extend",
        "old_value": m["expire_at"],
        "new_value": new_expire.isoformat(),
        "changed_by": admin_id
    }).execute()
    return new_expire

def set_expire_date(member_id: int, new_date: date, admin_id: int):
    m = supabase.table("members").select("*").eq("id", member_id).single().execute().data
    supabase.table("members").update({
        "expire_at": new_date.isoformat(),
        "status": "active" if new_date >= date.today() else "expired",
        "updated_at": "now()"
    }).eq("id", member_id).execute()
    supabase.table("admin_actions").insert({
        "member_id": member_id,
        "action_type": "set_date",
        "old_value": m["expire_at"],
        "new_value": new_date.isoformat(),
        "changed_by": admin_id
    }).execute()
