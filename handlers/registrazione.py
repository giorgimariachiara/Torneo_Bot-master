from telegram import KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, filters
from telegram.ext.filters import MessageFilter
from handlers.menu import *
from states import *
from utils.db import *
from utils.globals import ADMINS, CAPI
import utils.globals as globals
import sqlite3
from telegram import BotCommand, BotCommandScopeChat

async def set_comandi_utente(bot, user_id: int):
    print(f"admin -> imposta comandi")
    comandi_base = [
        BotCommand("start", "Inizia a parlare con il Bot")
    ]

    comandi_admin = [
        BotCommand("aggiungi_squadra", "Aggiungi una nuova squadra"),
        BotCommand("cancella_squadra", "Cancella una squadra esistente"),
        BotCommand("cancella_utente", "Rimuove un utente dal sistema"),
        BotCommand("modifica_punteggio", "Modifica punteggio partita"),
        BotCommand("inizio", "inizia la registrazione giocatori"),
    ]

    comandi_capo = [
        BotCommand("utenti", "Mostra la lista degli utenti registrati"),
        BotCommand("messaggio_tutti", "Invia un messaggio a tutti gli utenti"),

    ]

    '''comandi_gestione = [
        BotCommand("pausa", "Mette in pausa la disponibilità per le partite"),
        BotCommand("riprendi", "Riattiva la disponibilità per le partite"),
        BotCommand("fine_evento", "Fine evento a tempo, lasciare finire le partite"),
        BotCommand("fine_torneo", "Fine torneo, chiusura partite"),
    ]'''



    # Comandi per admin
    if user_id in ADMINS:
        await bot.set_my_commands(comandi_base + comandi_admin + comandi_capo, scope=BotCommandScopeChat(user_id))

    # Comandi per capi
    elif user_id in CAPI:
        await bot.set_my_commands(comandi_base + comandi_capo, scope=BotCommandScopeChat(user_id))

    # Comandi per gestione tempi torneo
    #elif user_id in GESTIONE:
        #await bot.set_my_commands(comandi_gestione, scope=BotCommandScopeChat(user_id))

    # Solo comandi base
    else:
        await bot.set_my_commands(comandi_base, scope=BotCommandScopeChat(user_id))

async def scelta_tipo_utente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    nome = update.message.from_user.first_name

    if text == "🎯 Gioco":
        aggiorna_giocante(user_id, nome, True)

        with sqlite3.connect("Torneo_Molkky.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT Nome_Squadra FROM Squadre")
            squadre = [r[0] for r in cur.fetchall()]

        if squadre:
            buttons = [[InlineKeyboardButton(nome, callback_data=f"squadra_{nome}")] for nome in squadre]
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text("A quale squadra appartieni?", reply_markup=reply_markup)
            return SQUADRA
        else:
            await update.message.reply_text("⚠️ Nessuna squadra trovata.")
            return ConversationHandler.END

    elif text == "👀 Osservo":
        aggiorna_giocante(user_id, nome, False)
        await update.message.reply_text("✔️ Ti sei registratƏ come osservatore. Fai il tifo per chi vuoi")
        await mostra_menu_principale(update, context)
        return MENU
    else:
        await update.message.reply_text("Per favore scegli tra 🎯 Gioco o 👀 Osservo.")
        return REGISTRAZIONE

async def scelta_squadra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("squadra_"):
        squadra = data.split("_", 1)[1]
        aggiorna_squadra(user_id, squadra)
        await query.edit_message_text(f"✅ Sei stato assegnatƏ alla squadra: {squadra}")
        await query.edit_message_text(f"In bocca al lupo e che i birilli siano con te!")
        await mostra_menu_principale(update, context)
        return MENU
    else:
        await query.edit_message_text("❌ Squadra non riconosciuta. Riprova.")
        return ConversationHandler.END


# Filtro primo messaggio

async def filtro_primo_messaggio():
    async def inner(update):
        user_id = update.effective_user.id
        return not crea_o_trova_utente(user_id)
    return filters.TEXT & filters.Create(inner)

class FiltroPrimoMessaggio(MessageFilter):
    """Filtro che intercetta solo i primi messaggi degli utenti non ancora registrati."""
    def filter(self, message) -> bool:
        user_id = message.from_user.id
        return not utente_esiste(user_id)  # True solo se NON esiste già

filtro_primo_msg = FiltroPrimoMessaggio()



# NUOVO star

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if globals.ISCRIZIONI:
        return ConversationHandler.END


    user = update.effective_user
    user_id = user.id
    await set_comandi_utente(context.bot, user_id)
    nuovo = crea_o_trova_utente(user.id, user.full_name)

    if nuovo:
        # Utente nuovo → chiedi subito se gioca o-osserva
        keyboard = [[KeyboardButton("🎯 Gioco"), KeyboardButton("👀 Osservo")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            f"Ciao {user.first_name}! BenvenutƏ al Torneo! \n\n Sei un giocatore o un osservatore?",
            reply_markup=reply_markup
        )
        return REGISTRAZIONE

    # Utente già presente: controllo se ha scelto il ruolo
    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT Giocante, Squadra FROM Utenti WHERE id_telegram = ?", (user_id,))
        risultato = cur.fetchone()

    if risultato is None:
        await update.message.reply_text("⚠️ Errore nel recuperare i tuoi dati.")
        return MENU

    giocante, squadra = risultato

    if giocante is None:
        # L'utente non ha ancora scelto se giocante-o osservatore
        keyboard = [[KeyboardButton("🎯 Gioco"), KeyboardButton("👀 Osservo")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            f"Ciao {user.first_name}! Sei un giocatore o un osservatore?",
            reply_markup=reply_markup
        )
        return REGISTRAZIONE

    if giocante == 1 and not squadra:
        # È un giocatore ma non ha ancora una squadra
        with sqlite3.connect("Torneo_Molkky.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT Nome_Squadra FROM Squadre")
            squadre = [r[0] for r in cur.fetchall()]

        if squadre:
            buttons = [[InlineKeyboardButton(nome, callback_data=f"squadra_{nome}")] for nome in squadre]
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text("A quale squadra appartieni?", reply_markup=reply_markup)
            return SQUADRA
        else:
            await update.message.reply_text("⚠️ Nessuna squadra disponibile.")
            return ConversationHandler.END

    # Tutto ok → mostra il menu principale
    await update.message.reply_text("🎊 BentornatƏ! Il divertimento continua.  👍")
    await mostra_menu_principale(update, context)
    return MENU