# Pokédex gestual

Das órdenes Pokémon apuntando recuadros con el dedo, frente a la cámara.

- La punta de tu **dedo índice derecho** es el cursor.
- Mantenlo **3 segundos** sobre un recuadro y esa palabra se suma a la frase,
  que se va escribiendo en la barra de abajo.
- Pon el **brazo en 90 grados** para **enviar la frase**. La frase no solo se
  guarda: **se ejecuta**.

```bash
python main.py
```

En Windows también puedes hacer doble clic en `jugar.bat`. La primera vez se
descargan solos los sprites y los gritos (unos 200 KB).

## Las 13 palabras

El tablero está agrupado por función:

| Fila | Recuadros |
|---|---|
| Pokémon | TOGEKISS · TYPHLOSION · GARCHOMP |
| Órdenes | YO TE ELIJO · USA · ¡ESQUIVA! · ¡REGRESA! |
| Ataques | BRILLO LUNAR · ESTALLIDO · TERREMOTO · TAJO AÉREO · LLAMARADA · GARRA DRAGÓN |

## Qué pasa al enviar una frase

| Frase | Efecto |
|---|---|
| `YO TE ELIJO TOGEKISS` | se abre su pokébola, suena su grito real y su sprite animado aparece abajo a la izquierda |
| `USA BRILLO LUNAR` | ataque con estallido, color y sonido del tipo del ataque |
| `¡ESQUIVA!` | el Pokémon se aparta de un salto |
| `¡REGRESA!` | vuelve a su pokébola y esta se cierra |
| `TOGEKISS YO TE ELIJO` | lo mismo que `YO TE ELIJO TOGEKISS`: el nombre vale antes o después de la orden |
| `YO TE ELIJO GARCHOMP USA TERREMOTO` | una frase puede encadenar órdenes: se ejecutan en secuencia |

El orden da igual: `YO TE ELIJO TOGEKISS` y `TOGEKISS YO TE ELIJO` hacen lo
mismo, y también valen `TOGEKISS ¡REGRESA!` o `LLAMARADA USA`.

Tres reglas del combate:

1. **Solo tienes 3 pokébolas** (una por Pokémon) y solo uno puede estar fuera.
   Si eliges otro, la pokébola anterior se cierra y se abre la nueva.
2. **Cada Pokémon solo conoce sus dos ataques.** Pedirle otro no hace nada:
   avisa con `TOGEKISS no aprende TERREMOTO`. Los ataques que sabe se ven en
   las etiquetas de tipo junto a su nombre.
3. **Hay que sacarlo antes de darle órdenes.** Nombrar a un Pokémon sin
   `YO TE ELIJO` (ni antes ni después) solo te recuerda que uses esa frase.

## Colores y sonidos por tipo

Cada ataque usa el color oficial de su tipo, tanto en el borde de su recuadro
como en el estallido, el cartel y el tinte de pantalla:

| Ataque | Tipo | Extra |
|---|---|---|
| BRILLO LUNAR | Hada | arpegio brillante |
| TAJO AÉREO | Volador | ráfaga de aire |
| LLAMARADA | Fuego | crepitar y estruendo |
| ESTALLIDO | Fuego | ídem |
| TERREMOTO | Tierra | retumbo **y la pantalla tiembla** |
| GARRA DRAGÓN | Dragón | rugido descendente |

Los **gritos son los reales** de cada Pokémon (`.ogg` de PokeAPI). Los demás
sonidos (pokébola, esquive, ataques, clic de palabra, error) se generan con
numpy al arrancar, así que no hay que descargar nada más. Todo se mezcla en un
solo stream: un grito y un ataque pueden sonar a la vez.

## Teclas

| Tecla | Qué hace |
|---|---|
| `BACKSPACE` | borra la última palabra |
| `C` | limpia la frase |
| `B` | alterna el gesto estricto del brazo |
| `M` | cambia el brazo que se lee (si detecta el equivocado) |
| `S` | silencio |
| `F` | pantalla completa |
| `Q` o `ESC` | salir |

## Opciones

```bash
python main.py --camera 1        # si tienes varias cámaras
python main.py --dwell 2         # 2 segundos por palabra en vez de 3
python main.py --fullscreen
python main.py --loose-arm       # basta el codo a 90, sin exigir brazo horizontal
python main.py --no-sound
python main.py --no-mirror
```

## El gesto para enviar

El brazo "en 90 grados" se mide como el ángulo del **codo**
(hombro-codo-muñeca), con ±20 grados de tolerancia, mantenido 0.8 segundos.

