"""Fitur landmark bersama untuk ekstraksi, training (Colab), dan aplikasi.

Alur per frame:  extractor.process(frame_bgr) -> vektor mentah (BASE_DIM,)
Alur per segmen: to_model_input(seq_mentah)    -> (T, FEAT_DIM) siap masuk model

Modul ini tidak meng-import mediapipe/cv2 di level atas supaya notebook Colab
cukup butuh numpy (augmentasi + resample memakai fungsi yang sama).
"""
import numpy as np

T = 32
MIN_SEG_FRAMES = 6  # segmen lebih pendek dari ini dianggap noise

# MediaPipe Pose: hidung, bahu kiri/kanan, siku kiri/kanan, pergelangan kiri/kanan
POSE_IDX = [0, 11, 12, 13, 14, 15, 16]
N_HAND = 21

# Tata letak vektor dasar per frame
HAND_DIM = N_HAND * 3                 # 63
POSE_DIM = len(POSE_IDX) * 3          # 21
L_SL = slice(0, HAND_DIM)             # tangan kiri
R_SL = slice(HAND_DIM, 2 * HAND_DIM)  # tangan kanan
P_SL = slice(2 * HAND_DIM, 2 * HAND_DIM + POSE_DIM)
FLAG_SL = slice(2 * HAND_DIM + POSE_DIM, 2 * HAND_DIM + POSE_DIM + 2)  # [ada_kiri, ada_kanan]
BASE_DIM = 2 * HAND_DIM + POSE_DIM + 2  # 149
FEAT_DIM = BASE_DIM * 2                 # + velocity = 298

# Kolom koordinat (tanpa flag) dan kolom x / y, dipakai augmentasi
COORD_DIM = 2 * HAND_DIM + POSE_DIM
X_COLS = np.arange(0, COORD_DIM, 3)
Y_COLS = np.arange(1, COORD_DIM, 3)

# Parameter MediaPipe, harus identik antara training dan aplikasi
HANDS_KW = dict(max_num_hands=2, model_complexity=1,
                min_detection_confidence=0.5, min_tracking_confidence=0.5)
POSE_KW = dict(model_complexity=1, min_detection_confidence=0.5,
               min_tracking_confidence=0.5)
PROC_WIDTH = 960  # frame diperkecil ke lebar ini sebelum deteksi


class LandmarkExtractor:
    """Bungkus MediaPipe Hands + Pose. Buat instance baru per video / per sesi kamera."""

    def __init__(self):
        import mediapipe as mp
        self._mp = mp
        self.hands = mp.solutions.hands.Hands(static_image_mode=False, **HANDS_KW)
        self.pose = mp.solutions.pose.Pose(static_image_mode=False, **POSE_KW)
        self.last_hands = None
        self.last_pose = None

    def close(self):
        self.hands.close()
        self.pose.close()

    def process(self, frame_bgr):
        """Frame BGR (tidak di-mirror) -> vektor mentah dalam piksel, belum dinormalisasi.

        Mengembalikan (vec, ada_tangan). vec berisi koordinat piksel (x*w, y*h, z*w),
        nol untuk tangan yang tidak terdeteksi; pose NaN jika tidak terdeteksi.
        """
        import cv2
        h0, w0 = frame_bgr.shape[:2]
        if w0 > PROC_WIDTH:
            s = PROC_WIDTH / w0
            frame_bgr = cv2.resize(frame_bgr, (PROC_WIDTH, int(round(h0 * s))))
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        hr = self.hands.process(rgb)
        pr = self.pose.process(rgb)
        self.last_hands, self.last_pose = hr, pr

        vec = np.zeros(BASE_DIM, np.float32)
        if hr.multi_hand_landmarks:
            for lms, hd in zip(hr.multi_hand_landmarks, hr.multi_handedness):
                # Label handedness MediaPipe mengasumsikan gambar mirror; karena frame
                # tidak di-mirror, "Right" dari MediaPipe = tangan kiri penutur.
                # Yang penting konsisten di training dan aplikasi.
                is_left = hd.classification[0].label == "Right"
                sl, flag = (L_SL, 0) if is_left else (R_SL, 1)
                if vec[FLAG_SL][flag]:
                    continue  # dua deteksi dengan label sama: ambil yang pertama
                pts = np.array([[p.x * w, p.y * h, p.z * w] for p in lms.landmark], np.float32)
                vec[sl] = pts.reshape(-1)
                vec[FLAG_SL.start + flag] = 1.0
        if pr.pose_landmarks:
            lm = pr.pose_landmarks.landmark
            pts = np.array([[lm[i].x * w, lm[i].y * h, lm[i].z * w] for i in POSE_IDX], np.float32)
            vec[P_SL] = pts.reshape(-1)
        else:
            vec[P_SL] = np.nan
        return vec, bool(vec[FLAG_SL].any())


