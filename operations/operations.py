from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from itertools import combinations
from utils.db import *
import asyncio
from utils import globals

#Cambiare questa variabile in base al numero di campi che si hanno
MAX_PARTITE_IN_CORSO = 8
#generazione tabella Campi
def genera_tabella_campi(n_campi):
    import sqlite3

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Elimina tutte le righe dalla tabella Campi
        cur.execute("DELETE FROM Campi;")

        # Resetta l'auto-incremento dell'id (opzionale)
        cur.execute("DELETE FROM sqlite_sequence WHERE name='Campi';")

        # Inserisce n_campi righe con match = NULL
        for _ in range(n_campi):

            cur.execute("INSERT INTO Campi (match) VALUES (NULL);")
    # commit e close automatici

    conn.close()
genera_tabella_campi(MAX_PARTITE_IN_CORSO)








def genera_match_per_squadra(squadra_utente: str, cur: sqlite3.Cursor):
    print('operation -> genera_match_per_squadra')

    # Ottieni tutte le altre squadre
    cur.execute("SELECT Nome_Squadra FROM Squadre WHERE Nome_Squadra != ?", (squadra_utente,))
    altre_squadre = [row[0] for row in cur.fetchall()]

    for altra in altre_squadre:
        nomi = sorted([squadra_utente, altra])
        match_nome = f"{nomi[0]}-{nomi[1]}"

        # Verifica se il match esiste già
        cur.execute("SELECT 1 FROM Partite WHERE Lista_Match = ?", (match_nome,))
        esiste = cur.fetchone()

        if not esiste:
            print(f"✔️ Genero partita: {match_nome}")
            cur.execute(
                "INSERT INTO Partite (Lista_Match, Set_1, Status_Partita, Durata) VALUES (?, '', 'non giocata', '')",
                (match_nome,)
            )
        else:
            print(f"⏩ Match già esistente: {match_nome}")

async def assegna_partita(bot: Bot, user_id=None, update=None):
    print('operation -> assegna_partita')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # 1. Controlla il numero di partite in corso
        cur.execute("SELECT COUNT(*) FROM Partite WHERE Status_Partita = 'in gioco' OR 'in attesa'")
        partite_in_corso = cur.fetchone()[0]

        if partite_in_corso >= MAX_PARTITE_IN_CORSO:
            return "tutti_occupati"

        # 2. Recupera le squadre disponibili con il numero di partite giocate
        cur.execute("""
                    SELECT Nome_Squadra, Partite_Giocate, Vittorie
                    FROM Squadre
                    WHERE Status = 'disponibile'
                    """)
        disponibili = cur.fetchall()

        if len(disponibili) < 2:
            return "nessuna_partita_disponibile"

        # 3. Ordina per numero di partite giocate
        disponibili = [x for x in disponibili if x[1] is not None and x[2] is not None]

        # 4. Ordina per partite giocate e poi vittorie (priorità alle meno attive)
        disponibili.sort(key=lambda x: (x[1], x[2]))

        nomi_squadre = [s[0] for s in disponibili]
        info_squadre = {s[0]: (int(s[1]), int(s[2])) for s in disponibili}  # mappa: Nome_Squadra -> (Partite_Giocate, Vittorie)

        # 5. Crea tutte le possibili coppie e calcola la distanza
        match_possibili = list(combinations(nomi_squadre, 2))

        def distanza(s1, s2):
            pj1, v1 = info_squadre[s1]
            pj2, v2 = info_squadre[s2]
            return 2 * abs(pj1 - pj2) + abs(v1 - v2)

        # 6. Ordina le coppie in base alla distanza minima
        match_possibili.sort(key=lambda pair: (
            info_squadre[pair[0]][0] + info_squadre[pair[1]][0],  # priorità a chi ha giocato meno
            distanza(pair[0], pair[1])                                # qualità del match
        ))
        print("operations -> squadre match in coda:", match_possibili)

        for squadra1, squadra2 in match_possibili:
            match_nome = f"{squadra1}-{squadra2}" if squadra1 < squadra2 else f"{squadra2}-{squadra1}"

            # 7. Verifica che il match esista ed è "non giocata"
            cur.execute("SELECT Status_Partita FROM Partite WHERE Lista_Match = ?", (match_nome,))
            riga = cur.fetchone()

            if riga and riga[0] == "non giocata":
                # 8. Notifica agli utenti delle due squadre
                utenti_s1 = get_utenti_della_squadra(squadra1)
                utenti_s2 = get_utenti_della_squadra(squadra2)
                tutti_utenti = utenti_s1 + utenti_s2
                print("operations -> squadre tutti utenti:", tutti_utenti)

                # Lista per raccogliere i messaggi inviati
                messages = []

                for uid in tutti_utenti:
                    try:
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ Siamo pronti!", callback_data=f"pronti_{match_nome}_{uid}")],
                            [InlineKeyboardButton("❌ Non possiamo giocare ora",
                                                  callback_data=f"rifiuto_{match_nome}_{uid}")]
                        ])
                        message = await bot.send_message(
                            chat_id=uid,
                            text=f"🎯 La tua squadra è stata selezionata per giocare!\n\n"
                                 f"⏳ Hai 3 minuti per confermare la presenza!",
                            parse_mode="Markdown",
                            reply_markup=keyboard,
                        )

                        messages.append((uid, message.message_id)) # salva (chat_id, message_id)

                    except Exception as e:
                        print(f"Errore nell'invio a {uid}: {e}")

                # 9. Inserisce gli utenti attesi nel DB
                utenti_attesi = set(tutti_utenti)
                for uid in utenti_attesi:
                    cur.execute("INSERT INTO Conferme (Match, User_ID,Confermato) VALUES (?, ?,0)", (match_nome, uid))

                # 10. Aggiorna stato partita e squadre
                cur.execute("UPDATE Partite SET Status_Partita = 'in attesa' WHERE Lista_Match = ?", (match_nome,))
                conn.commit()
                set_squadra_in_gioco(squadra1)
                set_squadra_in_gioco(squadra2)


                # 11. Avvia il timeout per la conferma
                task = asyncio.create_task(attendi_conferme(match_nome, utenti_attesi, bot, messages))
                globals.TASKS_IN_ATTESA[match_nome] = task
                print("assegna partita,messages--> ",messages)

                # 13. Ritorna il risultato
                return "partita_assegnata"
        return "nessuna_partita_disponibile"


