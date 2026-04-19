from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, Message
from members import upsert_member_on_join
from config import ADMIN_USER_ID, GROUP_ID

router = Router()

# ✅ group ထဲ new member join event (new_chat_members)
@router.message(F.new_chat_members)
async def on_user_join_message(msg: Message):
    for user in msg.new_chat_members:
        if user.is_bot:
            continue
        member, is_new = upsert_member_on_join(
            user.id, user.username, user.full_name
        )
        if is_new:
            await notify_admin_new_join(msg.bot, user, member)

# ✅ chat_member update (ပိုကောင်းတဲ့ detection method)
@router.chat_member()
async def on_chat_member_update(event: ChatMemberUpdated):
    if event.chat.id != GROUP_ID:
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    joined = old_status in ("left", "kicked") and new_status in ("member", "restricted")
    if not joined:
        return

    user = event.new_chat_member.user
    if user.is_bot:
        return

    member, is_new = upsert_member_on_join(
        user.id, user.username, user.full_name
    )
    if is_new:
        await notify_admin_new_join(event.bot, user, member)


async def notify_admin_new_join(bot, user, member):
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
            InlineKeyboardButton(text="👁 View", callback_data=f"view:{member['id']}"),
            InlineKeyboardButton(text="🗑 Remove", callback_data=f"remove:{member['id']}"),
        ],
    ])
    try:
        await bot.send_message(ADMIN_USER_ID, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        print(f"Failed to notify admin: {e}")
