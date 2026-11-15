"""Text-to-speech di thread sendiri supaya UI tidak pernah menunggu suara selesai."""
import queue
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, Signal

ID_HINTS = ("id-id", "id_id", "indonesia", "andika", "gadis", "damayanti")


def _is_indonesian(voice):
    text = " ".join([str(voice.id), str(voice.name)] + [str(l) for l in (voice.languages or [])])
    return any(h in text.lower() for h in ID_HINTS)


class Speaker(QObject):
    warning = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self._q = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def say(self, text):
        if self.enabled:
            self._q.put(text)

    def stop(self):
        self._q.put(None)

    def _run(self):
        try:
            speak = self._init_macos() if sys.platform == "darwin" else self._init_pyttsx3()
        except Exception as e:  # tanpa TTS aplikasi tetap jalan dengan subtitle saja
            self.warning.emit(f"Suara tidak tersedia ({type(e).__name__})")
            speak = None

        while True:
            text = self._q.get()
            if text is None:
                break
            if speak is None or not self.enabled:
                continue
            try:
                speak(text)
            except Exception as e:
                self.warning.emit(f"Suara gagal diputar ({type(e).__name__})")

    def _warn_no_indonesian(self):
        self.warning.emit("Suara bahasa Indonesia tidak ditemukan, memakai suara bawaan")

    def _init_pyttsx3(self):
        """Windows (SAPI5). Engine dibuat di thread ini dan dipakai ulang."""
        try:  # SAPI5 butuh COM diinisialisasi di thread ini
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass
        import pyttsx3
        engine = pyttsx3.init()
        voice = next((v for v in engine.getProperty("voices") if _is_indonesian(v)), None)
        if voice is not None:
            engine.setProperty("voice", voice.id)
        else:
            self._warn_no_indonesian()
        engine.setProperty("rate", 160)

        def speak(text):
            engine.say(text)
            engine.runAndWait()
        return speak

    def _init_macos(self):
        """Hanya untuk pengembangan di Mac: driver macOS pyttsx3 tidak bisa jalan di luar main thread."""
        voices = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
        voice = next((l.split("  ")[0].strip() for l in voices.splitlines() if "id_ID" in l), None)
        if voice is None:
            self._warn_no_indonesian()
        args = ["say"] + (["-v", voice] if voice else [])
        return lambda text: subprocess.run(args + [text], check=True)
