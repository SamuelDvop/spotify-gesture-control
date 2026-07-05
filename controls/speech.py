import subprocess
import threading
import queue
import time
import sys


PS_SCRIPT = r'''
Add-Type -AssemblyName System.Speech
$rec = New-Object System.Speech.Recognition.SpeechRecognizer
$gram = New-Object System.Speech.Recognition.GrammarBuilder
$choices = New-Object System.Speech.Recognition.Choices
$choices.Add(@("play", "reproducir", "tocar"))
$choices.Add(@("pause", "pausa", "parar", "stop"))
$choices.Add(@("like", "favorito", "me gusta", "favorite"))
$choices.Add(@("next", "siguiente", "proxima", "siguiente cancion"))
$choices.Add(@("previous", "anterior", "volver", "cancion anterior"))
$choices.Add(@("subir volumen", "volumen arriba", "mas alto"))
$choices.Add(@("bajar volumen", "volumen abajo", "mas bajo"))
$gram.Append($choices)
$g = New-Object System.Speech.Recognition.Grammar($gram)
$rec.LoadGrammar($g)
$rec.SpeechRecognized.Add({
    $result = $_.Result
    $result.Text | Write-Host
})
while($true) {
    Start-Sleep -Milliseconds 100
}
'''


class SpeechCommands:
    def __init__(self, on_command):
        self._on_command = on_command
        self._process = None
        self._running = False
        self._thread = None
        self._enabled = False
        self._error = None

    @property
    def enabled(self):
        return self._enabled

    @property
    def available(self):
        return self._error is None

    def toggle(self):
        self._enabled = not self._enabled
        status = "activado" if self._enabled else "desactivado"
        print(f"[Comandos] Voz {status}")
        if self._enabled and not self._running:
            self.start()
        return self._enabled

    def start(self):
        if self._running:
            return
        self._running = True
        self._enabled = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._enabled = False
        self._running = False
        if self._process:
            self._process.terminate()
            self._process = None

    def _run(self):
        try:
            self._process = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", PS_SCRIPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            print("[Comandos] Escuchando... (decí play, pausa, like, siguiente, anterior, subir/bajar volumen)")

            for line in iter(self._process.stdout.readline, ""):
                if not self._running:
                    break
                cmd = line.strip().lower()
                if cmd:
                    self._on_command(cmd)

        except FileNotFoundError:
            self._error = "PowerShell no encontrado"
            print(f"[!] {self._error}")
        except Exception as e:
            self._error = str(e)
            print(f"[!] Comandos de voz no disponibles: {e}")
        finally:
            self._running = False
