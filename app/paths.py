"""Lokasi file aset, baik saat dijalankan dari sumber maupun dari .exe PyInstaller."""
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def asset(*parts):
    return ROOT.joinpath("assets", *parts)
