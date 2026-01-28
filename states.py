#states.py --> ogni stato deve avere il suo numero univoco

# Stati principali della conversazione
REGISTRAZIONE, SQUADRA, MENU, INFO, DISPONIBILITA, PARTITA = range(6)

# Stati secondari (specifici di una feature)
CONFERMA_AVVERSARIO, INSERISCI_PUNTEGGIO = range(6,8)

#stati per inserire il punteggio
PARTITA_INSERISCI_PUNTEGGIO1, PARTITA_INSERISCI_PUNTEGGIO2 =  range(8,10)
