from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from services.members import upsert_member_on_join
from config import ADMIN_USER_ID, GROUP_ID

router = Router()

@router.chat_member()
async def on_chat_member_update(event: ChatMemberUpdated):
    if event.chat.id != GROUP_ID:
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    # detect actual "join" transition
    joined = old_status in ("left", "kicked") and new_status in ("member", "restricted")
    if not joined:
        return

    user = event.new_chat_member.user
    if user.is_bot:
        return

    member, is_new = upsert_member_on_join(
        user.id, user.username, user.full_name
    )

    text = (
        f"🆕 *New member joined*\n\n"
        f"👤 {user.full_name}\n"
        f"🔗 @{user.username or '—'}\n"
        f"🆔 `{user.id}`\n"
        f"📅 Joined: {member['joined_at']}\n"
        f"⌛ Expires: {member['expire_at']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="+30d", callback_data=f"ext:{member['id']}:30"),
            InlineKeyboardButton(text="+60d", callback_data=f"ext:{member['id']}:60"),
            InlineKeyboardButton(text="+90d", callback_data=f"ext:{member['id']}:90"),
        ],
        [
            InlineKeyboardButton(text="📅 Set Date", callback_data=f"setdate:{member['id']}"),
            InlineKeyboardButton(text="✏️ Edit", callback_data=f"edit:{member['id']}"),
        ],
    ])
    await event.bot.send_message(ADMIN_USER_ID, text, reply_markup=kb, parse_mode="Markdown")
