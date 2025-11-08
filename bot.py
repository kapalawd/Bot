import os
import random  # Tambahkan untuk gacha random
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_CHANNEL_ID = int(os.getenv("PUBLIC_CHANNEL_ID") or "0")
PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID") or "0")
SUPABASE_URL = os.getenv("SUPABASE_URL") or ""
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or ""
TABLE_NAME = os.getenv("TABLE_NAME", "films")
PRIVATE_GROUP_ID = int(os.getenv("PRIVATE_GROUP_ID")
                       or "0")  # ID grup privat VIP (misal -1001234567890)
SMARTLINK_URL = os.getenv("SMARTLINK_URL")  # Opsional, untuk monetisasi

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def is_member(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(PUBLIC_CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


def supabase_get_by_code(code: str):
    res = supabase.table(TABLE_NAME).select("code,file_id").eq(
        "code", code).limit(1).execute()
    if res and getattr(res, "data", None):
        rows = res.data
        if rows:
            return rows[0]
    return None


def get_winner_count():
    """Hitung jumlah pemenang gacha dari Supabase"""
    res = supabase.table("gacha_winners").select("id").execute()
    return len(res.data) if res.data else 0


def add_winner(user_id: int, username: str):
    """Tambah pemenang ke Supabase"""
    supabase.table("gacha_winners").insert({
        "user_id": user_id,
        "username": username
    }).execute()


async def gacha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /gacha"""
    user = update.effective_user
    chat = update.effective_chat

    winner_count = get_winner_count()
    if winner_count >= 100:
        await chat.send_message(
            "Maaf, gacha sudah penuh! Semua 100 slot pemenang sudah terisi. 😔")
        return

    # Cek apakah user sudah menang sebelumnya
    res = supabase.table("gacha_winners").select("user_id").eq(
        "user_id", user.id).limit(1).execute()
    if res.data:
        await chat.send_message(
            "Kamu sudah menang gacha sebelumnya! Selamat bergabung di grup VIP. 🎉"
        )
        return

    # Gacha: Peluang 1/100 menang
    if random.randint(1, 100) == 1:  # Menang!
        try:
            # Invite user ke grup privat
            await context.bot.invite_chat_member(chat_id=PRIVATE_GROUP_ID,
                                                 user_id=user.id)
            add_winner(user.id, user.username or "unknown")
            await chat.send_message(
                "🎉 SELAMAT! Kamu menang gacha! Kamu sekarang di-invite ke grup VIP untuk akses file tanpa bot lagi. Cek undangan di chat kamu! 🚀"
            )
        except Exception as e:
            await chat.send_message(
                "🎉 SELAMAT! Kamu menang gacha, tapi gagal invite ke grup. Hubungi admin untuk akses manual. 😅"
            )
            print(f"Error invite: {e}")
    else:
        # Kalah, tawarkan smartlink jika ada
        message = "😢 Sayang sekali, kamu belum beruntung kali ini. Coba lagi lain waktu!"
        if SMARTLINK_URL:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("🎁 Dukung Bot & Coba Lagi",
                                     url=SMARTLINK_URL)
            ]])
            await chat.send_message(message, reply_markup=kb)
        else:
            await chat.send_message(message)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    args = context.args
    code = args[0] if args else None

    if not code:
        await chat.send_message("Gunakan parameter kode. Contoh: /start GOON78"
                                )
        return

    if not await is_member(context.bot, user.id):
        join_url = f"https://t.me/critcritcrot/{PUBLIC_CHANNEL_ID}"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Join Channel", url=join_url)]])
        await chat.send_message(
            f"Silakan join channel publik dulu lalu klik link lagi https://t.me/boibubi_bot?start={code}",
            reply_markup=kb)
        return

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
        await context.bot.copy_message(chat_id=chat.id,
                                       from_chat_id=PRIVATE_CHANNEL_ID,
                                       message_id=message_id)

        # Kirim pesan gacha setelah file berhasil dikirim
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎰 Gacha!", url=SMARTLINK_URL)]])
        await chat.send_message(
            "Menangkan kesempatan masuk CHANNEL PRIVAT dengan full video 🥵💦🎬 tanpa link!!!\n\n🎰 Kesempatan 1/100 dan hanya ada 100 pemenang!!! \n\n hubungi atmin jika ada masalah @cilokkecil",
            reply_markup=kb)

    except Exception as e:
        await chat.send_message(
            "Gagal mengirim file. Pastikan bot admin di private channel dan message_id benar."
        )
        print(f"Error copy_message: {e}")


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gacha", gacha))  # Tambahkan handler gacha

    print("Bot running with gacha feature")
    app.run_polling(drop_pending_updates=True)
