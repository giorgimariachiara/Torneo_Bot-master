# utils/db.py
import sqlite3
import re
import time



DB_PATH = "Torneo_Molkky.db"

def crea_o_trova_utente(user_id: int, nome: str) -> bool:
    print('db -> crea_o_trova_utente')

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Controlla se l'utente esiste già tramite ID
        cur.execute("SELECT id_telegram FROM Utenti WHERE id_telegram = ?", (user_id,))
        if cur.fetchone():
            return False  # Utente già presente

        # Controlla se il nome è già usato
        cur.execute("SELECT Nome_Utente FROM Utenti WHERE Nome_Utente = ?", (nome,))
        esiste_nome = cur.fetchone()

        nome_unico = nome
        counter = 1

        # Finché il nome è già usato, aggiunge un suffisso numerico
        while esiste_nome:
            nome_unico = f"{nome}_{counter}"
            cur.execute("SELECT Nome_Utente FROM Utenti WHERE Nome_Utente = ?", (nome_unico,))
            esiste_nome = cur.fetchone()
            counter += 1

        # Inserisce nuovo utente con nome unico
        cur.execute("INSERT INTO Utenti (id_telegram, Nome_Utente) VALUES (?, ?)", (user_id, nome_unico))
        conn.commit()
        print(f"[INFO] Nuovo utente creato: {user_id} - {nome_unico}")
        return True


