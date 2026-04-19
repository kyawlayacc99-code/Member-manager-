from datetime import date, timedelta
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from db import supabase
from config import ADMIN_USER_ID
from reports import build_daily_report

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID


def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Members", callback_data="menu:members"),
            InlineKeyboardButton(text="⏰ Expiring", callback_data="menu:expiring"),
        ],
        [
            InlineKeyboardButton(text="❌ Expired", callback_data="menu:expired"),
            InlineKeyboardButton(text="📊 Today", callback_data="menu:today"),
        ],
        [
            InlineKeyboardButton(text="🔍 Search", callback_data="menu:search"),
        ],
    ])


# ===== /start =====
@router.message(CommandStart())
async def cmd_start(msg: Message):
    # member က /start နှိပ်ရင် dm_available = true လုပ်ပေး
    if not is_admin(msg.from_user.id):
        supabase.table("members").update({"dm_available": True}) \
            .eq("telegram_user_id", msg.from_user.id).execute()
        
        # သူ့ status ပြပေး
        r = supabase.table("members").select("*") \
            .eq("telegram_user_id", msg.from_user.id).execute()
        if r.data:
            m = r.data[0]
            await msg.answer(
                f"👋 Welcome!\n\n"
                f"📅 Joined: {m['joined_at']}\n"
                f"⌛ Expires: {m['expire_at']}\n"
                f"📊 Status: {m['status']}\n\n"
                f"✅ You'll receive renewal reminders here."
            )
        else:
            await msg.answer("👋 Hello! You're not in our member list yet.")
        return

    # Admin panel
    await msg.answer(
        "🎛 *Admin Panel*\n\nChoose an action:",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )


# ===== /members =====
@router.message(Command("members"))
async def cmd_members(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    await show_members_list(msg, page=0)


async def show_members_list(msg_or_cb, page: int = 0):
    per_page = 10
    offset = page * per_page
    r = supabase.table("members").select("*") \
        .order("expire_at", desc=False) \
        .range(offset, offset + per_page - 1).execute()

    if not r.data:
        text = "No members found."
        kb = None
    else:
        today = date.today()
        lines = [f"👥 *Members (page {page+1})*\n"]
        buttons = []
        for m in r.data:
            left = (date.fromisoformat(m["expire_at"]) - today).days
            emoji = "🟢" if left > 7 else "🟡" if left > 3 else "🟠" if left > 0 else "🔴"
            name = m['username'] or m['full_name'] or str(m['telegram_user_id'])
            lines.append(f"{emoji} @{name} — {m['expire_at']} ({left}d)")
            buttons.append([InlineKeyboardButton(
                text=f"{emoji} @{name}",
                callback_data=f"view:{m['id']}"
            )])

        # Pagination
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"page:{page-1}"))
        if len(r.data) == per_page:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"page:{page+1}"))
        if nav:
            buttons.append(nav)

        text = "\n".join(lines)
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if isinstance(msg_or_cb, Message):
        await msg_or_cb.answer(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await msg_or_cb.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)


