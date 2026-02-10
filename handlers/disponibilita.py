from telegram import ReplyKeyboardRemove
from handlers.menu import mostra_menu_principale
from states import *
from operations.operations import *

#numero di partite massime per squadra
max_partite = 10

async def gestione_disponibilita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("menu -> gestione_disponibilita")

    if not globals.DISPONIBILITA_ATTIVA:
        if globals.EVENTO_CHIUSO:
            await update.message.reply_text("⛔ Il torneo è quasi finito. Aspetta le ultime partite.")
        else:
            await update.message.reply_text("⏸️ Le partite sono attualmente in pausa. Riprova più tardi.")
        return MENU

    user_id = update.effective_user.id
    stato = verifica_stato_squadra(user_id)


    # Recupera la squadra dell'utente
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT Squadra FROM Utenti WHERE ID_Telegram = ?", (user_id,))
        user_squadra_row = cur.fetchone()
        if user_squadra_row:
            user_squadra = user_squadra_row[0]

            # Recupera il numero di partite giocate dalla squadra
            cur.execute("SELECT Partite_Giocate FROM Squadre WHERE Nome_Squadra = ?", (user_squadra,))
            partite_giocate_row = cur.fetchone()
            if partite_giocate_row:
                partite_giocate = partite_giocate_row[0]

                # Se la squadra ha raggiunto il limite di max_partite, non può più segnarsi come disponibile
                if partite_giocate >= max_partite:
                    await update.message.reply_text(
                        "⛔ La tua squadra ha già giocato tutte le partite. Non puoi più renderti disponibile.")
                    return MENU



    if stato == "disponibile":
        keyboard = [
            [
                InlineKeyboardButton("✅ Voglio giocare!", callback_data="disponibile"),
                InlineKeyboardButton("❌ Ora non voglio giocare!", callback_data="indisponibile")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Segna se vuoi giocare!",
            reply_markup=reply_markup
        )
        return DISPONIBILITA

    elif stato == "in gioco":
        await update.message.reply_text("⚠️ Hai già una partita in corso. Concludila prima di offrirti di nuovo.")
        return MENU
    elif stato in ["indisponibile", ""]:
        await update.message.reply_text(
            "🔄 Vuoi metterti in gioco?",
            reply_markup=ReplyKeyboardRemove()
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ Voglio giocare!", callback_data="disponibile"),
                InlineKeyboardButton("❌ Ora non voglio giocare", callback_data="indisponibile")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Vuoi giocare?",
            reply_markup=reply_markup
        )
        return DISPONIBILITA
    else:
        await update.message.reply_text("⚠️ Errore nel determinare lo stato della squadra.")
        return MENU


async def callback_disponibilita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("callback -> callback_disponibilita")
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    disponibilita = query.data == "disponibile"

    risultato = aggiorna_status_squadra(user_id, disponibilita)

    if risultato == "ok":
        messaggio = (
            "Hai segnalato che sei disponibile a giocare! In bocca al lupo"
            if disponibilita else
            "❌ Hai segnalato che al momento non vuoi giocare. Fatti un'altra birra dai!"
        )
    else:
        messaggio = risultato  # Mostra il messaggio d'errore ritornato dalla funzione

    await query.edit_message_text(messaggio)

    # 👉 Se disponibile, chiama processa_disponibilita
    if disponibilita and risultato == "ok":
        await processa_disponibilita(update, context)

    await mostra_menu_principale(update, context)
    return MENU