# Dopo aver notificato tutti
async def attendi_conferme(match_nome, utenti_attesi, bot, messages):
    print("operations -> attendi_conferme match_nome, utenti_attesi:", match_nome, utenti_attesi)
    try:
        await asyncio.sleep(180)  # 3 minuti

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM Conferme WHERE Match = ? AND Confermato = 1", (match_nome,))
            confermati = cur.fetchone()[0]

            if confermati >= len(utenti_attesi):
                print(f"Tutti hanno confermato per {match_nome}.")
                return  # già gestito
            else:
                # Timeout: annulla
                squadra1, squadra2 = match_nome.split("-")
                cur.execute("UPDATE Partite SET Status_Partita = 'non giocata' WHERE Lista_Match = ?", (match_nome,))
                cur.execute("UPDATE Squadre SET Status = 'indisponibile' WHERE Nome_Squadra IN (?, ?)", (squadra1, squadra2))
                cur.execute("DELETE FROM Conferme WHERE Match = ?", (match_nome,))
                conn.commit()

        for chat_id, message_id in messages:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                await bot.send_message(chat_id=chat_id,
                                       text="⚠️ La partita è stata annullata perché una squadra non ha confermato entro 3 minuti. Se vuoi giocare dai ancora la tua disponibilità!!")

            except Exception as e:
                print(f"Errore invio a {chat_id}: {e}")

    except asyncio.CancelledError:
        print(f"⏹️ Task per {match_nome} annullato: conferme ricevute.")
        return

