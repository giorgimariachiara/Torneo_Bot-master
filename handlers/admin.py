# handlers/admin.py
import random

from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, ConversationHandler, filters, \
    CallbackQueryHandler

import utils.globals as globals
from utils.db import *
from utils.globals import ADMINS, CAPI

# Stato per aggiunta squadra
ATTESA_NOME_SQUADRA = 1

# Stato per modifica punteggio
SCELTA_PARTITA, INSERISCI_PUNTEGGIO = range(2)

# --- Comandi diretti --- #

async def lista_utenti_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('admin -> lista_utenti_command')
    if update.effective_user.id not in ADMINS and update.effective_user.id not in CAPI:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return

    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id_telegram, Nome_Utente, Giocante, Squadra FROM Utenti")
        utenti = cur.fetchall()

    if not utenti:
        await update.message.reply_text("❌ Nessun utente trovato.")
    else:
        messaggio = "📋 Utenti registrati:\n"
        for u in utenti:
            giocante = "🎯" if u[2] else "👀"
            squadra = u[3] or "—"
            messaggio += f"{giocante} {u[1]} (ID: {u[0]}) - Squadra: {squadra}\n"
        await update.message.reply_text(messaggio)

async def cancella_utente_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('admin -> cancella_utente_command')
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return
    try:
        user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("❗ Usa il comando così: /cancella_utente <user_id>")
        return

    cancella_utente_completo(user_id)
    await update.message.reply_text(f"🗑️ Utente {user_id} cancellato.")

async def cancella_squadra_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('admin -> cancella_squadra_command')
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return
    print("context.args:", context.args)
    try:
        print()
        nome_squadra = " ".join(context.args)
        if not nome_squadra:
            raise IndexError
    except IndexError:
        await update.message.reply_text("❗ Usa il comando così: /cancella_squadra <nome_squadra>")
        return

    cancella_squadra_completa(nome_squadra.upper())
    await update.message.reply_text(f"🗑️ Squadra `{nome_squadra}` cancellata.",parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove())

# --- Flusso aggiunta squadra --- #

async def aggiungi_squadra_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print('admin -> aggiungi_squadra_start')
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return ConversationHandler.END

    await update.message.reply_text("✏️ Inserisci il nome della nuova squadra e invia il messaggio.\n\nScrivi 'fine' quando hai finito di inserire squadre.")

    return ATTESA_NOME_SQUADRA
NUM_SQUADRA=0
async def ricevi_nome_squadra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global NUM_SQUADRA
    print('admin -> ricevi_nome_squadra')
    nome = update.message.text.strip().upper()

    if nome.upper() == "FINE":
        await update.message.reply_text("🏁 Inserimento terminato. Tutte le squadre sono state aggiunte.",
                                        reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    nome = nome.upper()

    if not nome:
        await update.message.reply_text("⚠️ Nome non valido. Riprova.")
        return ATTESA_NOME_SQUADRA

    aggiungi_squadra(nome)

    await update.message.reply_text(f"✅ Squadra `{nome}` aggiunta con successo.", parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove())
    NUM_SQUADRA += 1
    return ATTESA_NOME_SQUADRA

aggiunta_squadra_handler = ConversationHandler(
    entry_points=[CommandHandler("aggiungi_squadra", aggiungi_squadra_start)],
    states={
        ATTESA_NOME_SQUADRA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_nome_squadra)],
    },
    fallbacks=[],
    name="aggiunta_squadra_conversation",
)


# messaggio a tutti gli utenti
from telegram.constants import ParseMode
# Stato per messaggio broadcast
ATTESA_TESTO_BROADCAST = 1
# --- Comando broadcast admin ---
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print('admin -> start_broadcast')

    if update.effective_user.id not in ADMINS and update.effective_user.id not in CAPI:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return ConversationHandler.END

    await update.message.reply_text("✏️ Scrivi il messaggio da inviare a *tutti gli utenti* iscritti:",
                                    parse_mode=ParseMode.MARKDOWN)
    return ATTESA_TESTO_BROADCAST

