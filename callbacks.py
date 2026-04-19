from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from members import extend_member
from db import supabase
from config import ADMIN_USER_ID, GROUP_ID
from reports import build_daily_report

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID


def member_detail_kb(member_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="+7d", callback_data=f"ext:{member_id}:7"),
            InlineKeyboardButton(text="+30d", callback_data=f"ext:{member_id}:30"),
            InlineKeyboardButton(text="+60d", callback_data=f"ext:{member_id}:60"),
        ],
        [
            InlineKeyboardButton(text="+90d", callback_data=f"ext:{member_id}:90"),
            InlineKeyboardButton(text="🗑 Remove", callback_data=f"remove:{member_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="menu:members"),
        ],
    ])


# ===== EXTEND button =====
@router.callback_query(F.data.startswith("ext:"))
async def handle_extend(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Not allowed", show_alert=True)
        return

    _, member_id, days = cb.data.split(":")
    new_expire = extend_member(int(member_id), int(days), cb.from_user.id)
    await cb.answer(f"✅ Extended {days} days")
    try:
        await cb.message.edit_text(
            (cb.message.text or "") + f"\n\n✅ Extended +{days}d → {new_expire}",
            reply_markup=None
        )
    except Exception:
        pass


# ===== VIEW member =====
@router.callback_query(F.data.startswith("view:"))
async def handle_view(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Not allowed", show_alert=True)
        return

    member_id = int(cb.data.split(":")[1])
    r = supabase.table("members").select("*").eq("id", member_id).single().execute()
    m = r.data
    today = date.today()
    left = (date.fromisoformat(m["expire_at"]) - today).days

    text = (
        f"👤 *{m['full_name'] or 'Unknown'}*\n"
        f"🔗 @{m['username'] or '—'}\n"
        f"🆔 `{m['telegram_user_id']}`\n\n"
        f"📅 Joined: {m['joined_at']}\n"
        f"⌛ Expires: {m['expire_at']}\n"
        f"⏱ Days left: {left}\n"
        f"📊 Status: {m['status']}\n"
        f"💬 DM: {'✅' if m['dm_available'] else '❌ (not started bot)'}"
    )
    await cb.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=member_detail_kb(member_id)
    )
    await cb.answer()


# ===== REMOVE =====
@router.callback_query(F.data.startswith("remove:"))
async def handle_remove(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Not allowed", show_alert=True)
        return

    member_id = int(cb.data.split(":")[1])
    r = supabase.table("members").select("*").eq("id", member_id).single().execute()
    m = r.data

    # Telegram group ကနေ ban + unban (kick effect)
    try:
        await cb.bot.ban_chat_member(GROUP_ID, m["telegram_user_id"])
        await cb.bot.unban_chat_member(GROUP_ID, m["telegram_user_id"])
    except Exception as e:
        await cb.answer(f"Kick failed: {e}", show_alert=True)

    # DB update
    supabase.table("members").update({"status": "removed"}) \
        .eq("id", member_id).execute()

    await cb.answer("✅ Removed from group")
    await cb.message.edit_text(
        (cb.message.text or "") + "\n\n🗑 Removed.",
        reply_markup=None
    )


# ===== MAIN MENU navigation =====
@router.callback_query(F.data.startswith("menu:"))
async def handle_menu(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Not allowed", show_alert=True)
        return

    action = cb.data.split(":")[1]
    today = date.today()

    if action == "today":
        report = build_daily_report()
        await cb.message.edit_text(report, parse_mode="Markdown")

    elif action == "expiring":
        d7 = today + timedelta(days=7)
        r = supabase.table("members").select("*") \
            .eq("status", "active") \
            .lte("expire_at", d7.isoformat()) \
            .gte("expire_at", today.isoformat()) \
            .order("expire_at").execute()
        if not r.data:
            await cb.message.edit_text("✅ No one expiring in 7 days.")
        else:
            lines = ["⏰ *Expiring Soon*\n"]
            buttons = []
            for m in r.data:
                name = m['username'] or m['full_name']
                left = (date.fromisoformat(m["expire_at"]) - today).days
                lines.append(f"• @{name} — {m['expire_at']} ({left}d)")
                buttons.append([InlineKeyboardButton(
                    text=f"@{name}",
                    callback_data=f"view:{m['id']}"
                )])
            await cb.message.edit_text(
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )

    elif action == "expired":
        r = supabase.table("members").select("*") \
            .lt("expire_at", today.isoformat()).execute()
        if not r.data:
            await cb.message.edit_text("✅ No expired members.")
        else:
            lines = ["❌ *Expired*\n"]
            buttons = []
            for m in r.data:
                name = m['username'] or m['full_name']
                lines.append(f"• @{name} — {m['expire_at']}")
                buttons.append([InlineKeyboardButton(
                    text=f"@{name}",
                    callback_data=f"view:{m['id']}"
                )])
            await cb.message.edit_text(
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )

    elif action == "members":
        per_page = 10
        r = supabase.table("members").select("*") \
            .order("expire_at").range(0, per_page - 1).execute()
        lines = [f"👥 *Members*\n"]
        buttons = []
        for m in r.data:
            left = (date.fromisoformat(m["expire_at"]) - today).days
            emoji = "🟢" if left > 7 else "🟡" if left > 3 else "🟠" if left > 0 else "🔴"
            name = m['username'] or m['full_name']
            lines.append(f"{emoji} @{name} — {m['expire_at']}")
            buttons.append([InlineKeyboardButton(
                text=f"{emoji} @{name}",
                callback_data=f"view:{m['id']}"
            )])
        await cb.message.edit_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    elif action == "search":
        await cb.message.edit_text(
            "🔍 Type `/search <name>` to find a member.",
            parse_mode="Markdown"
        )

    await cb.answer()
