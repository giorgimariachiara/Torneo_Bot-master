# handlers/registra_partita.py
import time

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
    match = "-".join([squadra1, squadra2])
    risposta = update.message.text.strip().lower()
    if risposta == "❌ no":
        await update.message.reply_text("Contatta un amministratore per risolvere la situazione.",
                                        reply_markup=ReplyKeyboardRemove())
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
        print('gegiù')
        return PARTITA_INSERISCI_PUNTEGGIO2

    except Exception:
        await update.message.reply_text(
            f"❌ Punteggio inserito non valido!\n\n Inserisci nuovamente il punteggio della squadra: `{squadra1}`.",
            parse_mode="Markdown")
        return PARTITA_INSERISCI_PUNTEGGIO1


async def inserisci_punteggio_squadra2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    partita = context.user_data.get("partita_corrente")
    squadra1 = partita["squadra1"]
    squadra2 = partita["squadra2"]

    try:
        punteggio2 = int(update.message.text.strip())
        print(f"DEBUG: Il testo ricevuto è '{update.message.text}'")
        if not (0 <= punteggio2 <= 50):
            raise ValueError("Punteggio fuori intervallo")

        punti1 = context.user_data.get("punti_squadra1")
        print('punti squadra 1', punti1)
        # IMPORTANTE: Non usiamo più sorted() per distinguere Andata/Ritorno
        match_attuale = f"{squadra1}-{squadra2}"

        if not ((punti1 == 50 and punteggio2 < 50) or (punteggio2 == 50 and punti1 < 50)):
            raise ValueError("Formato non valido")

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT Status_Partita FROM Partite WHERE Lista_Match = ?", (match_attuale,))
            stato = cur.fetchone()
            if not stato or stato[0] != "bloccata":
                await update.message.reply_text("⚠️ Partita già registrata o non valida.")
                return MENU

        # 1. Registra il punteggio dell'andata
        esito = registra_punteggio_partita(squadra1, squadra2, punti1, punteggio2)
        if not esito:
            await update.message.reply_text("⚠️ Punteggio già registrato.")
            return MENU

        # 2. Notifica i giocatori
        user_id = update.effective_user.id
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id_telegram FROM Utenti WHERE Squadra = ? OR Squadra = ?", (squadra1, squadra2))
            utenti_coinvolti = [r[0] for r in cur.fetchall()]

        risultato_msg = (f"✅ Partita registrata!\n\n⚔️ `{squadra1}` {punti1} - {punteggio2} `{squadra2}`")
        for uid in utenti_coinvolti:
            if uid != user_id:
                try:
                    await context.bot.send_message(uid, risultato_msg, parse_mode="Markdown")
                except:
                    pass

        # --- LOGICA RITORNO IMMEDIATO ---
        match_ritorno = f"{squadra2}-{squadra1}"
        ritorno_avviato = False

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            # Controlla se il ritorno esiste ed è da giocare
            cur.execute("SELECT 1 FROM Partite WHERE Lista_Match = ? AND Status_Partita = 'non giocata'",
                        (match_ritorno,))
            if cur.fetchone():
                # Avvia il ritorno saltando le conferme
                cur.execute("UPDATE Partite SET Status_Partita = 'in gioco',Durata=? WHERE Lista_Match = ?",
                            (time.time(), match_ritorno,))
                # Manteniamo le squadre in stato 'in gioco' (già lo sono)
                conn.commit()
                ritorno_avviato = True

        if ritorno_avviato:
            # 1. Aggiorniamo i dati della partita nel "cervello" del bot (context)
            # Invertiamo squadra1 e squadra2 per il ritorno
            nuova_partita = {
                "squadra1": squadra2,  # Ora chi era squadra2 gioca come s1
                "squadra2": squadra1,
                # "durata":,
                "match": match_ritorno
            }

            context.user_data["partita_corrente"] = nuova_partita

            # 2. Aggiorniamo il riferimento del match nella tabella Campi
            # Invece di liberare il campo e rioccuparlo, aggiorniamo il nome del match associato
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("UPDATE Campi SET match = ? WHERE match = ?",
                            (match_ritorno, match_attuale))
                conn.commit()

            msg_ritorno = f"🔄 **RITORNO IMMEDIATO!**\n\nContinuate sul campo attuale.\n⚔️ `{squadra2}` (Casa) VS. `{squadra1}` (Trasferta)"
            for uid in utenti_coinvolti:
                await context.bot.send_message(uid, msg_ritorno, parse_mode="Markdown")

            await mostra_menu_principale(update, context)
            return MENU

        # --- SE NON C'E' RITORNO (Fine turno o già giocato) ---
        set_squadra_disponibile(squadra1)
        set_squadra_disponibile(squadra2)
        libera_campo(match_attuale)

        # Prova ad assegnare nuove partite ad altri
        await assegna_partita(context.bot, user_id=user_id)

        await update.message.reply_text("Andata e Ritorno completati! Siete tornati disponibili.")
        await mostra_menu_principale(update, context)
        return MENU

    except Exception as e:
        print("Errore inserimento punteggio 2:", e)
        await update.message.reply_text(f"❌ Errore. Inserisci un numero tra 0 e 50 (solo uno dei due deve essere 50).")
        return PARTITA_INSERISCI_PUNTEGGIO2


async def avvia_ritorno_immediato(match_ritorno, bot):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Verifica se il ritorno esiste ed è disponibile
        cur.execute("SELECT 1 FROM Partite WHERE Lista_Match = ? AND Status_Partita = 'non giocata'", (match_ritorno,))
        if not cur.fetchone():
            return False  # Non c'è ritorno o è già giocato

        # Recupera le squadre dal nome del match
        s1, s2 = match_ritorno.split("-")

        # Imposta subito la partita come 'in gioco' saltando 'in attesa'
        cur.execute("UPDATE Partite SET Status_Partita = 'in gioco' WHERE Lista_Match = ?", (match_ritorno,))

        # Opzionale: Se hai una tabella Campi, rioccupa il campo per questo match
        # rioccupa_campo(match_ritorno, campo_precedente)

        # Blocca le squadre
        set_squadra_in_gioco(s1)
        set_squadra_in_gioco(s2)

        conn.commit()
        return True


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
