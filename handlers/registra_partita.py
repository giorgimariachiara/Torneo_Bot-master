# handlers/registra_partita.py
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup

from telegram.constants import ParseMode
from handlers.menu import mostra_menu_principale
from operations.operations import *
from states import *
from utils.db import *

async def gestione_partite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("partita -> gestione_partite")
    user_id = update.effective_user.id
    squadra = get_squadra_da_user_id(user_id)

    if not squadra:
        await update.message.reply_text("Non sei associato a nessuna squadra.")
        return MENU

    partita = get_partita_in_corso(squadra)
    print('la partita in corso è:', partita)
    if not partita:
        await update.message.reply_text("❌ La tua squadra non sta giocando.")
        return MENU

    avversario = partita["squadra1"] if partita["squadra2"] == squadra else partita["squadra2"]
    context.user_data["partita_corrente"] = partita

    await update.message.reply_text(
        f"📣 La tua squadra ha giocato contro `{avversario}`.\n\n Confermi questo avversario?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["✅ Sì", "❌ No"]], resize_keyboard=True)
    )
    return PARTITA


async def conferma_avversario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    partita = context.user_data.get("partita_corrente")
    squadra1 = partita["squadra1"]
    squadra2 = partita["squadra2"]
    match = "-".join(sorted([squadra1, squadra2]))
    risposta = update.message.text.strip().lower()
    if risposta == "❌ no":
        await update.message.reply_text("Contatta un amministratore per risolvere la situazione.", reply_markup=ReplyKeyboardRemove())
        return MENU

    # 🔒 Blocca la partita subito nel DB
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT Status_Partita FROM Partite WHERE Lista_Match = ?", (match,))
        stato_attuale = cur.fetchone()
        if not stato_attuale or stato_attuale[0] != "in gioco":
            await update.message.reply_text("⚠️ Questa partita non è più disponibile per la registrazione.")
            await mostra_menu_principale(update, context)
            return MENU

        # Blocca temporaneamente
        cur.execute("UPDATE Partite SET Status_Partita = 'bloccata' WHERE Lista_Match = ?", (match,))
        conn.commit()

    await update.message.reply_text(
        "️Se una squadra ha perso per falli, il suo punteggio sarà `0`.\n\n",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data["fase_inserimento"] = "squadra1"
    await update.message.reply_text(
        f"✏️ Scrivi SOLO i punti della squadra `{squadra1}`:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return PARTITA_INSERISCI_PUNTEGGIO1

async def inserisci_punteggio_squadra1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    partita = context.user_data.get("partita_corrente")
    squadra1 = partita["squadra1"]
    try:
        punteggio1 = int(update.message.text.strip())
        if not (0 <= punteggio1 <= 50):
            raise ValueError("Punteggio fuori intervallo")
        context.user_data["punti_squadra1"] = punteggio1

        squadra2 = context.user_data["partita_corrente"]["squadra2"]
        await update.message.reply_text(
            f"✏️ Ora scrivi SOLO i punti della squadra `{squadra2}`:",
            parse_mode="Markdown"
        )
        return PARTITA_INSERISCI_PUNTEGGIO2

    except Exception:
        await update.message.reply_text(f"❌ Punteggio inserito non valido!\n\n Inserisci nuovamente il punteggio della squadra: `{squadra1}`.",
                                        parse_mode="Markdown")
        return PARTITA_INSERISCI_PUNTEGGIO1

async def inserisci_punteggio_squadra2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    partita = context.user_data.get("partita_corrente")
    squadra2 = partita["squadra2"]
    try:
        punteggio2 = int(update.message.text.strip())
        if not (0 <= punteggio2 <= 50):
            raise ValueError("Punteggio fuori intervallo")
        punti1 = context.user_data.get("punti_squadra1")

        squadra1 = context.user_data["partita_corrente"]["squadra1"]
        squadra2 = context.user_data["partita_corrente"]["squadra2"]
        match = "-".join(sorted([squadra1, squadra2]))

        if not ((punti1 == 50 and punteggio2 < 50) or (punteggio2 == 50 and punti1 < 50)):
            raise ValueError("Formato non valido")

        # Controllo status
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT Status_Partita FROM Partite WHERE Lista_Match = ?", (match,))
            stato = cur.fetchone()
            if not stato or stato[0] != "bloccata":
                await update.message.reply_text("⚠️ Partita già registrata o non valida.")
                return MENU

        # Registra punteggio
        esito = registra_punteggio_partita(squadra1, squadra2, punti1, punteggio2)
        if not esito:
            await update.message.reply_text("⚠️ Punteggio già registrato.")
            return MENU

        # Notifica
        user_id = update.effective_user.id
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id_telegram FROM Utenti WHERE Squadra = ? OR Squadra = ?", (squadra1, squadra2))
            utenti = [r[0] for r in cur.fetchall() if r[0] != user_id]

        risultato = f"✅ Partita registrata con successo!\n\n⚔️ Match: `{squadra1}` VS. `{squadra2}`\n\n📊 Risultato: `{punti1} - {punteggio2}`\n\nSei già disponibile, aspetta la prossima partita "
        for uid in utenti:
            try:
                await context.bot.send_message(uid, risultato, parse_mode="Markdown")
            except Exception as e:
                print(f"[Errore invio a {uid}]: {e}")

        await assegna_partita(context.bot, user_id=user_id)

        # Imposta le squadre come disponibili
        set_squadra_disponibile(squadra1)
        set_squadra_disponibile(squadra2)
        #libera il campo in tabella Campi
        libera_campo(match)

        await mostra_menu_principale(update, context)
        return MENU

    except Exception as e:
        print("Errore inserimento punteggio 2:", e)
        await update.message.reply_text(f"❌ Inserisci un numero valido tra 0 e 50, solo una squadra può avere 50 punti.\n\n"
                                        f"Inserisci nuovamente il punteggio della squadra: `{squadra2}`.",
                                        parse_mode="Markdown")
        return PARTITA_INSERISCI_PUNTEGGIO2


async def verifica_fine_torneo(context: ContextTypes.DEFAULT_TYPE):
    if not globals.EVENTO_CHIUSO:
        return

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Partite WHERE Status_Partita = 'in gioco'")
        in_gioco = cur.fetchone()[0]

    if in_gioco == 0:
        user_ids = get_tutti_user_id()
        for user_id in user_ids:
            try:
                await context.bot.send_message(
                    user_id,
                    "🎉 🎉 🎉 🎉 🎉 🎉 🎉 \n *Il torneo è ufficialmente chiuso!*\n🏆 A breve si disputeranno le *finali!*\n Complimenti a tutti i giocatori 🎉 ",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                print(f"[Errore invio chiusura finale a {user_id}]: {e}")

        globals.EVENTO_CHIUSO = False  # Disattiva per non re inviare