from typing import Dict
import asyncio

ISCRIZIONI = True
DISPONIBILITA_ATTIVA = True
EVENTO_CHIUSO = False

#Variabili globali

TASKS_IN_ATTESA: Dict[str, asyncio.Task] = {}

config_torneo = {
    12: {"num_gironi": 2, "numero_campi": 4},
    13: {"num_gironi": 2, "numero_campi": 4},
    14: {"num_gironi": 2, "numero_campi": 4},
    15: {"num_gironi": 2, "numero_campi": 4},

    16: {"num_gironi": 4, "numero_campi": 2},
    17: {"num_gironi": 4, "numero_campi": 2},
    18: {"num_gironi": 4, "numero_campi": 2},
    19: {"num_gironi": 4, "numero_campi": 2},
    20: {"num_gironi": 4, "numero_campi": 2},
    21: {"num_gironi": 4, "numero_campi": 2},
    22: {"num_gironi": 4, "numero_campi": 2},
    23: {"num_gironi": 4, "numero_campi": 2},
    24: {"num_gironi": 4, "numero_campi": 2},
}


# PERMESSI

ADMINS = {6501412424, 1707848811,938710069,965795013}
CAPI = {934069316}
GESTIONE = {}



# Leo 2001039871
# Mida 1707848811
# Gio 6501412424
# Marco 934069316
# Mariachiara 965795013
# Despi 938710069
# Lucia 2105796204
# Cosimo Calciano 162857812


