"""Ajustes del proyecto.

Todo lo calibrable (palabras, tiempos, angulos, colores) vive aqui.
"""

# --- Camara ---
CAMERA_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
MIRROR = True            # vista espejo: te mueves como frente a un espejo
DETECT_WIDTH = 640       # ancho al que se reduce el frame para los modelos (0 = sin reducir)

# --- Tablero ---
# Cada fila puede tener distinta cantidad de recuadros: pokemon arriba,
# comandos en medio y ataques abajo.
WORD_ROWS = [
    ["TOGEKISS", "TYPHLOSION", "GARCHOMP"],
    ["YO TE ELIJO", "USA", "¡ESQUIVA!", "¡REGRESA!"],
    ["BRILLO LUNAR", "ESTALLIDO", "TERREMOTO", "TAJO AÉREO", "LLAMARADA",
     "GARRA DRAGÓN"],
]
WORDS = [w for row in WORD_ROWS for w in row]

# Tamano de cada recuadro dentro de su hueco de la grilla (1.0 = lo llena).
# Se encoge desde el centro, asi que la grilla no se mueve.
CELL_SCALE = 0.88

# --- Comandos ---
CMD_CHOOSE = "YO TE ELIJO"
CMD_USE = "USA"
CMD_DODGE = "¡ESQUIVA!"
CMD_RECALL = "¡REGRESA!"
COMMANDS = (CMD_CHOOSE, CMD_USE, CMD_DODGE, CMD_RECALL)

# --- Pokemon del equipo (3 pokebolas) ---
# `id` es el numero de la Pokedex: con el se bajan el sprite animado y el grito.
POKEMON = {
    "TOGEKISS":   {"id": 468, "moves": ("BRILLO LUNAR", "TAJO AÉREO")},
    "TYPHLOSION": {"id": 157, "moves": ("LLAMARADA", "ESTALLIDO")},
    "GARCHOMP":   {"id": 445, "moves": ("TERREMOTO", "GARRA DRAGÓN")},
}

# --- Ataques y su tipo ---
MOVES = {
    "BRILLO LUNAR":  "HADA",
    "TAJO AÉREO": "VOLADOR",
    "LLAMARADA":     "FUEGO",
    "ESTALLIDO":     "FUEGO",
    "TERREMOTO":     "TIERRA",
    "GARRA DRAGÓN": "DRAGÓN",
}

# Colores oficiales de los tipos, en BGR.
TYPE_COLORS = {
    "HADA":    (173, 133, 214),   # #D685AD
    "VOLADOR": (243, 143, 169),   # #A98FF3
    "FUEGO":   (48, 129, 238),    # #EE8130
    "TIERRA":  (101, 191, 226),   # #E2BF65
    "DRAGÓN": (252, 53, 111),    # #6F35FC
}

# Colores por rol en el tablero.
COLOR_POKEMON = (90, 210, 255)    # ambar
COLOR_COMMAND = (200, 220, 120)   # verde menta

# --- Mano que se rastrea ---
HAND_SIDE = "right"
STRICT_HAND_SIDE = True     # True: ignora la otra mano
HAND_MIN_DETECTION = 0.6
HAND_MIN_TRACKING = 0.5

# --- Seleccion por permanencia (dwell) ---
DWELL_SECONDS = 3.0
LOST_GRACE_SECONDS = 0.35   # tolera perder el dedo un instante sin reiniciar

# --- Gesto "brazo en 90 grados" para enviar la frase ---
ARM_SIDE = "right"
ARM_TARGET_ANGLE = 90.0
ARM_TOLERANCE = 20.0
ARM_HOLD_SECONDS = 0.8
# Al senalar los recuadros el codo ya queda cerca de 90 grados, asi que por
# defecto se exige la postura completa: brazo horizontal y antebrazo hacia
# arriba (como marcar biceps). Con la tecla [B] se relaja en vivo.
ARM_STRICT_POSE = True
ARM_UPPER_TOLERANCE = 35.0
POSE_EVERY_N_FRAMES = 2
POSE_MAX_AGE_SECONDS = 0.5

# --- Escena ---
STAGE_HEIGHT = 168          # banda del sprite y las pokebolas
BAR_HEIGHT = 118            # barra de la frase
HUD_HEIGHT = 70
SPRITE_SCALE = 2.1          # los sprites originales miden ~80 px
BALL_RADIUS = 27

# --- Audio ---
AUDIO_ENABLED = True
VOLUME = 0.75

# --- Salida ---
OUTPUT_FILE = "frases.txt"
MESSAGE_SECONDS = 2.6