# ===== /expiring =====
@router.message(Command("expiring"))
async def cmd_expiring(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    today = date.today()
    d7 = today + timedelta(days=7)
    r = supabase.table("members").select("*") \
        .eq("status", "active") \
        .lte("expire_at", d7.isoformat()) \
        .gte("expire_at", today.isoformat()) \
        .order("expire_at", desc=False).execute()

    if not r.data:
        await msg.answer("✅ No members expiring in the next 7 days.")
        return

    lines = ["⏰ *Expiring Soon (7 days)*\n"]
    buttons = []
    for m in r.data:
        left = (date.fromisoformat(m["expire_at"]) - today).days
        name = m['username'] or m['full_name']
        lines.append(f"• @{name} — {m['expire_at']} ({left}d)")
        buttons.append([
            InlineKeyboardButton(text=f"@{name} (+30d)", callback_data=f"ext:{m['id']}:30"),
        ])

    await msg.answer(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# ===== /expired =====
@router.message(Command("expired"))
async def cmd_expired(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    today = date.today()
    r = supabase.table("members").select("*") \
        .lt("expire_at", today.isoformat()).execute()

    if not r.data:
        await msg.answer("✅ No expired members.")
        return

    lines = ["❌ *Expired Members*\n"]
    buttons = []
    for m in r.data:
        name = m['username'] or m['full_name']
        days_ago = (today - date.fromisoformat(m["expire_at"])).days
        lines.append(f"• @{name} — {m['expire_at']} ({days_ago}d ago)")
        buttons.append([
            InlineKeyboardButton(text=f"@{name} (+30d)", callback_data=f"ext:{m['id']}:30"),
            InlineKeyboardButton(text="🗑", callback_data=f"remove:{m['id']}"),
        ])

    await msg.answer(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# ===== /today =====
@router.message(Command("today"))
async def cmd_today(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    report = build_daily_report()
    await msg.answer(report, parse_mode="Markdown")


# ===== /search =====
@router.message(Command("search"))
async def cmd_search(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("Usage: `/search <username or name>`", parse_mode="Markdown")
        return
    q = parts[1].strip().lstrip("@")
    r = supabase.table("members").select("*") \
        .or_(f"username.ilike.%{q}%,full_name.ilike.%{q}%").execute()

    if not r.data:
        await msg.answer(f"No members match '{q}'")
        return

    buttons = []
    for m in r.data[:20]:
        name = m['username'] or m['full_name']
        buttons.append([InlineKeyboardButton(
            text=f"@{name} — {m['expire_at']}",
            callback_data=f"view:{m['id']}"
        )])

    await msg.answer(
        f"🔍 Found {len(r.data)} result(s):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# ===== /extend <user_id> <days> =====
@router.message(Command("extend"))
async def cmd_extend(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) != 3:
        await msg.answer("Usage: `/extend <telegram_user_id> <days>`", parse_mode="Markdown")
        return
    try:
        tg_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await msg.answer("Invalid numbers.")
        return

    r = supabase.table("members").select("*").eq("telegram_user_id", tg_id).execute()
    if not r.data:
        await msg.answer(f"Member with ID {tg_id} not found.")
        return

    from members import extend_member
    new_expire = extend_member(r.data[0]["id"], days, msg.from_user.id)
    await msg.answer(f"✅ Extended +{days}d → {new_expire}")


# ===== /add <user_id> <days> =====
@router.message(Command("add"))
async def cmd_add(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) != 3:
        await msg.answer("Usage: `/add <telegram_user_id> <days>`", parse_mode="Markdown")
        return
    try:
        tg_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await msg.answer("Invalid numbers.")
        return

    today = date.today()
    expire = today + timedelta(days=days)
    try:
        supabase.table("members").insert({
            "telegram_user_id": tg_id,
            "joined_at": today.isoformat(),
            "expire_at": expire.isoformat(),
            "plan_days": days,
            "status": "active",
        }).execute()
        await msg.answer(f"✅ Added user {tg_id} — expires {expire}")
    except Exception as e:
        await msg.answer(f"Error: {e}")


# ===== /help =====
@router.message(Command("help"))
async def cmd_help(msg: Message):
    if is_admin(msg.from_user.id):
        await msg.answer(
            "*Admin Commands*\n\n"
            "/start - Admin panel\n"
            "/members - Member list\n"
            "/expiring - Expiring in 7 days\n"
            "/expired - Expired members\n"
            "/today - Daily report\n"
            "/search <name> - Find member\n"
            "/add <user_id> <days> - Add member\n"
            "/extend <user_id> <days> - Extend days\n",
            parse_mode="Markdown"
        )
    else:
        await msg.answer(
            "👋 Use /status to see your membership info.\n"
            "Contact admin to renew."
        )


# ===== /status (for members) =====
@router.message(Command("status"))
async def cmd_status(msg: Message):
    r = supabase.table("members").select("*") \
        .eq("telegram_user_id", msg.from_user.id).execute()
    if not r.data:
        await msg.answer("You're not a member yet.")
        return
    m = r.data[0]
    today = date.today()
    left = (date.fromisoformat(m["expire_at"]) - today).days
    await msg.answer(
        f"📊 *Your Membership*\n\n"
        f"📅 Joined: {m['joined_at']}\n"
        f"⌛ Expires: {m['expire_at']}\n"
        f"⏱ Days left: {left}\n"
        f"📊 Status: {m['status']}",
        parse_mode="Markdown"
    )
