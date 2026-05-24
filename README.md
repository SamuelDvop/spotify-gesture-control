# Control por Gestos - Spotify

Controla Spotify con la mano usando la camara web y MediaPipe.

## Gestos

| Gesto | Accion |
|-------|--------|
| Mano abierta | Reproducir / Reanudar |
| Punio | Pausa |
| Indice arriba | Subir volumen (sistema + Spotify) |
| Indice abajo | Bajar volumen (sistema + Spotify) |
| Deslizar derecha (x2) | Siguiente cancion |
| Deslizar izquierda (x2) | Cancion anterior |

## Requisitos

- Python 3.10+
- Camara web
- Spotify instalado (Windows)

## Instalacion

```bash
git clone https://github.com/SamuelDvop/spotify-gesture-control
cd spotify-gesture-control
pip install -r requirements.txt
```

## Uso

```bash
python gesture_control.py
```

La primera deteccion registra el gesto inicial sin accion. Cambia a otro gesto para comenzar a controlar.
