"""Jendela utama: preview dan kontrol di kiri, subtitle besar dan riwayat di kanan."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget)

from app import segmenter as seg
from app import theme
from app.camera import CameraWorker
from app.predictor import display_name
from app.tts import Speaker
from app.ui.widgets import ConfidenceMeter, StatusDot, VideoView

S = theme.SPACE
SUBTITLE_IDLE = "Menunggu isyarat"
HISTORY_EMPTY = "Kata yang dikenali akan muncul di sini."


def label(text, role=None, name=None):
    w = QLabel(text)
    if role:
        w.setProperty("role", role)
    if name:
        w.setObjectName(name)
    return w


def restyle(widget, prop, value):
    """Ubah property lalu minta Qt menerapkan ulang QSS untuk widget itu."""
    widget.setProperty(prop, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class MainWindow(QMainWindow):
    def __init__(self, predictor, videos=None):
        super().__init__()
        self.setWindowTitle("Penerjemah BISINDO")
        self.resize(1180, 720)
        self.setMinimumSize(980, 620)
        self.predictor = predictor
        self.words = []
        self._notes = {}

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(S * 4, S * 4, S * 4, S * 3)
        outer.setSpacing(S * 6)
        outer.addLayout(self._build_sidebar())
        outer.addLayout(self._build_main(), 1)

        self.speaker = Speaker(self)
        self.speaker.warning.connect(lambda msg: self._set_note("tts", msg))
        if predictor.is_mock:
            self._set_note("mock", "Mode simulasi: model belum dimuat, hasil acak")

        self.worker = CameraWorker(predictor, videos, self)
        self.worker.frame_ready.connect(self.video.set_image)
        self.worker.status.connect(self._on_status)
        self.worker.predicted.connect(self._on_prediction)
        self.worker.discarded.connect(lambda: self.status_text.setText("Gerakan terlalu singkat"))
        self.worker.cameras_found.connect(self._on_cameras)
        self.worker.error.connect(self.video.set_message)
        self._on_threshold(self.threshold.value())
        if videos:
            self.camera_box.setItemText(0, "File video (mode uji)")
        self.worker.start()

    # -- tata letak -----------------------------------------------------------
    def _build_sidebar(self):
        col = QVBoxLayout()
        col.setSpacing(S)

        self.video = VideoView()
        self.video.setFixedWidth(theme.SIDEBAR_WIDTH)
        col.addWidget(self.video)

        row = QHBoxLayout()
        row.setSpacing(S)
        self.status_dot = StatusDot()
        self.status_text = label("Menunggu tangan", "muted")
        row.addWidget(self.status_dot)
        row.addWidget(self.status_text, 1)
        col.addLayout(row)
        col.addSpacing(S * 3)

        col.addWidget(label("KAMERA", "section"))
        self.camera_box = QComboBox()
        self.camera_box.addItem("Mencari kamera…")
        self.camera_box.setEnabled(False)
        self.camera_box.activated.connect(self._on_camera_chosen)
        col.addWidget(self.camera_box)
        self.overlay_check = QCheckBox("Tampilkan titik tangan")
        self.overlay_check.setChecked(True)
        self.overlay_check.toggled.connect(self._on_overlay)
        col.addWidget(self.overlay_check)
        col.addSpacing(S * 3)

        col.addWidget(label("SUARA", "section"))
        self.tts_check = QCheckBox("Bacakan kata yang dikenali")
        self.tts_check.setChecked(True)
        self.tts_check.toggled.connect(self._on_tts)
        col.addWidget(self.tts_check)
        col.addSpacing(S * 3)

        row = QHBoxLayout()
        row.addWidget(label("AMBANG KEYAKINAN", "section"), 1)
        self.threshold_value = label("", "muted")
        row.addWidget(self.threshold_value)
        col.addLayout(row)
        self.threshold = QSlider(Qt.Horizontal)
        self.threshold.setRange(20, 95)
        self.threshold.setSingleStep(5)
        self.threshold.setValue(50)
        self.threshold.valueChanged.connect(self._on_threshold)
        col.addWidget(self.threshold)

        col.addStretch(1)
        self.notes = label("", "note")
        self.notes.setWordWrap(True)
        self.notes.setFixedWidth(theme.SIDEBAR_WIDTH)
        col.addWidget(self.notes)
        return col

    def _build_main(self):
        col = QVBoxLayout()
        col.setSpacing(S)

        col.addWidget(label("TERJEMAHAN", "section"))
        self.subtitle = label(SUBTITLE_IDLE, name="subtitle")
        self.subtitle.setProperty("unsure", True)
        self.subtitle.setWordWrap(True)
        self.subtitle.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.subtitle.setMinimumHeight(theme.SIZE_HERO * 3)
        col.addWidget(self.subtitle, 3)

        row = QHBoxLayout()
        row.setSpacing(S + 4)
        self.meter = ConfidenceMeter()
        self.meter_text = label("", "muted")
        row.addWidget(self.meter, 0, Qt.AlignVCenter)
        row.addWidget(self.meter_text, 1)
        col.addLayout(row)
        col.addSpacing(S * 3)

        col.addWidget(QFrame(objectName="rule"))
        col.addSpacing(S * 2)

        row = QHBoxLayout()
        row.addWidget(label("RIWAYAT", "section"), 1)
        clear = QPushButton("Hapus riwayat")
        clear.clicked.connect(self._clear_history)
        row.addWidget(clear)
        col.addLayout(row)

        self.history = label(HISTORY_EMPTY, name="history")
        self.history.setProperty("empty", True)
        self.history.setWordWrap(True)
        self.history.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.history.setTextInteractionFlags(Qt.TextSelectableByMouse)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.history)
        scroll.setMinimumHeight(theme.SIZE_HISTORY * 4)
        col.addWidget(scroll, 2)
        return col

    # -- sinyal dari worker ---------------------------------------------------
    def _on_status(self, state, elapsed):
        self.status_dot.set_on(state == seg.ACTIVE)
        if state == seg.ACTIVE:
            self.status_text.setText(f"Merekam gerakan  {elapsed:.1f} dtk".replace(".", ","))
        elif state == seg.WAIT_CLEAR:
            self.status_text.setText("Turunkan tangan untuk kata berikutnya")
        elif self.status_text.text().startswith(("Merekam", "Turunkan")):
            self.status_text.setText("Menunggu tangan")

    def _on_prediction(self, pred):
        percent = f"{pred.confidence:.0%}"
        if pred.sure:
            word = display_name(pred.label)
            self.subtitle.setText(word.capitalize())
            self.meter_text.setText(f"Keyakinan {percent}")
            self.words.append(word)
            self._render_history()
            self.speaker.say(word)
        else:
            self.subtitle.setText("tidak yakin")
            self.meter_text.setText(f"Keyakinan {percent}, tidak diucapkan")
        restyle(self.subtitle, "unsure", not pred.sure)
        self.meter.set_value(pred.confidence, pred.sure)
        self.status_text.setText("Menunggu tangan")

    def _on_cameras(self, cams):
        self.camera_box.clear()
        if not cams:
            self.camera_box.addItem("Tidak ada kamera")
            self.video.set_message("Kamera tidak ditemukan")
            return
        for i in cams:
            self.camera_box.addItem(f"Kamera {i + 1}", i)
        self.camera_box.setEnabled(len(cams) > 1)

    # -- kontrol --------------------------------------------------------------
    def _on_camera_chosen(self, row):
        index = self.camera_box.itemData(row)
        if index is not None:
            self.worker.set_camera(index)

    def _on_overlay(self, on):
        self.worker.overlay = on

    def _on_tts(self, on):
        self.speaker.enabled = on

    def _on_threshold(self, value):
        self.predictor.threshold = value / 100
        self.threshold_value.setText(f"{value}%")

    def _clear_history(self):
        self.words.clear()
        self._render_history()

    def _render_history(self):
        text = " ".join(self.words)
        self.history.setText(text[:1].upper() + text[1:] if text else HISTORY_EMPTY)
        restyle(self.history, "empty", not text)

    def _set_note(self, key, text):
        self._notes[key] = text
        self.notes.setText("\n".join(self._notes.values()))

    def closeEvent(self, event):
        self.worker.stop()
        self.speaker.stop()
        super().closeEvent(event)
