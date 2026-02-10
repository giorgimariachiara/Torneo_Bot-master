from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from itertools import combinations
from utils.db import *
import asyncio
from utils import globals
import sqlite3
import re
import time


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

    # Girone della squadra utente
    cur.execute("SELECT Girone FROM Squadre WHERE Nome_Squadra = ?", (squadra_utente,))
    r = cur.fetchone()
    if not r:
        print(f"❌ Squadra non trovata: {squadra_utente}")
        return
    girone = r[0]

    # Altre squadre SOLO dello stesso girone
    cur.execute("""
           SELECT Nome_Squadra
           FROM Squadre
           WHERE Nome_Squadra != ?
             AND Girone = ?
       """, (squadra_utente, girone))
    altre_squadre = [row[0] for row in cur.fetchall()]

    if not altre_squadre:
        print(f"ℹ️ Nessuna squadra nello stesso girone ({girone}) per {squadra_utente}")
        return

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




def _split_match(match_nome: str):
    # Richiede che i nomi squadra NON contengano '-'
    return match_nome.split("-", 1)

def _match_nome(s1: str, s2: str) -> str:
    return f"{s1}-{s2}" if s1 < s2 else f"{s2}-{s1}"

def _girone_squadra(cur, nome_squadra: str):
    cur.execute("SELECT Girone FROM Squadre WHERE Nome_Squadra = ?", (nome_squadra,))
    r = cur.fetchone()
    return r[0] if r else None

def _girone_da_match(cur, match_nome: str):
    try:
        s1, s2 = _split_match(match_nome)
    except ValueError:
        return None

    cur.execute("""
        SELECT sA.Girone, sB.Girone
        FROM Squadre sA
        JOIN Squadre sB ON sB.Nome_Squadra = ?
        WHERE sA.Nome_Squadra = ?
    """, (s2, s1))
    r = cur.fetchone()
    if not r:
        return None
    g1, g2 = r
    return g1 if g1 == g2 else None

def _prendi_campo_libero_del_girone(cur, girone):
    cur.execute("""
        SELECT ID_Campo
        FROM Campi
        WHERE Girone = ?
          AND (Match IS NULL OR Match = '')
        ORDER BY ID_Campo
        LIMIT 1
    """, (girone,))
    r = cur.fetchone()
    return r[0] if r else None