def utente_esiste(user_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM Utenti WHERE id_telegram = ?", (user_id,))
        return cur.fetchone() is not None


def cancella_utente_completo(user_id: int):
    print(f"db -> cancella_utente_completo (ID: {user_id})")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Recupera il nome dell'utente
        cur.execute("SELECT Nome_Utente FROM Utenti WHERE id_telegram = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            print(f"[INFO] Nessun utente trovato con ID {user_id}")
            return False

        nome_utente = row[0]

        # Rimuovi l'utente dalla colonna 'Giocatori' di tutte le squadre
        cur.execute("SELECT Nome_Squadra, Giocatori FROM Squadre")
        squadre = cur.fetchall()

        for nome_squadra, giocatori_str in squadre:
            if giocatori_str:
                giocatori = [g.strip() for g in giocatori_str.split(",")]
                if nome_utente in giocatori:
                    giocatori.remove(nome_utente)
                    nuovo_valore = ", ".join(giocatori)
                    cur.execute(
                        "UPDATE Squadre SET Giocatori = ? WHERE Nome_Squadra = ?",
                        (nuovo_valore, nome_squadra)
                    )
                    print(f"[INFO] Rimosso {nome_utente} dalla squadra '{nome_squadra}'")

        # Cancella l'utente dalla tabella Utenti
        cur.execute("DELETE FROM Utenti WHERE id_telegram = ?", (user_id,))
        conn.commit()
        print(f"[INFO] Utente {user_id} eliminato con successo.")

    return True

def aggiorna_giocante(user_id: int, nome: str, stato: bool):
    print('db -> aggiorna_giocante')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE Utenti SET Giocante = ? WHERE id_telegram = ?", (stato, user_id))
        conn.commit()

def aggiorna_squadra(user_id: int, nome_squadra: str):
    print('db -> aggiorna_squadra')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Recupera il nome dell'utente
        cur.execute("SELECT Nome_Utente FROM Utenti WHERE ID_Telegram = ?", (user_id,))
        result = cur.fetchone()
        if not result:
            print("⚠️ Utente non trovato.")
            return

        nome_utente = result[0]

        # Aggiorna la squadra dell'utente
        cur.execute("""
            UPDATE Utenti
            SET Squadra = ?
            WHERE ID_Telegram = ?
        """, (nome_squadra, user_id))

        # Recupera i giocatori attuali della squadra
        cur.execute("SELECT Giocatori FROM Squadre WHERE Nome_Squadra = ?", (nome_squadra,))
        result = cur.fetchone()
        if result:
            giocatori_attuali = result[0] or ""
            elenco = [n.strip() for n in giocatori_attuali.split(",") if n.strip()]
            if nome_utente not in elenco:
                elenco.append(nome_utente)
            nuovo_valore = ", ".join(elenco)
        else:
            nuovo_valore = nome_utente

        # Aggiorna la colonna Giocatori
        cur.execute("""
            UPDATE Squadre
            SET Giocatori = ?
            WHERE Nome_Squadra = ?
        """, (nuovo_valore, nome_squadra))

        conn.commit()


def aggiungi_squadra(nome: str):
    print(f"db -> aggiungi_squadra ({nome})")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Verifica se la squadra esiste già
        cur.execute("SELECT 1 FROM Squadre WHERE Nome_Squadra = ?", (nome,))
        if cur.fetchone():
            print(f"[INFO] La squadra {nome} esiste già.")
            return False

        # Aggiungi la nuova squadra
        cur.execute("INSERT INTO Squadre (Nome_Squadra,Partite_Giocate, Vittorie, Punti, Status) VALUES (?, ?, ?, ?, ?)", (nome, 0, 0, 0, "indisponibile"))
        print(f"[INFO] Squadra {nome} aggiunta.")

        # Recupera le altre squadre già presenti
        cur.execute("SELECT Nome_Squadra FROM Squadre WHERE Nome_Squadra != ?", (nome,))
        altre_squadre = [row[0] for row in cur.fetchall()]

        # Crea i match (una sola riga per coppia ordinata)
        for altra in altre_squadre:
            squadre = sorted([nome, altra])  # normalizza ordine
            match = f"{squadre[0]}-{squadre[1]}"

            # Inserisci il match solo se non esiste già
            cur.execute("SELECT 1 FROM Partite WHERE Lista_Match = ?", (match,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO Partite (Lista_Match, Status_Partita) VALUES (?, ?)",
                    (match, "non giocata")
                )
                print(f"[INFO] Match {match} creato.")

        conn.commit()

    return True


def cancella_squadra_completa(nome_squadra: str):
    print(f"db -> cancella_squadra_completa (Nome squadra: {nome_squadra})")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # 1. Scollega tutti gli utenti dalla squadra
        cur.execute("UPDATE Utenti SET Squadra = NULL WHERE Squadra = ?", (nome_squadra,))
        utenti_modificati = cur.rowcount
        print(f"[INFO] {utenti_modificati} utenti scollegati dalla squadra {nome_squadra}.")

        # 2. Elimina la squadra dalla tabella Squadre
        cur.execute("DELETE FROM Squadre WHERE Nome_Squadra = ?", (nome_squadra,))
        squadre_eliminate = cur.rowcount
        conn.commit()

        if squadre_eliminate:
            print(f"[INFO] Squadra {nome_squadra} cancellata dal database.")
            return True
        else:
            print(f"[WARN] Nessuna squadra chiamata {nome_squadra} trovata.")
            return False


def aggiungi_giocatore_a_squadra(user_name: str, squadra: str):
    print('db -> aggiungi_giocatore_a_squadra')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT Giocatori FROM Squadre WHERE Nome_Squadra = ?", (squadra,))
        risultato = cur.fetchone()
        if risultato:
            giocatori = risultato[0] or ""
            lista = [nome.strip() for nome in giocatori.split(",") if nome.strip()]
            if user_name not in lista:
                lista.append(user_name)
                cur.execute("UPDATE Squadre SET Giocatori = ? WHERE Nome_Squadra = ?", (", ".join(lista), squadra))
                conn.commit()


def aggiorna_status_squadra(user_id: int, disponibile: bool) -> str:
    print(f"db -> aggiorna_status_squadra (user_id: {user_id}, disponibile: {disponibile})")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Trova la squadra dell'utente
        cur.execute("SELECT Squadra FROM Utenti WHERE id_telegram = ?", (user_id,))
        result = cur.fetchone()

        if not result or not result[0]:
            print("[ERRORE] Nessuna squadra assegnata all'utente.")
            return "❗ Non risulti assegnato a nessuna squadra. Contatta un amministratore."

        nome_squadra = result[0]

        # Verifica che la squadra esista
        cur.execute("SELECT 1 FROM Squadre WHERE Nome_Squadra = ?", (nome_squadra,))
        squadra_esiste = cur.fetchone()

        if not squadra_esiste:
            print(f"[ERRORE] Squadra '{nome_squadra}' non esiste nella tabella Squadre.")
            return f"❗ La tua squadra '{nome_squadra}' non esiste nel sistema. Contatta un amministratore."

        # Aggiorna lo status della squadra
        nuovo_status = "disponibile" if disponibile else "indisponibile"
        cur.execute("UPDATE Squadre SET Status = ? WHERE Nome_Squadra = ?", (nuovo_status, nome_squadra))
        conn.commit()

        print(f"[INFO] Status della squadra '{nome_squadra}' aggiornato a '{nuovo_status}'.")
        return "ok"

def set_squadra_in_gioco(nome_squadra: str):
    print('db -> set_squadra_in_gioco:', nome_squadra)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE Squadre SET Status = 'in gioco' WHERE Nome_Squadra = ?", (nome_squadra,))
        conn.commit()

def set_squadra_indisponibile(nome_squadra: str):
    print('db -> set_squadra_indisponibile:', nome_squadra)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE Squadre SET Status = 'indisponibile' WHERE Nome_Squadra = ?", (nome_squadra,))
        conn.commit()

def set_squadra_disponibile(nome_squadra: str):
    print('db -> set_squadra_disponibile:', nome_squadra)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE Squadre SET Status = 'disponibile' WHERE Nome_Squadra = ?", (nome_squadra,))
        conn.commit()

def get_utenti_della_squadra(nome_squadra: str) -> list[int]:
    print('db -> get_utenti_della_squadra',nome_squadra)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id_telegram FROM Utenti WHERE squadra = ?", (nome_squadra,))
        return [row[0] for row in cur.fetchall()]

def get_squadra_da_user_id(user_id: int) -> str | None:
    print('db -> get_squadra_da_user_id')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT Squadra FROM Utenti WHERE id_telegram = ?", (user_id,))
        result = cur.fetchone()
        return result[0] if result else None

def get_partita_in_corso(squadra: str) -> dict | None:
    print('db -> get_partita_in_corso')
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row  # permette accesso per nome colonna
        cur = conn.cursor()

        # Recupera tutte le partite "in corso"
        cur.execute(""" SELECT Lista_Match, Status_Partita, Set_1 FROM Partite WHERE Status_Partita IN ('in gioco', 'bloccata') """)
        partite = cur.fetchall()

        for p in partite:
            print('get_partita_in_corso -> guardando a:',p)


            lista_match = p["Lista_Match"]
            print(f"Analizzo Lista_Match: '{lista_match}'")
            try:
                match = re.split(r"\s*-\s*", lista_match)
                if len(match) != 2:
                    continue  # formato errato
                squadra1, squadra2 = match
            except ValueError:
                continue  # formato non valido

            if squadra in (squadra1, squadra2):
                return {
                    "lista_match": lista_match,
                    "squadra1": squadra1,
                    "squadra2": squadra2,
                    "status": p["Status_Partita"],
                    "set1": p["Set_1"],
                }
        return None

def get_campo_libero_occupa_campo(match):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Trova il primo campo libero
        cur.execute("SELECT id_campo FROM Campi WHERE match IS NULL ORDER BY id_campo LIMIT 1;")
        risultato = cur.fetchone()

        if risultato:
            id_campo = risultato[0]
            # Occupa il campo aggiornando la colonna match
            cur.execute("UPDATE Campi SET match = ? WHERE id_campo = ?;", (match, id_campo))
            return id_campo
        else:
            # Nessun campo libero disponibile
            return None

def libera_campo(match):
    print('db -> libera_campo')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE Campi SET match = NULL WHERE match = ?;", (match,))
        conn.commit()


def registra_punteggio_partita(squadra1: str, squadra2: str, punti1: int, punti2: int):
    print('db -> registra_punteggio_partita')
    match = "-".join(sorted([squadra1, squadra2]))  # normalizza nome match
    set1 = f"[{punti1},{squadra1} - {punti2},{squadra2}]"

    #aggiornamento tabella Partite
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        #chek se punti gia inseriti
        cur.execute("""
            SELECT Set_1
            FROM Partite 
            WHERE Lista_Match = ? AND Status_Partita = 'in gioco'
        """, (match,))
        row = cur.fetchone()
        if row and all(v is not None and v != '' for v in row):
            return False  # Punteggio già esistente

        #qui recuperare durata e fare sottrazzione e segnare
        cur.execute("SELECT Durata FROM Partite WHERE Lista_Match = ?", (match,))
        row = cur.fetchone()

        inizio = float(row[0])
        fine = float(time.time())
        durata_sec = fine - inizio

        minuti = int(durata_sec // 60)
        secondi = int(durata_sec % 60)
        durata_str = f"{minuti}:{secondi}"


        cur.execute("""UPDATE Partite SET Set_1 = ?, Status_Partita = 'giocata', Durata = ? WHERE Lista_Match = ?""", (set1, durata_str, match,))
        conn.commit()
        print(f"partita {match,} durata {durata_str,match}")

        #aggiornamento tabella Squadre
        for squadra, punti_segnati in [(squadra1, punti1), (squadra2, punti2)]:
            print(f"registro punteggio per squadra: {squadra}")
            cur.execute(
                "SELECT Partite_Giocate, Vittorie, Punti FROM Squadre WHERE Nome_Squadra = ?",
                (squadra,)
            )
            partite_giocate, vittorie, punti = cur.fetchone()
            partite_giocate += 1
            punti += punti_segnati
            if punti_segnati == 50:
                vittorie += 1
            cur.execute(
                "UPDATE Squadre SET Partite_Giocate = ?, Vittorie = ?, Punti = ? WHERE Nome_Squadra = ?",
                (partite_giocate, vittorie, punti, squadra)
            )
            conn.commit()


    return True




def utente_disponibile(user_id: int) -> bool:
    print("db -> utente_disponibile")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Recupera la squadra a cui appartiene l'utente
        cur.execute("SELECT Squadra FROM Utenti WHERE id_telegram = ?", (user_id,))
        risultato = cur.fetchone()

        if not risultato or not risultato[0]:
            return False  # Utente non associato a nessuna squadra

        nome_squadra = risultato[0]

        # Verifica se la squadra ha lo status "disponibile"
        cur.execute("SELECT Status FROM Squadre WHERE Nome_Squadra = ?", (nome_squadra,))
        status = cur.fetchone()

        return status is not None and status[0] == "disponibile"

def verifica_stato_squadra(user_id: int) -> str:
    """
    Ritorna lo stato della squadra dell'utente:
    - 'disponibile'
    - 'indisponibile'
    - 'in gioco'
    - 'nessuna_squadra'
    - 'errore'
    """
    print("db -> verifica_stato_squadra")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()

            # Trova la squadra dell'utente
            cur.execute("SELECT Squadra FROM Utenti WHERE id_telegram = ?", (user_id,))
            risultato = cur.fetchone()

            if not risultato or not risultato[0]:
                return "nessuna_squadra"

            squadra = risultato[0]

            # Recupera lo stato della squadra
            cur.execute("SELECT Status FROM Squadre WHERE Nome_Squadra = ?", (squadra,))
            row = cur.fetchone()

            if not row:
                return "errore"

            return row[0]  # "disponibile", "attesa", "in gioco"

    except Exception as e:
        print("Errore in verifica_stato_squadra:", e)
        return "errore"

# funzioni per mettere in pausa disponibilità

def get_tutti_user_id():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id_telegram FROM Utenti")
        return [row[0] for row in cur.fetchall()]

def aggiorna_status_squadra_per_nome(nome_squadra: str, nuovo_status: str):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE Squadre SET Status = ? WHERE Nome_Squadra = ?", (nuovo_status, nome_squadra))
        conn.commit()