async def conferma_prontezza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("operations -> conferma_prontezza")
    query = update.callback_query
    await query.answer()

    data = query.data
    pattern = r"^(pronti|rifiuto)_(.*)_(\d+)$"
    match = re.match(pattern, data)

    if not match:
        await query.edit_message_text("⚠️ Errore nel comando.")
        return

    azione, match_nome, user_id = match.groups()
    user_id = int(user_id)

    squadra1, squadra2 = match_nome.split("-")
    utenti_s1 = [int(uid) for uid in get_utenti_della_squadra(squadra1)]
    utenti_s2 = [int(uid) for uid in get_utenti_della_squadra(squadra2)]

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        if azione == "rifiuto":
            # Capisci a quale squadra appartiene
            if user_id in utenti_s1:
                squadra_rifiuto = squadra1
            elif user_id in utenti_s2:
                squadra_rifiuto = squadra2
            else:
                await query.edit_message_text("❌ Errore: non appartieni a nessuna delle squadre.")
                return

            # Imposta la squadra come indisponibile
            set_squadra_indisponibile(squadra_rifiuto)
            # L'altra squadra torna disponibile
            squadra_altro = squadra2 if squadra_rifiuto == squadra1 else squadra1
            set_squadra_disponibile(squadra_altro)


            # Annulla la partita
            cur.execute("UPDATE Partite SET Status_Partita = 'non giocata' WHERE Lista_Match = ?", (match_nome,))
            cur.execute("DELETE FROM Conferme WHERE Match = ?", (match_nome,))
            conn.commit()

            # Annulla il task di attesa se attivo
            task = globals.TASKS_IN_ATTESA.pop(match_nome, None)
            if task:
                task.cancel()

            # Notifica agli utenti coinvolti
            tutti_utenti = utenti_s1 + utenti_s2
            for uid in tutti_utenti:
                try:
                    if uid == user_id:
                        continue
                    else:
                        await context.bot.send_message(
                            chat_id=uid,
                            text=f"⚠️ La partita `{match_nome}` è stata annullata.\n"
                                 f"Una squadra ha dichiarato indisponibilità. ⛔️",
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    print(f"Errore invio annullamento a {uid}: {e}")

            # Aggiorna messaggio originale
            await query.edit_message_text("🚫 Hai annullato la partecipazione. La partita è stata annullata.")
            return

        # Altrimenti, se ha confermato...
        cur.execute("UPDATE Conferme SET Confermato = 1 WHERE Match = ? AND User_ID = ?", (match_nome, user_id))
        conn.commit()

        s1_confermata = len(utenti_s1) == 0
        s2_confermata = len(utenti_s2) == 0

        cur.execute("""
            SELECT DISTINCT User_ID
            FROM Conferme
            WHERE Match = ?
              AND Confermato = 1
        """, (match_nome,))
        confermati = {row[0] for row in cur.fetchall()}

        if not s1_confermata:
            s1_confermata = any(uid in confermati for uid in utenti_s1)
        if not s2_confermata:
            s2_confermata = any(uid in confermati for uid in utenti_s2)

    await query.edit_message_text("✅ Hai confermato! In attesa degli altri membri...")

    if s1_confermata and s2_confermata:
        task = globals.TASKS_IN_ATTESA.pop(match_nome, None)
        print("operations -> task annullata: ", task)
        if task:
            task.cancel()

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE Partite SET Status_Partita = 'in gioco', Durata = ? WHERE Lista_Match = ?", (time.time(), match_nome))
            cur.execute("UPDATE Squadre SET Status = 'in gioco' WHERE Nome_Squadra IN (?, ?)", (squadra1, squadra2))
            cur.execute("DELETE FROM Conferme WHERE Match = ?", (match_nome,))



            conn.commit()

        utenti = utenti_s1 + utenti_s2
        id_campo = get_campo_libero_occupa_campo(match_nome)

        #Pulizia del messaggio precedente


        
        for uid in utenti:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"❗️❗️ Le squadre hanno confermato ❗️❗️\n\nRecati al campo numero >> `{id_campo}` << !\n\nLa partita può iniziare:\n\n`{match_nome}` 🏆",
                    parse_mode="Markdown",
                )
            except Exception as e:
                print(f"Errore invio conferma a {uid}: {e}")



# --- Funzione da chiamare in disponibilita.py ---
async def processa_disponibilita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('operation -> processa_disponibilita')
    user_id = update.effective_user.id

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Recupera la squadra dell'utente
        cur.execute("SELECT Squadra FROM Utenti WHERE id_telegram = ?", (user_id,))
        riga = cur.fetchone()
        if not riga:
            await update.message.reply_text("❗ Errore: la tua squadra non è stata trovata. Contatta un amministratore.")
            return
        squadra_utente = riga[0]

        # Verifica che la squadra esista
        cur.execute("SELECT COUNT(*) FROM Squadre WHERE Nome_Squadra = ?", (squadra_utente,))
        if cur.fetchone()[0] == 0:
            await update.message.reply_text("❗ Errore: la tua squadra non è registrata. Contatta un amministratore.")
            return

        # 🔄 Genera match se mancanti
        genera_match_per_squadra(squadra_utente, cur)
        conn.commit()

    # Procedi con l'assegnazione
    risultato = await assegna_partita(context.bot, user_id=user_id)
    msg = update.message or update.callback_query.message

    if risultato == "tutti_occupati":
        await msg.reply_text("🚫 Tutti i campi sono occupati, verrai avvisato quando sarà il tuo turno!")
    elif risultato == "nessuna_partita_disponibile":
        await msg.reply_text("⌛ Nessun avversario disponibile al momento.\n\n Invita gli altri a iscriversi")
    elif risultato == "partita_assegnata":
        pass #msg.reply_text("✅ Sei stato assegnato a una partita! Controlla il messaggio con i dettagli del match.")