async def assegna_partita(bot: Bot, user_id=None, update=None, squadra_trigger: str | None = None):
    print('operation -> assegna_partita')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # 0) Recupera squadra_trigger se non passata (da user_id).
        #    Se hai già una tua funzione, sostituisci questo blocco.
        if squadra_trigger is None:
            if user_id is None:
                return "errore_squadra"

        # 1) Determina girone della squadra trigger
        girone = _girone_squadra(cur, squadra_trigger)
        if girone is None:
            return "errore_squadra"

        # 2) Controllo: c'è almeno un campo libero nel girone? (non influenzi altri gironi)
        campo_id = _prendi_campo_libero_del_girone(cur, girone)
        if campo_id is None:
            return "tutti_occupati"

        # 3) Recupera squadre disponibili SOLO nello stesso girone
        cur.execute("""
            SELECT Nome_Squadra,
                   COALESCE(Partite_Giocate, 0) as Partite_Giocate,
                   COALESCE(Vittorie, 0) as Vittorie
            FROM Squadre
            WHERE Status = 'disponibile'
              AND Girone = ?
        """, (girone,))
        disponibili = cur.fetchall()

        if len(disponibili) < 2:
            return "nessuna_partita_disponibile"

        # mappa: Nome_Squadra -> (Partite_Giocate, Vittorie)
        info_squadre = {s[0]: (int(s[1]), int(s[2])) for s in disponibili}

        # 4) Genera coppie possibili.
        #    CONSIGLIATO: la disponibilità "attiva" la squadra trigger => match solo con trigger
        nomi_altre = [s[0] for s in disponibili if s[0] != squadra_trigger]
        if not nomi_altre:
            return "nessuna_partita_disponibile"

        match_possibili = [(squadra_trigger, altra) for altra in nomi_altre]

        def distanza(s1, s2):
            pj1, v1 = info_squadre[s1]
            pj2, v2 = info_squadre[s2]
            return 2 * abs(pj1 - pj2) + abs(v1 - v2)

        match_possibili.sort(key=lambda pair: (
            info_squadre[pair[0]][0] + info_squadre[pair[1]][0],  # chi ha giocato meno
            distanza(pair[0], pair[1])                            # qualità match
        ))
        print("operations -> match in coda (girone)", girone, ":", match_possibili)

        for squadra1, squadra2 in match_possibili:
            match_nome = _match_nome(squadra1, squadra2)

            # 5) Verifica che il match esista ed è "non giocata"
            cur.execute("SELECT Status_Partita FROM Partite WHERE Lista_Match = ?", (match_nome,))
            riga = cur.fetchone()
            if not riga or riga[0] != "non giocata":
                continue

            # 6) Sicurezza: verifica che il match appartenga allo stesso girone (derivato dalle squadre)
            girone_match = _girone_da_match(cur, match_nome)
            if girone_match is None or girone_match != girone:
                continue

            # 7) (Re)prendi un campo libero nel girone e occupalo in modo “sicuro”
            campo_id = _prendi_campo_libero_del_girone(cur, girone)
            if campo_id is None:
                return "tutti_occupati"

            # Metti partita "in attesa" (solo se era "non giocata")
            cur.execute("""
                UPDATE Partite
                SET Status_Partita = 'in attesa'
                WHERE Lista_Match = ?
                  AND Status_Partita = 'non giocata'
            """, (match_nome,))
            if cur.rowcount == 0:
                conn.rollback()
                continue

            # Occupa il campo SOLO del girone (Match NULL/'' => libero)
            cur.execute("""
                UPDATE Campi
                SET Match = ?
                WHERE ID_Campo = ?
                  AND Girone = ?
                  AND (Match IS NULL OR Match = '')
            """, (match_nome, campo_id, girone))
            if cur.rowcount == 0:
                conn.rollback()
                return "tutti_occupati"

            conn.commit()

            # 8) Notifica utenti delle due squadre
            utenti_s1 = get_utenti_della_squadra(squadra1)
            utenti_s2 = get_utenti_della_squadra(squadra2)
            tutti_utenti = utenti_s1 + utenti_s2
            print("operations -> squadre tutti utenti:", tutti_utenti)

            messages = []

            for uid in tutti_utenti:
                try:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Siamo pronti!", callback_data=f"pronti|{match_nome}")],
                        [InlineKeyboardButton("❌ Non possiamo giocare ora", callback_data=f"rifiuto|{match_nome}")]
                    ])
                    message = await bot.send_message(
                        chat_id=uid,
                        text=(
                            "🎯 La tua squadra è stata selezionata per giocare!\n\n"
                            f"🏟️ Campo: {campo_id} (Girone {girone})\n"
                            "⏳ Hai 3 minuti per confermare la presenza!"
                        ),
                        parse_mode="Markdown",
                        reply_markup=keyboard,
                    )
                    messages.append((uid, message.message_id))
                except Exception as e:
                    print(f"Errore nell'invio a {uid}: {e}")

            # 9) Inserisce gli utenti attesi nel DB (consigliato: ripulisci eventuali vecchi record)
            cur.execute("DELETE FROM Conferme WHERE Match = ?", (match_nome,))
            utenti_attesi = set(tutti_utenti)
            for uid in utenti_attesi:
                cur.execute(
                    "INSERT INTO Conferme (Match, User_ID, Confermato) VALUES (?, ?, 0)",
                    (match_nome, uid)
                )
            conn.commit()

            # 10) Aggiorna stato squadre (attenzione: ideale farlo nella stessa connessione)
            set_squadra_in_gioco(squadra1)
            set_squadra_in_gioco(squadra2)

            # 11) Avvia timeout conferme
            task = asyncio.create_task(attendi_conferme(match_nome, utenti_attesi, bot, messages))
            globals.TASKS_IN_ATTESA[match_nome] = task
            print("assegna partita,messages--> ", messages)

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
                cur.execute("UPDATE Campi SET Match = NULL WHERE Match = ?",(match_nome,))
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

'''async def conferma_prontezza(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                print(f"Errore invio conferma a {uid}: {e}")'''



