import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
NAME, VOUCHER_TYPE, VOUCHER_AMOUNT = range(3)

# Google Sheets setup
def setup_google_sheets():
    """Setup connection to Google Sheets"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Try to get credentials from environment variable (for cloud deployment)
    creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    
    if creds_json:
        # Load from environment variable (Railway, Render, etc)
        import json
        creds_dict = json.loads(creds_json)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        # Load from file (local development)
        credentials = Credentials.from_service_account_file(
            os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json'), scopes=scope
        )
    
    client = gspread.authorize(credentials)
    sheet = client.open(os.getenv('SPREADSHEET_NAME')).sheet1
    return sheet

# Initialize sheet
try:
    sheet = setup_google_sheets()
    # Setup header if needed
    if sheet.row_values(1) == []:
        sheet.append_row(['Tanggal', 'Nama', 'Jenis Voucher', 'Jumlah (Dollar)'])
    logger.info("Google Sheets connected successfully!")
except FileNotFoundError:
    logger.error("credentials.json not found. Please set GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable.")
    sheet = None
except Exception as e:
    logger.error(f"Error setting up Google Sheets: {e}")
    logger.info("Bot will continue, but data won't be saved to sheets.")
    sheet = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for name"""
    await update.message.reply_text(
        "Selamat datang di Bot Farm House! 🏡\n\n"
        "Saya akan membantu Anda mencatat data voucher.\n\n"
        "Silakan masukkan nama Anda:"
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store name and ask for voucher type"""
    context.user_data['name'] = update.message.text
    
    # Create keyboard with voucher types by merchant
    voucher_types = [
        ['Amazon', 'eBay', 'Target'],
        ['Walmart', 'Best Buy'],
        ['Nike', 'Adidas', 'H&M'],
        ['Sephora', 'Ulta Beauty'],
        ['Spotify', 'Netflix', 'Xbox'],
        ['PlayStation', 'Steam'],
        ['Starbucks', 'Domino\'s', 'Uber Eats'],
        ['Other']
    ]
    reply_markup = ReplyKeyboardMarkup(voucher_types, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"Terima kasih, {update.message.text}!\n\n"
        "Pilih atau ketik jenis voucher:",
        reply_markup=reply_markup
    )
    return VOUCHER_TYPE


async def get_voucher_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store voucher type and ask for amount"""
    context.user_data['voucher_type'] = update.message.text
    
    await update.message.reply_text(
        "Berapa jumlah voucher dalam dollar? (contoh: 50)\n"
        "Masukkan hanya angka:",
        reply_markup=ReplyKeyboardRemove()
    )
    return VOUCHER_AMOUNT


async def get_voucher_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store amount and save to spreadsheet"""
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount
        
        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare data
        name = context.user_data['name']
        voucher_type = context.user_data['voucher_type']
        
        # Save to Google Sheets
        if sheet:
            try:
                sheet.append_row([current_date, name, voucher_type, amount])
                await update.message.reply_text(
                    "✅ Data berhasil disimpan!\n\n"
                    f"📅 Tanggal: {current_date}\n"
                    f"👤 Nama: {name}\n"
                    f"🎫 Jenis Voucher: {voucher_type}\n"
                    f"💵 Jumlah: ${amount}\n\n"
                    "Ketik /start untuk menambah data baru atau /cancel untuk berhenti."
                )
            except Exception as e:
                logger.error(f"Error saving to sheet: {e}")
                await update.message.reply_text(
                    "❌ Maaf, terjadi kesalahan saat menyimpan ke spreadsheet.\n"
                    "Silakan coba lagi atau hubungi admin."
                )
        else:
            await update.message.reply_text(
                "❌ Koneksi ke Google Sheets belum tersedia.\n"
                "Silakan periksa konfigurasi."
            )
        
        # Clear user data
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Input tidak valid. Mohon masukkan angka saja.\n"
            "Contoh: 50 atau 25.5"
        )
        return VOUCHER_AMOUNT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    await update.message.reply_text(
        "Operasi dibatalkan. Ketik /start untuk memulai lagi.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display help message"""
    await update.message.reply_text(
        "📖 Bantuan Bot Farm House\n\n"
        "Perintah yang tersedia:\n"
        "/start - Mulai menambahkan data voucher\n"
        "/cancel - Batalkan operasi saat ini\n"
        "/help - Tampilkan pesan bantuan ini\n\n"
        "Bot ini akan mencatat:\n"
        "• Tanggal (otomatis)\n"
        "• Nama\n"
        "• Jenis Voucher\n"
        "• Jumlah dalam Dollar"
    )


def main() -> None:
    """Start the bot"""
    # Get token from environment
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            VOUCHER_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_voucher_type)],
            VOUCHER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_voucher_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    
    # Start the bot
    logger.info("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
