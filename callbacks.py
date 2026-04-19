from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.members import extend_member
from config import ADMIN_USER_ID

router = Router()

@router.callback_query(F.data.startswith("ext:"))
async def handle_extend(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_USER_ID:
        await cb.answer("Not allowed", show_alert=True); return

    _, member_id, days = cb.data.split(":")
    new_expire = extend_member(int(member_id), int(days), cb.from_user.id)
    await cb.answer(f"Extended {days} days")
    await cb.message.edit_text(
        cb.message.text + f"\n\n✅ Extended +{days}d → {new_expire}",
        reply_markup=None
    )