Como al señalar los recuadros el codo también queda cerca de 90 grados, por
defecto se exige la postura completa: **brazo horizontal y antebrazo hacia
arriba** (como marcar bíceps). Si te resulta incómodo, pulsa `B` o arranca con
`--loose-arm`. El HUD dice en todo momento qué ve el programa
(`codo 92 ok, sube el brazo (48)`), así que es fácil calibrar.

## Ajustes

Todo lo calibrable está en `config.py`: las palabras (`WORD_ROWS`), qué ataques
conoce cada Pokémon y su número de Pokédex (`POKEMON`), el tipo de cada ataque
(`MOVES`, `TYPE_COLORS`), los segundos de permanencia, los umbrales del brazo,
el tamaño del sprite y el volumen.

Para cambiar el equipo basta poner otro número de Pokédex en `POKEMON`: el
sprite animado y el grito se descargan solos. `ESTALLIDO` está clasificado como
Fuego para que encaje con Typhlosion; cámbialo en `MOVES` si prefieres otro tipo.

## Instalación

```bash
pip install -r requirements.txt
```

Probado en Windows 11 con Python 3.12, mediapipe 0.10.21, OpenCV 4.11,
Pillow 12 y soundfile 0.14. Si `soundfile` falta, el juego funciona igual y los
gritos se reemplazan por un efecto sintetizado.

## Prueba sin cámara

```bash
python selftest.py
```

Valida el tablero, el conteo de 3 segundos, el gesto del brazo y todo el motor
de combate (elegir, atacar, tipos, regresar, frases encadenadas), y deja tres
imágenes: `preview.png`, `preview_combate.png` y `preview_secuencia.png` (una
tira con la animación completa cuadro a cuadro).

## Archivos

| Archivo | Contenido |
|---|---|
| `main.py` | bucle principal, teclas, orquestación |
| `tracking.py` | MediaPipe Hands (punta del índice) y Pose (ángulo del codo) |
| `board.py` | rejilla de recuadros, permanencia de 3 s, frase |
| `game.py` | pokébolas, Pokémon activo, órdenes y animaciones |
| `effects.py` | estallidos, carteles y tintes de pantalla |
| `ui.py` | tablero, HUD, escena y barra de la frase |
| `sprites.py` | carga de los GIF animados |
| `audio.py` | mezclador, gritos y síntesis de efectos |
| `camera.py` | captura en un hilo aparte |
| `gfx.py` | mezclas con alpha, rectángulos redondeados |
| `text_render.py` | texto con acentos (PIL) con cache |
| `assets.py` | descarga de sprites y gritos |
| `config.py` | todos los parámetros |
| `selftest.py` | pruebas sin cámara |

## Cinco detalles que importan

1. **Corrección de aspecto**: los landmarks vienen normalizados 0-1 en cada
   eje, así que en 16:9 los ángulos salen deformados (un codo de 90 grados
   reales se mide como ~70). Se reescala la `x` por el aspecto antes de medir.
2. **Anti-repetición**: al confirmar una palabra el recuadro queda bloqueado
   hasta que el dedo sale, para que no se agregue varias veces seguidas.
3. **Tolerancia a pérdidas**: si MediaPipe pierde la mano un instante
   (`LOST_GRACE_SECONDS`), el conteo de 3 segundos no se reinicia.
4. **Cámara en un hilo**: leer un frame cuesta ~60 ms con poca luz. Leyéndolo
   en paralelo, el bucle va al ritmo del más lento (cámara o dibujado) en vez
   de a la suma de ambos.
5. **Mezclas en 8 bits**: los rellenos y los textos se componen con
   operaciones de OpenCV en `uint8` en vez de float con numpy. Eso bajó el
   dibujado de 56 ms a ~11 ms por frame.

## Notas

- **Luz**: MediaPipe necesita luz decente. A oscuras la cámara baja a ~17 FPS
  por la exposición y la detección falla.
- **Espejo**: la imagen se voltea para que te muevas como frente a un espejo.
  MediaPipe Hands asume justo esa imagen espejada, así que la etiqueta
  "derecha" corresponde a tu mano derecha real. Pose no hace esa suposición y
  el código lo compensa; si aun así lee el brazo equivocado, pulsa `M`.
- Si la cámara no abre, cierra Teams / Zoom / Chrome, que la retienen.
- Las frases enviadas se guardan en `frases.txt` con su hora.

## Créditos

Sprites animados y gritos: [PokeAPI/sprites](https://github.com/PokeAPI/sprites)
y [PokeAPI/cries](https://github.com/PokeAPI/cries). Pokémon es una marca de
Nintendo / Game Freak / The Pokémon Company; esto es un juguete personal, sin
ánimo comercial.