async def conferma_prontezza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("operations -> conferma_prontezza")
    query = update.callback_query
    await query.answer()

    # callback_data attesa: "pronti|SquadraA-SquadraB" oppure "rifiuto|SquadraA-SquadraB"
    data = query.data or ""
    try:
        azione, match_nome = data.split("|", 1)
    except ValueError:
        await query.edit_message_text("⚠️ Errore nel comando.")
        return

    user_id = query.from_user.id

    # Validazione match
    try:
        squadra1, squadra2 = match_nome.split("-", 1)
    except ValueError:
        await query.edit_message_text("⚠️ Match non valido.")
        return

    utenti_s1 = [int(uid) for uid in get_utenti_della_squadra(squadra1)]
    utenti_s2 = [int(uid) for uid in get_utenti_della_squadra(squadra2)]
    tutti_utenti = utenti_s1 + utenti_s2

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # --- RIFIUTO ---
        if azione == "rifiuto":
            # determina squadra che rifiuta
            if user_id in utenti_s1:
                squadra_rifiuto = squadra1
            elif user_id in utenti_s2:
                squadra_rifiuto = squadra2
            else:
                await query.edit_message_text("❌ Errore: non appartieni a nessuna delle squadre.")
                return

            squadra_altro = squadra2 if squadra_rifiuto == squadra1 else squadra1

            # Aggiorna stati squadre
            set_squadra_indisponibile(squadra_rifiuto)
            set_squadra_disponibile(squadra_altro)

            # Ripristina DB partita + pulizia + libera campo
            cur.execute("UPDATE Partite SET Status_Partita = 'non giocata' WHERE Lista_Match = ?", (match_nome,))
            cur.execute("DELETE FROM Conferme WHERE Match = ?", (match_nome,))
            cur.execute("UPDATE Campi SET Match = NULL WHERE Match = ?", (match_nome,))
            conn.commit()

            # Annulla task timeout se attivo
            task = globals.TASKS_IN_ATTESA.pop(match_nome, None)
            if task:
                task.cancel()

            # Notifica gli altri utenti coinvolti
            for uid in tutti_utenti:
                if uid == user_id:
                    continue
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"⚠️ La partita `{match_nome}` è stata annullata.\nUna squadra ha dichiarato indisponibilità. ⛔️",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"Errore invio annullamento a {uid}: {e}")

            await query.edit_message_text("🚫 Hai annullato la partecipazione. La partita è stata annullata.")
            return

        # --- CONFERMA ("pronti") ---
        if azione != "pronti":
            await query.edit_message_text("⚠️ Azione non riconosciuta.")
            return

        # segna conferma dell'utente
        cur.execute(
            "UPDATE Conferme SET Confermato = 1 WHERE Match = ? AND User_ID = ?",
            (match_nome, user_id)
        )
        conn.commit()

        # Leggi confermati
        cur.execute("""
            SELECT DISTINCT User_ID
            FROM Conferme
            WHERE Match = ?
              AND Confermato = 1
        """, (match_nome,))
        confermati = {row[0] for row in cur.fetchall()}

        # Basta 1 conferma per squadra
        s1_confermata = any(uid in confermati for uid in utenti_s1)
        s2_confermata = any(uid in confermati for uid in utenti_s2)

    await query.edit_message_text("✅ Hai confermato! In attesa dell'altra squadra...")

    # Se entrambe le squadre hanno almeno 1 conferma => partita parte
    if s1_confermata and s2_confermata:
        # Annulla task timeout
        task = globals.TASKS_IN_ATTESA.pop(match_nome, None)
        if task:
            task.cancel()

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()

            # aggiorna partita e squadre
            cur.execute(
                "UPDATE Partite SET Status_Partita = 'in gioco', Durata = ? WHERE Lista_Match = ?",
                (time.time(), match_nome)
            )
            cur.execute(
                "UPDATE Squadre SET Status = 'in gioco' WHERE Nome_Squadra IN (?, ?)",
                (squadra1, squadra2)
            )
            cur.execute("DELETE FROM Conferme WHERE Match = ?", (match_nome,))

            # prende il campo già assegnato (NON riassegnare un campo nuovo)
            cur.execute("SELECT ID_Campo FROM Campi WHERE Match = ? LIMIT 1", (match_nome,))
            r = cur.fetchone()
            id_campo = r[0] if r else None

            conn.commit()

        campo_txt = f"`{id_campo}`" if id_campo is not None else "`?`"

        for uid in tutti_utenti:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        "❗️❗️ Le squadre hanno confermato ❗️❗️\n\n"
                        f"Recati al campo numero >> {campo_txt} << !\n\n"
                        f"La partita può iniziare:\n\n`{match_nome}` 🏆"
                    ),
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
    risultato = await assegna_partita(context.bot, user_id=user_id, update=update, squadra_trigger=squadra_utente)
    msg = update.message or update.callback_query.message

    if risultato == "tutti_occupati":
        await msg.reply_text("🚫 Tutti i campi sono occupati, verrai avvisato quando sarà il tuo turno!")
    elif risultato == "nessuna_partita_disponibile":
        await msg.reply_text("⌛ Nessun avversario disponibile al momento.\n\n Invita gli altri a iscriversi")
    elif risultato == "partita_assegnata":
        pass #msg.reply_text("✅ Sei stato assegnato a una partita! Controlla il messaggio con i dettagli del match.")

