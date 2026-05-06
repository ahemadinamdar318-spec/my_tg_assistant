import os
import logging
import mimetypes
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === CONFIGURATION ===
BOT_TOKEN = "8422094251:AAGLAOljbRo_2XosYBLuE7zb10zmUH47SWE"
AUTHORIZED_USER_ID = 825505825 # Replace with your Telegram user_id
STORAGE_DIR = "local_storage"

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === INITIAL SETUP ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def ensure_storage():
    """Ensure the local storage directory exists."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)
        logger.info("Storage folder created.")
    else:
        logger.info("Storage folder exists.")

def is_authorized(user_id: int) -> bool:
    """Check if the user is authorized."""
    return user_id == AUTHORIZED_USER_ID

def search_files(keyword: str):
    """Search for files containing the keyword."""
    matches = []
    for root, _, files in os.walk(STORAGE_DIR):
        for f in files:
            if keyword.lower() in f.lower():
                matches.append(os.path.join(root, f))
    return matches

def get_storage_summary():
    """Return summary of all files."""
    total_size = 0
    files_info = []
    for root, dirs, files in os.walk(STORAGE_DIR):
        for f in files:
            path = os.path.join(root, f)
            size = os.path.getsize(path)
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            total_size += size
            files_info.append((f, size, mtime))
    return total_size, files_info

def get_extension_from_mime(mime_type: str) -> str:
    """Guess the correct extension from MIME type."""
    ext = mimetypes.guess_extension(mime_type or "")
    return ext if ext else ""

# === COMMAND HANDLERS ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("🚫 Access denied.")
        return
    ensure_storage()
    await message.answer("✅ Bot initialized! Local storage ready.")

@dp.message(Command("overview"))
async def cmd_overview(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("🚫 Access denied.")
        return

    total_size, files_info = get_storage_summary()
    if not files_info:
        await message.answer("📁 Storage is empty.")
        return

    summary = "\n".join(
        [f"{f} — {s/1024:.1f} KB — {d.strftime('%Y-%m-%d %H:%M:%S')}" for f, s, d in files_info]
    )
    await message.answer(f"📦 Files:\n{summary}\n\nTotal: {total_size/1024:.1f} KB")

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("🚫 Access denied.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /search <keyword>")
        return

    keyword = args[1]
    results = search_files(keyword)
    if not results:
        await message.answer("🔍 No matching files found.")
        return

    builder = InlineKeyboardBuilder()
    for i, f in enumerate(results):
        builder.button(text=f"{i+1}. {os.path.basename(f)}", callback_data=f"get|{f}")

    await message.answer("🔍 Found files:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("get|"))
async def cb_get_file(callback: types.CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.message.answer("🚫 Access denied.")
        return

    path = callback.data.split("|", 1)[1]
    if not os.path.exists(path):
        await callback.message.answer("File not found.")
        return

    await callback.message.answer_document(FSInputFile(path))

@dp.message(Command("delete"))
async def cmd_delete(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("🚫 Access denied.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /delete <filename>")
        return

    keyword = args[1]
    matches = search_files(keyword)
    if not matches:
        await message.answer("File not found.")
        return

    for f in matches:
        os.remove(f)

    await message.answer(f"🗑️ Deleted {len(matches)} file(s).")

# === MESSAGE HANDLER FOR FILES/TEXT ===
@dp.message(F.photo | F.video | F.document | F.text)
async def handle_incoming(message: types.Message):
    if not is_authorized(message.from_user.id):
        await message.answer("🚫 Access denied.")
        return

    ensure_storage()

    # --- Handle text ---
    if message.text and not (message.photo or message.video or message.document):
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = os.path.join(STORAGE_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(message.text)
        await message.answer(f"💾 Text saved as `{filename}`", parse_mode="Markdown")
        return

    # --- Handle media/documents ---
    file_obj = None
    file_name = None
    mime_type = None

    if message.document:
        file_obj = message.document
        file_name = message.document.file_name or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        mime_type = message.document.mime_type
    elif message.photo:
        file_obj = message.photo[-1]  # Highest resolution
        file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        mime_type = "image/jpeg"
    elif message.video:
        file_obj = message.video
        file_name = message.video.file_name or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        mime_type = message.video.mime_type

    if file_obj:
        ext = os.path.splitext(file_name)[1]
        if not ext:
            ext = get_extension_from_mime(mime_type)
        if not ext:
            ext = ".bin"  # Fallback

        final_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        path = os.path.join(STORAGE_DIR, final_name)
        file_info = await bot.get_file(file_obj.file_id)
        await bot.download_file(file_info.file_path, path)
        await message.answer(f"💾 Saved `{final_name}` ({mime_type or 'unknown'})", parse_mode="Markdown")

# === MAIN ENTRY ===
async def main():
    ensure_storage()
    logger.info("🚀 Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
