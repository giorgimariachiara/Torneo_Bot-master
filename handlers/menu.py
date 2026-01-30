from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import datetime
import os


from utils.db import *
from states import *
#from handlers.registra_partita import *

def is_giocante(user_id: int) -> bool:
    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT Giocante FROM Utenti WHERE ID_Telegram = ?", (user_id,))
        result = cur.fetchone()
        return result and result[0] == 1


async def mostra_menu_principale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('menu -> menu_principale')
    user_id = update.effective_user.id
    giocante = is_giocante(user_id)

    if giocante:
        keyboard = [
            ["ℹ️ Info", "📸 Foto"],
            ["🎖 Voglio giocare", "📝 Registra punteggio"],
        ]
    else:
        keyboard = [["ℹ️ Info", "📸 Foto"]]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Se è un messaggio normale (utente ha scritto qualcosa)
    if update.message:
        testo = update.message.text
        if testo not in ["ℹ️ Info", "🎖 Voglio giocare", "📝 Registra punteggio", "📸 Foto"]:
            await update.message.reply_text("📋 Eccoci nel Menu principale:", reply_markup=reply_markup)
        # Switch basato sul testo
        match testo:
            case "ℹ️ Info":
                return INFO
                #'''await mostra_info(update, context)'''
            case "🎖 Voglio giocare":
                return DISPONIBILITA
                    #await gestione_disponibilita(update, context)
            case "📝 Registra punteggio":
                return PARTITA
                    #await gestione_partita(update, context)
            case "📸 Foto":
                return MENU
            case _:
                return MENU
    # Se è una callback (es. Viene da scelta_squadra)
    elif update.callback_query:
        await update.callback_query.message.reply_text("📋 Menu principale:", reply_markup=reply_markup)
        return MENU


# raccoglitore foto funziona

FOTO_DIR = ".\\Foto\\foto emiliana"
os.makedirs(FOTO_DIR, exist_ok=True)

async def ricevi_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('menu -> ricevi_foto')
    user = update.effective_user
    photo = update.message.photo[-1]  # migliore qualità
    file = await photo.get_file()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") # arriva ai microsecondi
    filename = f"{user.id}_{timestamp}.jpg" # nomina ogni foto diversa in base all'orario

    path = os.path.join(FOTO_DIR, filename)
    await file.download_to_drive(path)

    await update.message.reply_text("✅ Foto ricevuta e salvata con successo.")

    return MENU

async def richiedi_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Mandami una tua foto da salvare. Quando sei nel menu principale aspetto sempre le pose più bizzarre.")
    return MENU