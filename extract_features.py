"""Ekstraksi fitur landmark dari video dataset ke data/processed/.

Label diambil dari teks di dalam kurung pada nama folder kelas, mis.
"bisindo isyara ai ( halo)" -> "halo". Video dipotong ke rentang frame saat tangan
terdeteksi (sama seperti segmentasi di aplikasi), lalu di-resample ke T frame.

Pakai:  python extract_features.py --data-root ".data/bisindo isyara ai"
"""
import argparse
import json
import re
import time
from pathlib import Path

import cv2
import numpy as np

import features as F

VIDEO_EXT = {".mov", ".mp4", ".avi", ".mkv", ".m4v"}


def label_from_folder(name):
    m = re.search(r"\(([^)]*)\)", name)
    return (m.group(1) if m else name).strip().lower()


def extract_video(path):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    ext = F.LandmarkExtractor()
    raw = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            vec, _ = ext.process(frame)
            raw.append(vec)
    finally:
        ext.close()
        cap.release()
    return np.stack(raw) if raw else np.zeros((0, F.BASE_DIM), np.float32), fps


def stratified_split(y, ratios=(0.7, 0.15, 0.15), seed=42):
    rng = np.random.default_rng(seed)
    split = np.empty(len(y), dtype=object)
    for c in np.unique(y):
        idx = rng.permutation(np.where(y == c)[0])
        n = len(idx)
        n_val = max(1, int(round(n * ratios[1])))
        n_test = max(1, int(round(n * ratios[2])))
        split[idx[:n_val]] = "val"
        split[idx[n_val:n_val + n_test]] = "test"
        split[idx[n_val + n_test:]] = "train"
    return split


def write_prototypes(processed, assets):
    """Contoh referensi untuk aplikasi: dipakai menolak gerakan yang tidak mirip data training."""
    d = np.load(Path(processed) / "dataset.npz")
    seqs = np.split(d["seq_concat"], np.cumsum(d["seq_len"])[:-1])
    pos = np.stack([F.resample(s) for s in seqs])
    y = d["y"]
    motion = np.array([F.hand_motion(p) for p in pos])
    # jarak leave-one-out ke contoh sekelas terdekat = skala "seberapa mirip itu wajar"
    loo = []
    for i in range(len(pos)):
        same = (y == y[i]) & (np.arange(len(pos)) != i)
        loo.append(np.sqrt(((pos[same] - pos[i]) ** 2).mean((1, 2))).min())
    d_ref = float(np.max(loo))
    motion_min = float(0.5 * motion.min())
    Path(assets).mkdir(parents=True, exist_ok=True)
    np.savez_compressed(Path(assets) / "prototypes.npz", pos=pos.astype(np.float16), y=y,
                        d_ref=d_ref, motion_min=motion_min)
    print(f"prototypes.npz: {len(pos)} contoh, d_ref={d_ref:.3f}, "
          f"gerakan per kelas min={[round(float(motion[y == c].min()), 2) for c in np.unique(y)]}, "
          f"ambang gerakan={motion_min:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".data/bisindo isyara ai")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--assets", default="assets")
    ap.add_argument("--prototypes-only", action="store_true",
                    help="hanya buat ulang assets/prototypes.npz dari dataset.npz yang sudah ada")
    args = ap.parse_args()
    if args.prototypes_only:
        write_prototypes(args.out, args.assets)
        return

    root, out = Path(args.data_root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    class_dirs = sorted(d for d in root.iterdir() if d.is_dir())
    labels = sorted({label_from_folder(d.name) for d in class_dirs})
    print("Kelas:", labels)

    X, y, files, seqs, log = [], [], [], [], []
    t0 = time.time()
    for d in class_dirs:
        lab = label_from_folder(d.name)
        vids = sorted(p for p in d.iterdir() if p.suffix.lower() in VIDEO_EXT)
        for i, p in enumerate(vids, 1):
            raw, fps = extract_video(p)
            n = len(raw)
            hand = raw[:, F.FLAG_SL].any(1) if n else np.zeros(0, bool)
            pose_ok = np.isfinite(raw[:, F.P_SL]).all(1) if n else np.zeros(0, bool)
            trimmed = F.trim_to_hands(raw) if n else None
            entry = dict(file=f"{d.name}/{p.name}", label=lab, frames=n, fps=round(fps, 2),
                         hand_frames=int(hand.sum()), pose_frames=int(pose_ok.sum()),
                         left_frames=int(raw[:, F.FLAG_SL.start].sum()) if n else 0,
                         right_frames=int(raw[:, F.FLAG_SL.start + 1].sum()) if n else 0)
            if trimmed is None or len(trimmed) < F.MIN_SEG_FRAMES:
                entry["status"] = "tangan_tidak_terdeteksi" if trimmed is None else "segmen_terlalu_pendek"
                print(f"  [LEWATI] {entry['file']}: {entry['status']}")
            else:
                norm = F.normalize_sequence(trimmed)
                entry.update(status="ok", seg_frames=len(trimmed),
                             seg_sec=round(len(trimmed) / fps, 2),
                             gap_frames=int((~trimmed[:, F.FLAG_SL].any(1)).sum()))
                X.append(F.to_model_input(norm))
                y.append(labels.index(lab))
                files.append(entry["file"])
                seqs.append(norm)
            log.append(entry)
            print(f"  {lab:12s} {i:2d}/{len(vids)} {p.name} frames={n} tangan={entry['hand_frames']}"
                  f" segmen={entry.get('seg_frames', '-')}  ({time.time() - t0:.0f}s)", flush=True)

    X, y = np.stack(X), np.array(y)
    split = stratified_split(y, seed=args.seed)
    lengths = np.array([len(s) for s in seqs])
    np.savez_compressed(out / "dataset.npz", X=X, y=y, files=np.array(files),
                        split=split.astype(str), seq_concat=np.concatenate(seqs),
                        seq_len=lengths)
    (out / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2))
    (out / "splits.json").write_text(json.dumps(
        {s: [f for f, sp in zip(files, split) if sp == s] for s in ("train", "val", "test")}, indent=2))
    (out / "extraction_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2))
    print(f"\nSelesai {time.time() - t0:.0f}s. X={X.shape}, simpan di {out}/")
    write_prototypes(out, args.assets)


if __name__ == "__main__":
    main()
