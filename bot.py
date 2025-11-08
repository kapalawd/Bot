import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client

load_dotenv()

# Ambil konfigurasi dari environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_CHANNEL_ID = int(os.getenv("PUBLIC_CHANNEL_ID") or "0")
PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID") or "0")
SUPABASE_URL = os.getenv("SUPABASE_URL") or ""
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or ""
TABLE_NAME = os.getenv("TABLE_NAME", "films")

# Inisialisasi client Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def ping_task(context: ContextTypes.DEFAULT_TYPE):
    """Background task yang ping setiap 1 menit untuk menjaga bot tetap aktif"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[PING] Bot masih aktif - {current_time}")


async def is_member(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(PUBLIC_CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


def supabase_get_by_code(code: str):
    """Ambil record dari supabase berdasarkan code"""
    res = supabase.table(TABLE_NAME).select("code,file_id").eq(
        "code", code).limit(1).execute()
    if res and getattr(res, "data", None):
        rows = res.data
        if rows:
            return rows[0]
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    args = context.args
    code = args[0] if args else None

    if not code:
        await chat.send_message("Gunakan parameter kode. Contoh: /start GOON78"
                                )
        return

    # Cek apakah user anggota channel publik
    if not await is_member(context.bot, user.id):
        # Buat link join channel, jika channel punya username bisa diubah di sini
        channel_username = None  # Contoh: "mypublicchannel"
        if channel_username:
            join_url = f"https://t.me/{channel_username}"
        else:
            # fallback pakai ID channel (strip -100)
            join_url = f"https://t.me/kuncifilm"  # misal "-1002742502135" -> "2742502135"

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Join Channel", url=join_url)]])
        await chat.send_message(
            f"Silakan join channel publik dulu lalu klik link lagi https://t.me/boibubi_bot?start={code}",
            reply_markup=kb)
        return

    # Ambil data dari supabase berdasarkan code
    row = supabase_get_by_code(code)
    if not row:
        await chat.send_message("Kode tidak terdaftar.")
        return

    file_id_value = row.get("file_id")
    if not file_id_value:
        await chat.send_message("file_id kosong/tidak valid di database.")
        return

    try:
        message_id = int(file_id_value)
    except Exception:
        await chat.send_message(
            "Nilai file_id di database tidak valid. Harus angka (message_id).")
        return

    try:
        # Kirim file (copy message) dari channel private ke user
        await context.bot.copy_message(chat_id=chat.id,
                                       from_chat_id=PRIVATE_CHANNEL_ID,
                                       message_id=message_id)
    except Exception as e:
        await chat.send_message(
            "Gagal mengirim file. Pastikan bot admin di private channel dan message_id benar."
        )
        print(f"Error copy_message: {e}")


if __name__ == "__main__":
    while True:
        try:
            app = ApplicationBuilder().token(BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", start))

            # Jalankan background ping task setiap 60 detik (1 menit)
            job_queue = app.job_queue
            job_queue.run_repeating(ping_task, interval=60, first=10)

            print("Bot running with ping task every 1 minute")
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"Bot error: {e}")
            print("Restarting bot in 5 seconds...")
            asyncio.run(asyncio.sleep(5))
            continue
