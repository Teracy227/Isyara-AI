"""Widget kecil yang digambar sendiri. Warna dan ukuran diambil dari app.theme."""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from app import theme


class VideoView(QWidget):
    """Preview kamera, menjaga rasio gambar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self._message = "Menyalakan kamera…"
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(theme.SIDEBAR_WIDTH, theme.SIDEBAR_WIDTH * 3 // 4)

    def set_image(self, image):
        self._image = image
        self.update()

    def set_message(self, text):
        self._image = None
        self._message = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.SURFACE))
        if self._image is None:
            p.setPen(QColor(theme.TEXT_MUTED))
            p.drawText(self.rect(), Qt.AlignCenter, self._message)
            return
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        scaled = self._image.size().scaled(self.size(), Qt.KeepAspectRatio)
        x = (self.width() - scaled.width()) / 2
        y = (self.height() - scaled.height()) / 2
        p.drawImage(QRectF(x, y, scaled.width(), scaled.height()), self._image)


class ConfidenceMeter(QWidget):
    """Garis tipis: indikator keyakinan yang sengaja tidak mencolok."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._active = False
        self.setFixedSize(120, 12)

    def set_value(self, value, active):
        self._value = max(0.0, min(1.0, value))
        self._active = active
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        y = self.height() // 2 - 1
        p.fillRect(0, y, self.width(), 2, QColor(theme.BORDER))
        fill = QColor(theme.ACCENT if self._active else theme.TEXT_MUTED)
        p.fillRect(0, y, int(self.width() * self._value), 2, fill)


class StatusDot(QWidget):
    """Titik kecil di samping teks status; aksen saat sedang merekam gerakan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on = False
        self.setFixedSize(10, 10)

    def set_on(self, on):
        if on != self._on:
            self._on = on
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.ACCENT if self._on else theme.BORDER))
        p.drawEllipse(1, 1, 8, 8)
