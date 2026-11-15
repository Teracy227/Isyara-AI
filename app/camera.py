"""Thread kamera: ambil frame, deteksi landmark, segmentasi, dan klasifikasi.

Semua pekerjaan berat ada di thread ini; UI hanya menerima sinyal.
"""
import sys
import time

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

import features as F
from app import segmenter as seg
from app.theme import ACCENT_BGR

PREVIEW_WIDTH = 640
POSE_LINES = [(1, 2), (1, 3), (3, 5), (2, 4), (4, 6)]  # indeks ke features.POSE_IDX


def open_camera(index):
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    return cv2.VideoCapture(index, backend)


def list_cameras(max_index=4):
    found = []
    for i in range(max_index):
        cap = open_camera(i)
        if cap.isOpened() and cap.read()[0]:
            found.append(i)
        cap.release()
    return found


class CameraWorker(QThread):
    frame_ready = Signal(QImage)
    status = Signal(str, float)      # state segmenter, detik berjalan
    predicted = Signal(object)       # predictor.Prediction
    discarded = Signal()             # gerakan terlalu singkat
    cameras_found = Signal(list)
    error = Signal(str)

    def __init__(self, predictor, videos=None, parent=None):
        super().__init__(parent)
        self.predictor = predictor
        self.videos = videos or []   # mode uji: putar file video sebagai pengganti kamera
        self.overlay = True
        self._index = 0
        self._want_index = 0
        self._running = True

    def set_camera(self, index):
        self._want_index = index

    def stop(self):
        self._running = False
        self.wait(3000)

    # -- sumber frame ---------------------------------------------------------
    def _frames_camera(self):
        cams = list_cameras()
        self.cameras_found.emit(cams)
        if cams and self._want_index not in cams:
            self._want_index = cams[0]
        cap = None
        while self._running:
            if cap is None or self._index != self._want_index:
                if cap is not None:
                    cap.release()
                self._index = self._want_index
                cap = open_camera(self._index)
                yield None, 0.0  # sumber berganti: reset segmenter
            ok, frame = cap.read() if cap.isOpened() else (False, None)
            if not ok:
                self.error.emit(f"Kamera {self._index} tidak dapat dibuka")
                cap.release()
                cap = None
                time.sleep(1.0)
                continue
            yield frame, time.monotonic()
        if cap is not None:
            cap.release()

    def _frames_video(self):
        t = 0.0
        while self._running:
            for path in self.videos:
                cap = cv2.VideoCapture(str(path))
                dt = 1.0 / (cap.get(cv2.CAP_PROP_FPS) or 30.0)
                while self._running:
                    t0 = time.monotonic()
                    ok, frame = cap.read()
                    if not ok:
                        break
                    t += dt
                    yield frame, t
                    time.sleep(max(0.0, dt - (time.monotonic() - t0)))
                cap.release()
                t += 1.0  # jeda antar video

    # -- loop utama -----------------------------------------------------------
    def run(self):
        extractor = F.LandmarkExtractor()
        segmenter = seg.Segmenter()
        try:
            for frame, t in (self._frames_video() if self.videos else self._frames_camera()):
                if frame is None:
                    segmenter.reset()
                    continue
                vec, has_hand = extractor.process(frame)
                event, segment = segmenter.update(vec, has_hand, t)
                if event == "segment":
                    self.predicted.emit(self.predictor.predict(segment))
                elif event == "discard":
                    self.discarded.emit()
                self.status.emit(segmenter.state, segmenter.elapsed(t))
                self.frame_ready.emit(self._preview(frame, extractor))
        finally:
            extractor.close()

    def _preview(self, frame, extractor):
        h, w = frame.shape[:2]
        frame = cv2.resize(frame, (PREVIEW_WIDTH, int(h * PREVIEW_WIDTH / w)))
        if self.overlay:
            self._draw_landmarks(frame, extractor)
        frame = cv2.flip(frame, 1)  # cermin hanya untuk tampilan
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()

    @staticmethod
    def _draw_landmarks(frame, extractor):
        import mediapipe as mp
        h, w = frame.shape[:2]
        px = lambda p: (int(p.x * w), int(p.y * h))
        hands = extractor.last_hands
        if hands is not None and hands.multi_hand_landmarks:
            for lms in hands.multi_hand_landmarks:
                pts = [px(p) for p in lms.landmark]
                for a, b in mp.solutions.hands.HAND_CONNECTIONS:
                    cv2.line(frame, pts[a], pts[b], ACCENT_BGR, 2, cv2.LINE_AA)
                for p in pts:
                    cv2.circle(frame, p, 3, (255, 255, 255), -1, cv2.LINE_AA)
        pose = extractor.last_pose
        if pose is not None and pose.pose_landmarks:
            pts = [px(pose.pose_landmarks.landmark[i]) for i in F.POSE_IDX]
            for a, b in POSE_LINES:
                cv2.line(frame, pts[a], pts[b], (255, 255, 255), 1, cv2.LINE_AA)
