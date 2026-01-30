from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext
from handlers.menu import mostra_menu_principale
from states import *
from utils.db import *
import sqlite3

#import per renderizzare immagine
import hashlib
import os
from PIL import Image, ImageDraw, ImageFont




# --- GESTIONE PERCORSI DINAMICI ---
# Calcola la cartella principale del progetto (Torneo_Bot-master)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Percorsi universali (funzionano su Windows e Mac)
DB_PATH = os.path.join(BASE_DIR, "Torneo_Molkky.db")
OUTPUT_CLASSIFICA_PATH = os.path.join(BASE_DIR, "Foto", "classifica")
FONT_PATH = os.path.join(BASE_DIR, "assets", "seguiemj.ttf") 

# --- COSTANTI GRAFICHE ---
EMOJI_POSIZIONE = ["🥇", "🥈", "🥉", "😎", "😜", "🤩", "😏", "🤫", "😣", "😑", "😶", "🥵", "🤬", "😬", "😧", "🥱", "🥶"]
FONT_SIZE = 34
PADDING = 30
LINE_SPACING = 20  
BORDER_COLOR = "#CCCCCC"
BG_COLOR = "white"
TEXT_COLOR = "black"


# Mostra i pulsanti info
async def mostra_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('info -> mostra_info')
    keyboard = [
        ["📜 Regolamento della gara"],
        ["📊 Classifica in tempo reale"],
        ["🔥 Partite in corso"],
        #["🍔 Menu cibo"],
        ["🛍 Merchandising"],
        #["🎮 Mini Giochi"],
        ["🤖 Spiegazione bot"],
        ["🔙 Torna indietro"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    if update.message:
        await update.message.reply_text("ℹ️ Scegli un'opzione informativa:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text("ℹ️ Scegli un'opzione informativa:", reply_markup=reply_markup)

    return INFO

async def invia_regolamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('info -> invia_regolamento')
    await update.message.reply_text(
        "📜 *Regolamento del Torneo*\n\n"
    "🕒 *Formula:* Massimo 7 partite per un tempo limite!\n"
    "Squadre composte da 2 giocatori.\n"
    "Durante il torneo, le squadre si sfidano continuamente.\n"
    "Dalle 11 alle 13 e dalle 14 alle 16 puoi sfidare.\n"
    "Chi vuole giocare segnala la disponibilità, chi vuole riposare può farlo 😎\n\n"
    "🎮 *Come funziona:*\n"
    "1. Quando ti senti pronto, clicca su *🎖 Voglio giocare* per partecipare\n"
    "2. Il bot forma le partite e assegna gli avversari 👥\n"
    "3. Le partite sono a set unico, non affronterai mai una squadra più volte\n"
    "4. A fine partita inserisci il punteggio tramite *📝 Registra punteggio*, basta che solo uno dei giocatori lo faccia e la partita si conclude!\n\n"
    "🏆 *Classifica:*\n"
    "Ogni vittoria in più ti avvicina al podio! \n"
    "Più giochi, più possibilità hai di vincere! (se sei bravo)\n\n"
    "📌 *Note:*\n"
    "- Puoi renderti disponibile per giocare tutte le volte che vuoi\n"
    "- La possibilità di iniziare una partita finisce allo scadere del tempo, si lascerà il tempo per concludere le partite già iniziate \n"
    "- In caso di parità vittorie: si contano i punti totali fatti\n\n"
    "Buon divertimento e che vinca la squadra più agguerrita! 🔥",
        parse_mode="Markdown"
    )
    await mostra_menu_principale(update, context)
    return MENU

#---------------------------CLASSIFICA----------------------------------#

async def invia_classifica(update: Update, context: CallbackContext):
    path_img = calcola_classifica(update.effective_user.id)
    with open(path_img, 'rb') as f:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f)

    # Cancella l'immagine dopo l'invio
    if os.path.exists(path_img):
        os.remove(path_img)
    await mostra_menu_principale(update, context)
    return MENU

# Calcolo classifica con evidenziazione squadra utente
def calcola_classifica(user_id: int) -> str:
    print('info -> calcola_classifica')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Prendi la squadra dell’utente (se è un giocante)
        cur.execute("SELECT Squadra FROM Utenti WHERE ID_Telegram = ? AND Giocante = 1", (user_id,))
        user_squadra_row = cur.fetchone()
        user_squadra = user_squadra_row[0] if user_squadra_row else None

        # Recupera classifica
        cur.execute("""
            SELECT Nome_Squadra, Partite_Giocate, Vittorie, Punti
            FROM Squadre
            ORDER BY Vittorie DESC, Punti DESC
        """)
        risultati = cur.fetchall()

    if not risultati:
        return "❌ Nessuna squadra registrata."

    return genera_classifica_con_pillow(risultati, user_squadra) # riga aggiunta per renderizzare

#---------------------RENDERIZZAZIONE IMMAGINE-------------------------#

def genera_classifica_con_pillow(dati, squadra_utente, output_folder=OUTPUT_CLASSIFICA_PATH):
    os.makedirs(output_folder, exist_ok=True)

    # Calcolo hash per caching
    raw = "".join([f"{n}-{g}-{v}-{p}" for n, g, v, p in dati]) + (squadra_utente or "")
    hash_id = hashlib.md5(raw.encode()).hexdigest()
    filepath = os.path.join(output_folder, f"classifica_{hash_id}.png")
    if os.path.exists(filepath):
        return filepath

    # Font
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except IOError:
        font = ImageFont.load_default()
        print("⚠️ Font non trovato, uso font di default.")

    # Preparazione righe (con intestazione)
    # Intestazione colonne
    header_font = ImageFont.truetype(FONT_PATH, FONT_SIZE + 4)
    header = ("      Squadra", "V/PG", "Punti")
    righe = [header] + [
        (
            f"{EMOJI_POSIZIONE[i] if i < len(EMOJI_POSIZIONE) else EMOJI_POSIZIONE[-1]} {nome}" + (
                " 👈" if nome == squadra_utente else ""),
            f"{vinte} / {giocate}",
            str(punti),
            nome == squadra_utente
        )
        for i, (nome, giocate, vinte, punti) in enumerate(dati)
    ]

    # Calcola colonne
    col_widths = [0, 0, 0]
    for r in righe:
        for idx, txt in enumerate(r[:-1]):  # esclude il flag boolean
            w = int(font.getbbox(txt)[2])
            col_widths[idx] = max(col_widths[idx], w)
    col_pads = [10, 20, 20]

    row_h = font.getbbox("Ay")[3] + LINE_SPACING
    img_w = sum(col_widths[i] + col_pads[i] for i in range(len(col_widths))) + 2 * PADDING
    img_h = int(row_h * len(righe) + PADDING * 2 + 20)

    img = Image.new("RGB", (img_w, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = PADDING

    # Header
    x = PADDING
    for idx, txt in enumerate(header):
        draw.text((x, y), txt, font=font, fill=TEXT_COLOR)
        x += col_widths[idx] + col_pads[idx]
    y += row_h

    # Righe
    for nome_display, vg, pt, evidenziata in righe[1:]:
        draw.line([PADDING, y, img_w - PADDING, y], fill=BORDER_COLOR, width=1)

        x = PADDING
        for idx, txt in enumerate((nome_display, vg, pt)):
            draw.text((x, y + LINE_SPACING // 2), txt, font=font, fill=TEXT_COLOR)
            x += col_widths[idx] + col_pads[idx]
        y += row_h

    # Bordo finale
    draw.line([PADDING, y, img_w - PADDING, y], fill=BORDER_COLOR, width=1)

    img.save(filepath)
    return filepath


#-------------------------MENU CIBO------------------------------------#
async def invia_menu_cibo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('info -> invia_menu_cibo')
    await update.message.reply_text(
        "🍔 *Menu Cibo:*\n\n"
        "- Cibo 7€\n"
        "- Birra 3€\n\n",
        parse_mode="Markdown"
    )
    await mostra_menu_principale(update, context)
    return MENU

async def invia_spiegazione_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('info -> invia_spiegazione_bot')
    chat_id = update.message.chat_id
    await context.bot.send_message(chat_id = chat_id, text =
        "🎉 *BenvenutƏ nel Bot del Torneo!* 🏆\n\n"
        "Con questo bot puoi gestire tutto il tuo torneo in modo semplice e veloce!\n"
        "Attraverso la *Registrazione* ti iscrivi, non importa se vuoi giocare o solo guardare: "
        "Dal menu principale puoi tenere monitorato tutto il torneo!\n"
        "Ecco cosa puoi fare:\n\n"
        "🎖 *Disponibilità*\n"
        "Segnala se sei disponibile per giocare la prossima partita ✅\n\n"
        "📝 *Registra Punteggio*\n"
        "Quando la tua squadra gioca, conferma l'avversario e inserisci il punteggio finale!\n\n"
        "📊 *Classifica*\n"
        "Guarda la classifica aggiornata in tempo reale con le vittorie e i punti delle squadre\n\n"
        "📸 *Foto*\n"
        "Carica una tua foto per rendere il torneo ancora più divertente!\nNon ti preoccupare, poi le condividiamo.\n\n"
        "🍔 *Info extra*\n"
        "Troverai anche il regolamento del torneo, il menu cibo e tante altre informazioni utili\n\n"
        "Fai festa e offri una birra 🍻 a chi vuoi!\n\n"
        "Bot sviluppato da Luca Midali e Giorgio Cortinovis per L'Emiliana Mölkky",
        parse_mode="Markdown"
    )
    await mostra_menu_principale(update, context)
    return MENU


async def invia_partite_in_corso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("info -> invia_partite_in_corso")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT Lista_Match FROM Partite WHERE Status_Partita = 'in gioco'")
            partite = [row[0] for row in cur.fetchall()]

        if not partite:
            await update.message.reply_text("🚫 Nessuna partita attualmente in corso.")
            await mostra_menu_principale(update, context)
            return MENU

        messaggio = "🎯 *Partite attualmente in corso:*\n\n"
        for p in partite:
            squadre = p.split("-")
            if len(squadre) == 2:
                messaggio += f"🔁 *{squadre[0].strip()}* vs *{squadre[1].strip()}*\n"
            else:
                messaggio += f"🔁 {p}\n"

        await update.message.reply_text(messaggio, parse_mode="MarkdownV2")
        await mostra_menu_principale(update, context)
        return MENU

    except Exception as e:
        print("[ERRORE] invia_partite_in_corso:", e)
        await update.message.reply_text("⚠️ Errore nel recuperare le partite in corso.")
        await mostra_menu_principale(update, context)
        return MENU

async def invia_merchandising(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('info -> invia_merchandising')

    # Invia un messaggio con foto e descrizione degli oggetti in vendita
    messaggio = (
        "🛍 Merchandising del Torneo\n\n"
        "Acquista il nostro merchandising esclusivo!\n\n"
        "- Spilla Tonda - 3€\n"
        "- Spilla Emiliana Molkky - 5€\n"
        "- Portachiavi - 2€\n"
        "- Magliette - 10€\n"
        "- Ventagli - 5€\n"
        "- Teli Mare - 10€\n\n"
        #"- Poster - 5€\n"
        "Acquista ora per supportare l'Emiliana Mölkky! 🎁"
    )

    # Carica l'immagine degli oggetti in vendita (assicurati che l'immagine sia nel percorso giusto)
    #photo_path = ' '  # Cambia con il percorso corretto dell'immagine

    # Invia il messaggio con l'immagine
    await update.message.reply_text(messaggio)
    #await update.message.reply_photo(photo=open(photo_path, 'rb'))

    # Torna al menu principale
    await mostra_menu_principale(update, context)
    return MENU

async def mostra_menu_minigiochi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('info -> mostra_menu_minigiochi')

    # Crea la tastiera per il menu dei mini giochi
    keyboard = [
        ["🎰 Roulette!"],  # Primo mini gioco
        ["🪿 Bonus & Malus"],  # Secondo mini gioco
        ["🎯 Allenamento Plus"],  # Terzo mini gioco
        ["🔙 Torna indietro"]  # Per tornare al menu precedente
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Mostra il messaggio con il nuovo menu
    if update.message:
        await update.message.reply_text("🎮 Seleziona un Mini Gioco per le regole!", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text("🎮 Seleziona un Mini Gioco per le regole!", reply_markup=reply_markup)

    return INFO

async def gestisci_scelta_minigioco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scelta = update.message.text
    if scelta == "🎰 Roulette!":
        await update.message.reply_text("Hai scelto la 🎰 Roulette!\n\n"
                                        "Sei stanco di scegliere? Lascia scegliere al caso!\n"
                                        "Gira la Roulette e tira ciò che ti viene ordinato!\n\n"
                                        "La 🎰 Roulette regale sogni, mettiti alla prova!\n")
        # Qui potresti avviare il codice del gioco 1
    elif scelta == "🪿 Bonus & Malus":
        await update.message.reply_text("Hai scelto 🪿 Bonus & Malus!\n\n"
                                        "Fai una partita normale di molkky ma che normale non è!\n"
                                        "Nel campo ci saranno aree delimitate da fili di colore diverso\n"
                                        "Attento ai colori dello spago, alcuni ti aiutano altri ti bullizzano\n"
                                        "Le regole sono le stesse del Molkky.")
        # Qui potresti avviare il codice del gioco 2
    elif scelta == "🎯 Allenamento Plus":
        await update.message.reply_text("Hai scelto 🎯 Allenamento Plus!\n\n"
                                        "Ogni ora il birillo da colpire cambia!\n"
                                        "Cambia anche la sua posizione\n"
                                        "Cambiano anche i suoi vicini\n"
                                        "Insomma, in questo mondo moderno e accelerato l'unica cosa su cui puoi fare affidamento sono le tue capacità di lanciare cilindri con precisione.\n\n"
                                        "Hai solo un tentativo ogni ora. Colpisci il birillo designato!\n"
                                        "Alla fine della giornata chi ha abbattuto più birilli vince!")
        # Qui potresti avviare il codice del gioco 3
    elif scelta == "🔙 Torna indietro":
        await mostra_info(update, context)
    else:
        await update.message.reply_text("❌ Scelta non valida. Torna al menu e scegli un gioco.")
        await mostra_menu_minigiochi(update, context)
    await mostra_menu_principale(update, context)
    return MENU

async def torna_al_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('info -> torna_al_menu')
    await mostra_menu_principale(update, context)
    return MENU

