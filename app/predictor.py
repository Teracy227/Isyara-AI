"""Klasifikasi satu segmen gerakan menjadi satu kata.

MockPredictor dipakai saat model.onnx belum ada (atau dengan --mock).
"""
import json
import random
from dataclasses import dataclass

import numpy as np

import features as F
from app.paths import asset

# Label dataset -> teks yang ditampilkan dan diucapkan
DISPLAY_NAMES = {"terimakasih": "terima kasih"}


def display_name(label):
    return DISPLAY_NAMES.get(label, label)


@dataclass
class Prediction:
    label: str        # kata terbaik menurut model
    confidence: float  # 0..1, yang ditampilkan ke pengguna
    sure: bool         # False -> tampilkan "tidak yakin", jangan diucapkan
    reason: str = ""   # alasan tidak yakin (untuk log)


class MockPredictor:
    is_mock = True

    def __init__(self, labels=None):
        self.labels = labels or ["halo", "terimakasih"]
        self.threshold = 0.5
        self._rng = random.Random(0)

    def predict(self, raw_segment):
        conf = self._rng.uniform(0.3, 0.99)
        return Prediction(self._rng.choice(self.labels), conf, conf >= self.threshold)


class OnnxPredictor:
    is_mock = False

    def __init__(self, model_path, labels_path, prototypes_path=None):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.labels = json.loads(open(labels_path, encoding="utf-8").read())
        self.threshold = 0.5
        self.proto = None
        if prototypes_path and prototypes_path.exists():
            p = np.load(prototypes_path)
            self.proto = dict(pos=p["pos"].astype(np.float32), y=p["y"],
                              d_ref=float(p["d_ref"]), motion_min=float(p["motion_min"]))

    def _probs(self, norm_seq):
        x = F.to_model_input(norm_seq)[None]
        return self.sess.run(None, {"features": x})[0][0]

    def predict(self, raw_segment):
        norm = F.normalize_sequence(raw_segment)

        # Stabilitas: prediksi harus sama walau batas segmen digeser sedikit
        k = max(1, len(norm) // 10)
        variants = [norm] + ([norm[k:], norm[:-k]] if len(norm) - k >= F.MIN_SEG_FRAMES else [])
        probs = np.stack([self._probs(v) for v in variants])
        cls = int(probs[0].argmax())
        stable = bool((probs.argmax(1) == cls).all())
        confidence = float(probs[:, cls].min())

        # Model 2 kelas selalu "yakin", jadi keyakinan dikalikan kemiripan dengan
        # contoh training terdekat, dan gerakan yang nyaris diam ditolak.
        moving = True
        if self.proto is not None:
            pos = F.resample(norm)
            ref = self.proto["pos"][self.proto["y"] == cls]
            d = float(np.sqrt(((ref - pos) ** 2).mean((1, 2))).min())
            confidence *= float(np.exp(-np.log(2) * (d / self.proto["d_ref"]) ** 2))
            moving = F.hand_motion(pos) >= self.proto["motion_min"]

        reason = ""
        if not stable:
            reason = "prediksi tidak stabil"
        elif not moving:
            reason = "gerakan terlalu sedikit"
        elif confidence < self.threshold:
            reason = "keyakinan di bawah ambang"
        return Prediction(self.labels[cls], confidence, not reason, reason)


def load_predictor(force_mock=False):
    model = asset("model.onnx")
    if force_mock or not model.exists():
        return MockPredictor()
    return OnnxPredictor(model, asset("labels.json"), asset("prototypes.npz"))
