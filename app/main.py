"""Titik masuk aplikasi.  Jalankan dari root repo:  python -m app.main

Opsi pengembangan:
  --mock                 pakai MockPredictor walau model.onnx ada
  --video a.mov b.mov    putar file video sebagai pengganti kamera
  --screenshot out.png   simpan tangkapan jendela lalu keluar (dengan --quit-after)
"""
import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # dijalankan sebagai skrip / dari PyInstaller
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app import theme
from app.predictor import load_predictor
from app.ui.main_window import MainWindow


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--video", nargs="*", default=[])
    ap.add_argument("--screenshot")
    ap.add_argument("--quit-after", type=float, default=0)
    args = ap.parse_args()

    app = QApplication(sys.argv[:1])
    theme.apply(app)
    window = MainWindow(load_predictor(args.mock), args.video)
    window.show()

    if args.quit_after:
        def finish():
            if args.screenshot:
                window.grab().save(args.screenshot)
            window.close()
        QTimer.singleShot(int(args.quit_after * 1000), finish)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
