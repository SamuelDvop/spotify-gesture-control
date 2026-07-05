import threading


class VoiceFeedback:
    def __init__(self):
        self._engine = None
        self._enabled = True
        self._lock = threading.Lock()
        try:
            import win32com.client
            self._engine = win32com.client.Dispatch("SAPI.SpVoice")
            self._engine.Rate = 1
            self._engine.Volume = 80
        except Exception as e:
            print(f"[!] TTS no disponible: {e}")

    @property
    def enabled(self):
        return self._enabled

    def toggle(self):
        self._enabled = not self._enabled
        status = "activado" if self._enabled else "desactivado"
        print(f"[TTS] Feedback por voz {status}")
        if self._enabled and self._engine:
            threading.Thread(target=self._speak, args=(f"Voz {status}",), daemon=True).start()
        return self._enabled

    def speak(self, text):
        if not self._enabled or not self._engine:
            return
        threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    def _speak(self, text):
        with self._lock:
            try:
                self._engine.Speak(text, 1)
            except:
                pass
