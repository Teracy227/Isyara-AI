# Penerjemah BISINDO per kata

Aplikasi desktop Windows: kamera -> deteksi tangan -> subtitle + TTS. MVP, semua teks UI Bahasa Indonesia.
Tahap 0-3 selesai dan teruji di macOS (dengan file video, bukan kamera). Tahap 4 (packaging) belum dikerjakan.

## Tumpukan (jangan diubah tanpa alasan kuat)
- Python 3.11, MediaPipe Hands + Pose (bukan Holistic), pin `mediapipe==0.10.14` (butuh API `mp.solutions`).
- Model: BiLSTM kecil PyTorch, dilatih HANYA di Google Colab (`notebooks/train.ipynb`), tidak pernah di mesin lokal.
- Runtime app: ONNX Runtime saja (tanpa PyTorch). UI: PySide6. TTS: pyttsx3 (SAPI5) di worker thread.
- `features.py` dipakai bersama oleh ekstraksi, notebook, dan app. Jangan menduplikasi logika fitur.
  Fitur: T=32 frame, 298 dimensi (149 + velocity). `data/processed/features.py` adalah salinan basi, di-ignore.
- Hanya satu paket OpenCV: `opencv-contrib-python` (dibawa mediapipe). Jangan pasang `opencv-python` bersamaan.

## Data dan model
- Dataset mentah (`.data/`, tidak di repo): 86 video iPhone 1080p/30fps, 2 kelas: halo (48), terimakasih (38). Label dari nama folder.
  Klien tidak bisa memberi data tambahan. Tidak ada kelas negatif.
- "halo" = dua tangan, "terimakasih" = satu tangan (kanan). Satu peraga, satu sesi: akurasi 100% di val/test belum mencerminkan dunia nyata.
- Tanpa flip horizontal pada augmentasi (dominasi tangan bisa mengubah makna). Frame tidak di-mirror saat diproses; mirror hanya untuk preview.
- `assets/model.onnx`: input `features` (1,32,298), output `probs`. Mean/std sudah ditanam di model.
- `assets/prototypes.npz` dibuat `extract_features.py` (`--prototypes-only` untuk membuat ulang saja).

## Logika aplikasi (app/)
- `segmenter.py`: mulai saat tangan terdeteksi, selesai saat tangan hilang 0,5 dtk atau maks 3 dtk (lalu tunggu tangan turun). Segmen < 0,5 dtk dibuang.
- `predictor.py`: model 2 kelas selalu "yakin", jadi "tidak yakin" dibangun dari: prediksi harus stabil pada 3 variasi batas segmen,
  keyakinan dikalikan kemiripan dengan contoh training terdekat, dan gerakan nyaris diam ditolak. Penyaring kemiripan lemah
  (tangan digeser jauh masih lolos). Gerakan sembarang yang mirip tetap bisa terbaca sebagai kata. Tidak bisa diperbaiki tanpa data negatif.
- `camera.py`: kamera + MediaPipe + segmenter + klasifikasi di satu QThread. `--video` memutar file sebagai pengganti kamera (uji tanpa kamera).
- `tts.py`: Windows memakai pyttsx3/SAPI5 (engine dibuat di thread worker, `pythoncom.CoInitialize`). macOS memakai perintah `say`,
  karena driver pyttsx3 macOS gagal di luar main thread. Jalur SAPI5 BELUM teruji.
- `theme.py` adalah satu-satunya sumber gaya (token + QSS). Widget tidak boleh memasang warna/ukuran sendiri.
- Label "terimakasih" ditampilkan/diucapkan sebagai "terima kasih".

## Desain UI
Gelap netral, satu aksen kuning, font Atkinson Hyperlegible (bundled, `assets/fonts`), subtitle 96px sebagai hero.
Tanpa gradient, glow, bayangan bertumpuk, atau ikon emoji. Kontras tinggi (pengguna bisa tunarungu).

## Belum teruji / perlu dikerjakan di Windows
1. `pip install -r requirements.txt` dan `python -m app.main` di Windows.
2. Kamera (DirectShow), daftar kamera, ganti kamera.
3. Suara SAPI5 + fallback bila suara id-ID tidak ada; UI tidak boleh freeze saat bicara.
4. Kecepatan MediaPipe di laptop tanpa GPU (di M1: 41 ms/frame). Turunkan `model_complexity` di `features.py` HANYA bila ekstraksi dan app tetap identik
   (kalau diubah, ekstraksi ulang + latih ulang di Colab).
5. Tahap 4: PyInstaller spec (bundle `assets/`; hidden import `pyttsx3.drivers.sapi5`), workflow GitHub Actions `windows-latest`
   yang membangun .exe, dan `README.md` singkat (setup, jalan lokal, training di Colab, build).

## Aturan kerja
- Jangan menjalankan training di lokal. Jangan pasang TensorFlow. Jangan over-engineer.
- Keputusan yang bisa memutar arah proyek: tanya dulu. Keputusan kecil: putuskan sendiri dan catat di README.
- Jangan push `.data/` (video wajah orang) dan jangan sentuh `findmy/` (proyek lain, berisi kunci pribadi; sudah di-ignore).