async def invia_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print("admin -> invia_broadcast", update.message.text)
    messaggio = update.message.text

    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT ID_Telegram FROM Utenti")
        utenti = [r[0] for r in cur.fetchall()]

    count = 0
    for user_id in utenti:
        try:
            await context.bot.send_message(chat_id=user_id, text=messaggio)
            count += 1
        except Exception as e:
            print(f"[Errore] Non riesco a mandare messaggio a {user_id}: {e}")

    await update.message.reply_text(f"✅ Messaggio inviato a {count} utenti.")

    return ConversationHandler.END

broadcast_handler = ConversationHandler(
    entry_points=[CommandHandler("messaggio_tutti", start_broadcast)],
    states={
        ATTESA_TESTO_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, invia_broadcast)]
    },
    fallbacks=[],
    name="broadcast_conversation"
)
# comando modifica fine registrazioni














async def inizio_torneo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global NUM_SQUADRA


    status=globals.config_torneo[NUM_SQUADRA]
    num_gironi=status['num_gironi']
    num_campi=status['numero_campi']
    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()

        for index in range(8):
            girone=(index//num_campi)+1
            cur.execute("UPDATE Campi SET Girone=? WHERE id_campo=?",(girone,index+1,))
            conn.commit()
    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT Nome_squadra FROM Squadre")
        nome_squadre = [r[0] for r in cur.fetchall()]

        random.shuffle(nome_squadre)
        #assegnazioni = {}
        for i, squadra in enumerate(nome_squadre):
            girone = (i % num_gironi) + 1
            #assegnazioni[squadra] = girone
            cur.execute("UPDATE Squadre SET Girone=? WHERE Nome_squadra=?", (girone, squadra,))
            conn.commit()

    globals.ISCRIZIONI = False
    print(f"fine registrazioni")


















#    GESTIONE PAUSA PRANZO

# comando per mettere in pausa disponibilità
async def pausa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("admin -> pausa_command")

    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return

    globals.DISPONIBILITA_ATTIVA = False  # blocca il tasto

    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT Nome_Squadra FROM Squadre WHERE Status = 'disponibile'")
        squadre = [row[0] for row in cur.fetchall()]

    for squadra in squadre:
        aggiorna_status_squadra_per_nome(squadra, "indisponibile")

    # Manda il messaggio a tutti gli utenti
    user_ids = get_tutti_user_id()
    for user_id in user_ids:
        try:
            await context.bot.send_message(user_id, "⏸️ *Pausa!* Le partite sono temporaneamente sospese. ", parse_mode="Markdown")
        except Exception as e:
            print(f"Errore nell'invio a {user_id}: {e}")

    await update.message.reply_text("✅ Pausa attivata. Tutti gli utenti sono stati avvisati.")

# comando per mettere in gioco disponibilità
async def riprendi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    print("admin -> riprendi_command")

    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return

    globals.DISPONIBILITA_ATTIVA = True

    # Manda il messaggio a tutti gli utenti
    user_ids = get_tutti_user_id()
    for user_id in user_ids:
        try:
            await context.bot.send_message(
                user_id,
                "✅ Si riparte! Le partite possono riprendere.\n📅 Ricordati di segnalare la tua disponibilità!",
            )
        except Exception as e:
            print(f"Errore nell'invio a {user_id}: {e}")

    await update.message.reply_text("🔓 Disponibilità riattivata. Gli utenti sono stati informati.")


#    GESTIONE FINE PARTITE a tempo
async def chiusura_evento_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("admin -> chiusura_evento_command")

    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return

    globals.DISPONIBILITA_ATTIVA = False
    globals.EVENTO_CHIUSO = True

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # 1. Rendi tutte le squadre indisponibili
        cur.execute("UPDATE Squadre SET Status = 'indisponibile' WHERE Status = 'disponibile'")
        conn.commit()

    # 5. Avvisa tutti gli utenti
    user_ids = get_tutti_user_id()
    for user_id in user_ids:
        try:
            await context.bot.send_message(
                user_id,
                "⛔ *Il torneo è quasi finito!*\nStiamo completando le ultime partite...\n\n Completa la tua partita o aspetta la fine.\n La disponibilità a giocare è chiusa!",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            print(f"[Errore invio a {user_id}]: {e}")

    await update.message.reply_text("✅ Chiusura avviata. Tutti sono ora osservatori. Monitoraggio partite attivo.")


# Gestione chiusura torneo
async def fine_torneo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("admin -> fine_torneo_command")

    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return

    # Verifica se ci sono partite "in gioco"
    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Partite WHERE Status_Partita = 'in gioco'")
        partite_in_corso = cur.fetchone()[0]

    if partite_in_corso > 0:
        await update.message.reply_text("❌ C'è ancora una partita in corso. Non è possibile chiudere il torneo.")
        return

    # Ottieni le prime 4 squadre dalla classifica
    with sqlite3.connect(DB_PATH):
        # Recupera classifica
        cur.execute("""
                    SELECT Nome_Squadra, Partite_Giocate, Vittorie, Punti
                    FROM Squadre
                    ORDER BY Vittorie DESC, Punti DESC
                    """)
        risultati = cur.fetchall()

    # Invia il messaggio finale
    messaggio = (
        "⛔ *Fine del torneo!* \n\n"
        "Il torneo è terminato. Le partite sono concluse.\n\n"
        "Complimenti a tutti i partecipanti.\n"
        "🔥 Le semifinali si giocheranno tra i primi 4 classificati:\n\n"
        f"1. `{risultati[0][0]}`\n"
        f"2. `{risultati[1][0]}`\n"
        f"3. `{risultati[2][0]}`\n"
        f"4. `{risultati[3][0]}`\n\n"
        "Preparati per l'ultima fase del torneo!"
    )

    # Ottieni tutti gli utenti
    with sqlite3.connect("Torneo_Molkky.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT ID_Telegram FROM Utenti")
        utenti = [r[0] for r in cur.fetchall()]

    # Invia il messaggio a tutti gli utenti
    for user_id in utenti:
        try:
            await context.bot.send_message(user_id, messaggio, parse_mode = "Markdown")
        except Exception as e:
            print(f"[Errore invio a {user_id}]: {e}")

    # Conferma la chiusura al comando admin
    await update.message.reply_text("✅ Torneo terminato. Tutti sono ora osservatori. Le semifinali sono in arrivo.")






#Gestione modifica punteggio
async def inizia_modifica_punteggio(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Non sei autorizzato.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT Lista_Match, Set_1 FROM Partite WHERE Status_Partita = 'giocata' AND Set_1 != ''")
        partite = cur.fetchall()

    if not partite:
        await update.message.reply_text("❌ Nessuna partita giocata con punteggio trovato.")
        return ConversationHandler.END

    keyboard = [
    [InlineKeyboardButton(
        text=f"{match} ({set1})",
        callback_data=f"{match} {set1}"
    )]
        for match, set1 in partite
    ]
    await update.message.reply_text("📝 Seleziona la partita da modificare:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SCELTA_PARTITA


async def seleziona_partita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data  # es. "LUPI-POTA [25,LUPI - 50,POTA]"
    try:
        # Divido il nome match e il punteggio (split solo alla prima occorrenza di spazio)
        nome_match, set_1 = callback_data.split(" ", 1)

        # tolgo parentesi quadre da set_1, se ci sono
        set_1 = set_1.strip("[]")

        # salvo il match per i prossimi step
        context.user_data["match"] = nome_match
        context.user_data["set_1"] = set_1

        # divido i due lati della partita
        s1_raw, s2_raw = set_1.split(" - ")

        # per ciascuno separo punteggio e nome squadra
        punteggio1_str, squadra1 = s1_raw.split(",", 1)
        punteggio2_str, squadra2 = s2_raw.split(",", 1)

        # converto in interi i punteggi
        punteggio1 = int(punteggio1_str.strip())
        punteggio2 = int(punteggio2_str.strip())

        # salvo in user_data per il prossimo step
        context.user_data["vecchio_punteggio"] = (punteggio1, punteggio2)
        context.user_data["squadra1"] = squadra1.strip()
        context.user_data["squadra2"] = squadra2.strip()

        # chiedo il nuovo punteggio all'utente
        await query.message.reply_text(
            f"Inserisci il nuovo punteggio per:\n"
            f"{squadra1.strip()} - {squadra2.strip()}\n"
            f"(formato: 50-30 dove {squadra1.strip()} è a sinistra e {squadra2.strip()} a destra)"
        )
        return INSERISCI_PUNTEGGIO

    except Exception as e:
        await query.message.reply_text(f"❌ Formato callback_data non riconosciuto.\nErrore: {e}")
        return ConversationHandler.END


async def aggiorna_punteggio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo = update.message.text.strip()
    try:
        nuovo1, nuovo2 = map(int, testo.split("-"))
    except:
        await update.message.reply_text("⚠️ Formato non valido. Usa il formato `punteggio1 - punteggio2`.")
        return INSERISCI_PUNTEGGIO

    squadra1 = context.user_data.get("squadra1")
    squadra2 = context.user_data.get("squadra2")
    match = "-".join(sorted([squadra1, squadra2]))
    vecchio1, vecchio2 = context.user_data["vecchio_punteggio"]

    # calcola modifiche
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # 1. annulla effetti del vecchio punteggio
        for squadra, punteggio in zip((squadra1, squadra2), (vecchio1, vecchio2)):
            cur.execute("UPDATE Squadre SET Partite_Giocate = Partite_Giocate - 1, Punti = Punti - ? WHERE Nome_Squadra = ?", (punteggio, squadra))

        # togli vittoria precedente
        if vecchio1 == 50:
            cur.execute("UPDATE Squadre SET Vittorie = Vittorie - 1 WHERE Nome_Squadra = ?", (squadra1,))
        elif vecchio2 == 50:
            cur.execute("UPDATE Squadre SET Vittorie = Vittorie - 1 WHERE Nome_Squadra = ?", (squadra2,))

        # 2. applica nuovo punteggio
        for squadra, punteggio in zip((squadra1, squadra2), (nuovo1, nuovo2)):
            cur.execute("UPDATE Squadre SET Partite_Giocate = Partite_Giocate + 1, Punti = Punti + ? WHERE Nome_Squadra = ?", (punteggio, squadra))

        # aggiungi vittoria corretta
        if nuovo1 == 50:
            cur.execute("UPDATE Squadre SET Vittorie = Vittorie + 1 WHERE Nome_Squadra = ?", (squadra1,))
        elif nuovo2 == 50:
            cur.execute("UPDATE Squadre SET Vittorie = Vittorie + 1 WHERE Nome_Squadra = ?", (squadra2,))

        # aggiorna la tabella Partite
        cur.execute("UPDATE Partite SET Set_1 = ? WHERE Lista_Match = ?", (f"[{nuovo1},{squadra1} - {nuovo2},{squadra2}]", match))
        conn.commit()

    await update.message.reply_text("✅ Punteggio aggiornato con successo.")
    return ConversationHandler.END

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operazione annullata.")
    return ConversationHandler.END

admin_modifica_punteggio = ConversationHandler(
    entry_points=[CommandHandler("modifica_punteggio", inizia_modifica_punteggio)],
    states={
        SCELTA_PARTITA: [CallbackQueryHandler(seleziona_partita)],
        INSERISCI_PUNTEGGIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, aggiorna_punteggio)],
    },
    fallbacks=[CommandHandler("annulla", annulla)],
)


#------------------------------------------
# confere azioni
'''async def chiedi_conferma(update: Update, context: ContextTypes.DEFAULT_TYPE, funzione_target: str, messaggio: str):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Conferma", callback_data=f"conferma_azione:{funzione_target}"),
         InlineKeyboardButton("❌ Annulla", callback_data="annulla_azione")]
    ])
    await update.message.reply_text(messaggio, parse_mode="Markdown", reply_markup=keyboard)

async def gestisci_callback_conferma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("conferma_azione:"):
        nome_funzione = data.split(":")[1]

        # ESECUZIONE DINAMICA
        funzione = globals().get(nome_funzione)
        if funzione:
            await funzione(update, context)
        else:
            await query.edit_message_text("❌ Errore: funzione non trovata.")

    elif data == "annulla_azione":
        await query.edit_message_text("❌ Azione annullata.")'''

