"""Satukan PNG hasil render.py, suara/film.wav, dan suara/film.srt menjadi film.

Jalankan dengan Python biasa (butuh ffmpeg):
    python3 gabung.py                  # film_lebar.mp4 dari render/lebar/
    python3 gabung.py --versi tegak    # film_tegak.mp4 dari render/tegak/

Video H.264 24 fps (yuv420p, CRF 18), suara AAC 48 kHz, subtitle sebagai trek
terpisah (mov_text, bahasa Indonesia) yang bisa dinyalakan atau dimatikan
pemutar; subtitle tidak dibakar ke gambar.
"""

import argparse
import os
import subprocess
import sys

AKAR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AKAR)

from film import waktu  # noqa: E402  (hanya daftar shot dan FPS, tanpa bpy)


def main():
    p = argparse.ArgumentParser(prog="gabung.py")
    p.add_argument("--versi", choices=("lebar", "tegak"), default="lebar")
    arg = p.parse_args()

    folder = os.path.join(AKAR, "render", arg.versi)
    suara = os.path.join(AKAR, "suara", "film.wav")
    teks = os.path.join(AKAR, "suara", "film.srt")
    keluar = os.path.join(AKAR, f"film_{arg.versi}.mp4")

    # Semua frame harus ada, berurutan; daftar frame ditulis untuk demuxer concat
    frames, hilang = [], []
    for s in waktu.SHOTS:
        for f in range(s.frame_mulai, s.frame_selesai + 1):
            j = os.path.join(folder, f"shot{s.nomor}", f"frame_{f:04d}.png")
            (frames if os.path.exists(j) and os.path.getsize(j) > 0 else hilang).append(j)
    if hilang:
        contoh = ", ".join(os.path.relpath(j, AKAR) for j in hilang[:3])
        sys.exit(f"[gabung] {len(hilang)} frame belum ada (misalnya {contoh}). "
                 f"Lanjutkan: blender --background --python render.py -- --versi {arg.versi}")
    for j in (suara, teks):
        if not os.path.exists(j):
            sys.exit(f"[gabung] {os.path.relpath(j, AKAR)} belum ada. Jalankan dulu: "
                     "blender --background --python sinkron.py")

    daftar = os.path.join(folder, "daftar_frame.txt")
    with open(daftar, "w") as f:
        for j in frames:
            f.write(f"file '{j}'\nduration {1 / waktu.FPS:.10f}\n")

    perintah = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y",
        "-f", "concat", "-safe", "0", "-i", daftar,
        "-i", suara,
        "-i", teks,
        "-map", "0:v", "-map", "1:a", "-map", "2:s",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-r", str(waktu.FPS), "-fps_mode", "cfr",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
        "-c:s", "mov_text", "-metadata:s:s:0", "language=ind", "-metadata:s:s:0", "title=Indonesia",
        "-metadata", "title=Paket Terakhir Malam Ini",
        "-movflags", "+faststart",
        "-t", str(len(frames) / waktu.FPS),
        keluar,
    ]
    print(f"[gabung] {len(frames)} frame + film.wav + film.srt -> {os.path.relpath(keluar, AKAR)}", flush=True)
    subprocess.run(perintah, check=True)
    os.remove(daftar)

    # Laporan isi berkas
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                           "stream=index,codec_type,codec_name,width,height,r_frame_rate,nb_frames:format=duration",
                           "-of", "compact=p=0:nk=0", keluar], capture_output=True, text=True, check=True)
    for baris in info.stdout.strip().splitlines():
        print(f"[gabung]   {baris}")


main()
