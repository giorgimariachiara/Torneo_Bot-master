from telegram.ext import Application

# Importa i moduli dei vari handler (da creare o aggiornare)
from handlers.admin import *
from handlers.disponibilita import *
from handlers.info import *

from handlers.registra_partita import *
from handlers.registrazione import *
from states import *





# ---------------------------------------MAIN----------------------------------------------------------------#


if __name__ == '__main__':
    bot = Bot(token="7212644773:AAHDztFblrdlWgJ18MF02u77dyfG22JuhiY")

    app = Application.builder().token("7212644773:AAHDztFblrdlWgJ18MF02u77dyfG22JuhiY").build()

    # --- COMANDI ADMIN ---
    app.add_handler(CommandHandler("Utenti", lista_utenti_command))
    app.add_handler(CommandHandler("Cancella_utente", cancella_utente_command))
    app.add_handler(CommandHandler("Cancella_squadra", cancella_squadra_command))
    app.add_handler(CommandHandler("Pausa", pausa_command))
    app.add_handler(CommandHandler("Riprendi", riprendi_command))
    app.add_handler(CommandHandler("Chiusura_Evento", chiusura_evento_command))
    app.add_handler(CommandHandler("Fine_Torneo", fine_torneo_command))
    app.add_handler(CommandHandler("Inizio", inizio_torneo))
    app.add_handler(aggiunta_squadra_handler)
    app.add_handler(admin_modifica_punteggio)
    app.add_handler(broadcast_handler)


    # --- CONVERSATION HANDLER PRINCIPALE ---
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            MessageHandler(filtro_primo_msg, start_command)
            # MessageHandler(filters.TEXT & ~filters.COMMAND, start_command)
        ],

        states={

            # Stato 1: REGISTRAZIONE iniziale (giocante/osservatore)
            REGISTRAZIONE: [
                MessageHandler(filters.TEXT & filters.Regex("^(🎯 Gioco|👀 Osservo)$"), scelta_tipo_utente)
            ],

            # Stato 2: scelta della squadra
            SQUADRA: [
                CallbackQueryHandler(scelta_squadra, pattern="^squadra_")
            ],

            # Stato 5: MENU PRINCIPALE
            MENU: [
                MessageHandler(filters.TEXT & filters.Regex("^ℹ️ Info$"), mostra_info),
                MessageHandler(filters.TEXT & filters.Regex("^🎖 Voglio giocare$"), gestione_disponibilita),
                MessageHandler(filters.TEXT & filters.Regex("^📝 Registra punteggio$"), gestione_partite),
                MessageHandler(filters.TEXT & filters.Regex("^📸 Foto$"), richiedi_foto),
                MessageHandler(filters.PHOTO, ricevi_foto),
                MessageHandler(filters.ALL, mostra_menu_principale)
            ],

            # Stato 2: RICHIESTA INFORMAZIONI
            INFO: [

                # Handler futuri per classifica, info torneo ecc.
                MessageHandler(filters.TEXT & filters.Regex("^📜 Regolamento della gara$"), invia_regolamento),
                MessageHandler(filters.TEXT & filters.Regex("^📊 Classifica in tempo reale$"), invia_classifica),
                MessageHandler(filters.TEXT & filters.Regex("^🔥 Partite in corso$"), invia_partite_in_corso),
                #MessageHandler(filters.TEXT & filters.Regex("^🎮 Mini Giochi$"), mostra_menu_minigiochi),
                #MessageHandler(filters.TEXT & filters.Regex("^🎰 Roulette!$"), gestisci_scelta_minigioco),
                #MessageHandler(filters.TEXT & filters.Regex("^🪿 Bonus & Malus$"), gestisci_scelta_minigioco),
                #MessageHandler(filters.TEXT & filters.Regex("^🎯 Allenamento Plus$"), gestisci_scelta_minigioco),
                #MessageHandler(filters.TEXT & filters.Regex("^🍔 Menu cibo$"), invia_menu_cibo),
                MessageHandler(filters.TEXT & filters.Regex("^🛍 Merchandising$"), invia_merchandising),
                MessageHandler(filters.TEXT & filters.Regex("^🤖 Spiegazione bot$"), invia_spiegazione_bot),
                MessageHandler(filters.TEXT & filters.Regex("^🔙 Torna indietro$"), torna_al_menu),
                MessageHandler(filters.ALL, mostra_info)
            ],

            # Stato 3: STATO SQUADRA (disponibile, indisponibile) -> tasto voglio giocare
            DISPONIBILITA: [
                CallbackQueryHandler(callback_disponibilita, pattern="^(disponibile|indisponibile)$")
            ],

            # Stato 4: REGISTRAZIONE PARTITA (punteggio, verifica) -> aggiungi punteggio partita
            PARTITA: [
                MessageHandler(filters.TEXT & filters.Regex("^[✅❌]"), conferma_avversario),
            ],

            PARTITA_INSERISCI_PUNTEGGIO1: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, inserisci_punteggio_squadra1)
            ],

            PARTITA_INSERISCI_PUNTEGGIO2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, inserisci_punteggio_squadra2)
            ],
        },

        fallbacks=[],
        allow_reentry=True,
    )
    app.add_handler(CallbackQueryHandler(conferma_prontezza, pattern=r"^(pronti|rifiuto)_.*_\d+$"))
    app.add_handler(conv_handler)


    # --- Avvio del bot ---
    print("🤖 Bot avviato e in ascolto...")
    app.run_polling()