def normalize_sequence(raw):
    """(N, BASE_DIM) piksel -> dinormalisasi terhadap titik tengah & lebar bahu.

    Bahu diambil per frame; frame tanpa pose memakai nilai frame valid terdekat.
    Jika seluruh segmen tanpa pose, dipakai pusat & skala dari tangan (fallback).
    """
    raw = np.asarray(raw, np.float32)
    n = len(raw)
    pose = raw[:, P_SL].reshape(n, len(POSE_IDX), 3)
    ls, rs = pose[:, 1, :2], pose[:, 2, :2]
    center = (ls + rs) / 2
    width = np.linalg.norm(ls - rs, axis=1)
    valid = np.isfinite(width) & (width > 1e-3)

    if valid.any():
        idx = np.where(valid)[0]
        nearest = idx[np.abs(np.arange(n)[:, None] - idx[None, :]).argmin(1)]
        center, width = center[nearest], width[nearest]
    else:
        flags = raw[:, FLAG_SL]
        hand_xy = np.concatenate([raw[:, L_SL].reshape(n, N_HAND, 3)[:, :, :2][flags[:, 0] > 0],
                                  raw[:, R_SL].reshape(n, N_HAND, 3)[:, :, :2][flags[:, 1] > 0]])
        c = hand_xy.reshape(-1, 2).mean(0) if len(hand_xy) else np.zeros(2, np.float32)
        center = np.tile(c, (n, 1))
        width = np.full(n, 200.0, np.float32)  # perkiraan lebar bahu dalam piksel @960px

    out = raw.copy()
    out[:, P_SL] = np.nan_to_num(out[:, P_SL])
    for sl, flag in ((L_SL, 0), (R_SL, 1), (P_SL, None)):
        pts = out[:, sl].reshape(n, -1, 3)
        pts[:, :, :2] -= center[:, None, :]
        pts /= width[:, None, None]
        if flag is not None:
            pts[raw[:, FLAG_SL.start + flag] == 0] = 0.0
        out[:, sl] = pts.reshape(n, -1)
    return out


def trim_to_hands(raw):
    """Potong ke frame pertama..terakhir yang tangannya terdeteksi. None jika tidak ada."""
    present = np.asarray(raw)[:, FLAG_SL].any(1)
    if not present.any():
        return None
    idx = np.where(present)[0]
    return raw[idx[0]: idx[-1] + 1]


def resample(seq, t=T):
    """Ambil t frame yang tersebar seragam (nearest frame)."""
    n = len(seq)
    idx = np.round(np.linspace(0, n - 1, t)).astype(int)
    return seq[idx]


def add_velocity(seq):
    """Tambahkan delta antar frame. Velocity tangan dinolkan jika tangan hilang di salah satu frame."""
    vel = np.zeros_like(seq)
    vel[1:] = seq[1:] - seq[:-1]
    for sl, flag in ((L_SL, FLAG_SL.start), (R_SL, FLAG_SL.start + 1)):
        both = np.zeros(len(seq), bool)
        both[1:] = (seq[1:, flag] > 0) & (seq[:-1, flag] > 0)
        vel[~both, sl] = 0.0
    vel[:, FLAG_SL] = 0.0
    return np.concatenate([seq, vel], axis=1).astype(np.float32)


def to_model_input(norm_seq, t=T):
    """Sekuens ternormalisasi (sudah di-trim) -> (t, FEAT_DIM)."""
    return add_velocity(resample(norm_seq, t))


def hand_motion(seq):
    """Total perpindahan titik tengah tangan (satuan lebar bahu) dari tangan yang paling aktif."""
    best = 0.0
    for sl, flag in ((L_SL, FLAG_SL.start), (R_SL, FLAG_SL.start + 1)):
        on = seq[:, flag] > 0
        if on.sum() < 2:
            continue
        c = seq[on][:, sl].reshape(-1, N_HAND, 3)[:, :, :2].mean(1)
        best = max(best, float(np.linalg.norm(np.diff(c, axis=0), axis=1).sum()))
    return best
