"""Segmentasi satu gerakan = satu kata, berdasarkan ada/tidaknya tangan.

Mulai saat tangan terdeteksi, selesai saat tangan hilang ~0,5 detik atau setelah
maksimum 3 detik. Segmen dipotong sampai frame terakhir yang ada tangannya, sama
seperti trim_to_hands() saat ekstraksi data training.
"""
import numpy as np

import features as F

IDLE, ACTIVE, WAIT_CLEAR = "idle", "active", "wait_clear"


class Segmenter:
    def __init__(self, end_gap=0.5, max_len=3.0, min_len=0.5, start_frames=2):
        self.end_gap = end_gap
        self.max_len = max_len
        self.min_len = min_len
        self.start_frames = start_frames  # tangan harus muncul berturut-turut, bukan kedip 1 frame
        self.reset()

    def reset(self):
        self.state = IDLE
        self._buf = []
        self._pending = []
        self._start_t = self._last_hand_t = 0.0
        self._last_hand_n = 0

    def elapsed(self, t):
        return t - self._start_t if self.state == ACTIVE else 0.0

    def update(self, vec, has_hand, t):
        """Masukkan satu frame. Mengembalikan (event, segmen).

        event: None | "start" | "segment" | "discard". Segmen (N, BASE_DIM) hanya
        ada untuk event "segment".
        """
        if self.state == IDLE:
            if not has_hand:
                self._pending.clear()
                return None, None
            self._pending.append((vec, t))
            if len(self._pending) < self.start_frames:
                return None, None
            self._buf = [v for v, _ in self._pending]
            self._start_t = self._pending[0][1]
            self._pending = []
            self._last_hand_t, self._last_hand_n = t, len(self._buf)
            self.state = ACTIVE
            return "start", None

        if self.state == WAIT_CLEAR:
            if has_hand:
                self._last_hand_t = t
            elif t - self._last_hand_t >= self.end_gap:
                self.state = IDLE
            return None, None

        self._buf.append(vec)
        if has_hand:
            self._last_hand_t, self._last_hand_n = t, len(self._buf)
        hand_gone = t - self._last_hand_t >= self.end_gap
        too_long = t - self._start_t >= self.max_len
        if not (hand_gone or too_long):
            return None, None

        seg = np.stack(self._buf[:self._last_hand_n])
        duration = self._last_hand_t - self._start_t
        # Jika terpotong karena terlalu lama, tunggu tangan turun dulu sebelum segmen baru
        self.state = IDLE if hand_gone else WAIT_CLEAR
        self._buf = []
        if duration < self.min_len or len(seg) < F.MIN_SEG_FRAMES:
            return "discard", None
        return "segment", seg
