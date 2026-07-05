# Control por Gestos — Spotify

Controla Spotify con la mano usando la cámara web y MediaPipe, o con comandos de voz.

## Gestos

| Gesto | Acción |
|-------|--------|
| ✋ Mano abierta | Play (si está en pausa) |
| ✊ Puño | Pausa (si está reproduciendo) |
| ☝️ Índice arriba | Subir volumen |
| ☝️ Índice abajo | Bajar volumen |
| ✌️ Paz (índice + medio) | Like / Unlike |
| →→ Deslizar derecha (x2) | Siguiente canción |
| ←← Deslizar izquierda (x2) | Canción anterior |

## Comandos de Voz

Presioná **`S`** para activar. Decí:

| Comando | Acción |
|---------|--------|
| "Play" / "reproducir" | Play/Pause |
| "Pausa" / "parar" | Play/Pause |
| "Like" / "favorito" | Like / Unlike |
| "Siguiente" / "next" | Siguiente canción |
| "Anterior" / "previous" | Canción anterior |
| "Subir volumen" / "más alto" | Subir volumen |
| "Bajar volumen" / "más bajo" | Bajar volumen |

## Funcionalidades

- **Visualización de canción actual**: nombre, artista, barra de progreso, ❤️ like/unlike
- **Carátula del álbum**: se muestra en pantalla cuando hay reproducción activa
- **Like/Unlike inteligente**: usa la API de Spotify para saber el estado real
- **Play/Pause inteligente**: con API, solo pausa si está sonando; solo reproduce si está en pausa
- **Feedback por voz (TTS)**: presioná **`V`** para que lea las acciones en voz alta
- **Comandos por voz**: presioná **`S`** para activar reconocimiento de voz
- **Doble volumen**: controla volumen maestro + volumen de Spotify.exe
- **Interfaz limpia**: solo lo esencial, indicadores de voz y TTS en la barra superior

## Requisitos

- Python 3.10+
- Cámara web
- Spotify instalado (Windows)
- Micrófono (para comandos de voz)

## Instalación

```bash
git clone <repo>
cd spotify_gesture
pip install -r requirements.txt
```

## Spotify API (para Like, info de canción y play/pausa inteligente)

1. Andá a https://developer.spotify.com/dashboard y creá una app
2. Copiá `.env.example` como `.env` y completá:

```env
SPOTIFY_CLIENT_ID=tu_client_id
SPOTIFY_CLIENT_SECRET=tu_client_secret
```

3. En la app de Spotify agregá `http://localhost:8888/callback` como Redirect URI
4. La primera vez se abrirá el navegador para autenticar

> Si no configurás la API, todo funciona igual pero sin like, info de canción ni play/pausa inteligente.

## Uso

```bash
python main.py
```

### Teclas

| Tecla | Función |
|-------|---------|
| `ESC` | Salir |
| `V` | Activar/desactivar feedback por voz |
| `S` | Activar/desactivar comandos de voz |

La primera detección registra el gesto inicial sin acción. Cambiá a otro gesto para comenzar a controlar.

## Estructura del proyecto

```
spotify_gesture/
├── main.py                  # Punto de entrada (loop principal)
├── config.py                # Constantes y configuración
├── vision/
│   ├── camera.py            # Captura de cámara
│   └── gesture.py           # Reconocimiento de gestos
├── controls/
│   ├── spotify_keys.py      # Control por teclas multimedia + volumen
│   ├── spotify_api.py       # API de Spotify (info, like, carátula)
│   ├── voice.py             # Feedback por voz (TTS)
│   └── speech.py            # Comandos de voz (System.Speech)
├── ui/
│   └── overlay.py           # Interfaz visual (paneles, barras, textos)
├── hand_landmarker.task     # Modelo MediaPipe
├── requirements.txt
├── .env.example
└── .gitignore
```
