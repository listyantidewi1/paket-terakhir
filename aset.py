"""Mengunduh aset CC0 dari Poly Haven (api.polyhaven.com) ke folder aset/.

Jalankan:
    python3 aset.py           # unduh yang belum ada, lalu tulis ASET.md
    python3 aset.py --lihat   # hanya tampilkan rencana, tanpa mengunduh

Hanya memakai pustaka standar Python, jadi bisa juga dijalankan dengan
Python bawaan Blender. Berkas yang sudah ada dan cocok md5-nya dilewati.
"""

import hashlib
import json
import os
import sys
import urllib.request

AKAR = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(AKAR, "aset")
CATATAN = os.path.join(AKAR, "ASET.md")
API = "https://api.polyhaven.com"
HALAMAN = "https://polyhaven.com/a/"
AGEN = "blender-asset-fetcher/1.0"
RESOLUSI = "2k"  # aturan proyek: tekstur paling besar 2k
LISENSI = "CC0 1.0"

# (id Poly Haven, jenis, kegunaan di film)
DAFTAR = [
    ("moonless_golf", "hdri", "Langit malam gelap, cahaya kota di cakrawala"),
    ("asphalt_01", "tekstur", "Aspal jalan"),
    ("plastered_wall", "tekstur", "Dinding plester"),
    ("red_bricks_04", "tekstur", "Bata"),
    ("clay_roof_tiles_02", "tekstur", "Genteng tanah liat"),
    ("rusty_metal_04", "tekstur", "Logam berkarat"),
    ("concrete_floor_02", "tekstur", "Beton tepi kali"),
]

# Peta tekstur yang diambil (nama di API -> format). Metal hanya jika ada.
PETA = {"Diffuse": "jpg", "nor_gl": "jpg", "Rough": "jpg",
        "Displacement": "png", "Metal": "jpg"}


def ambil_json(jalur):
    req = urllib.request.Request(API + jalur, headers={"User-Agent": AGEN})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def md5(jalur):
    h = hashlib.md5()
    with open(jalur, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def berkas_untuk(id_aset, jenis):
    """Kembalikan daftar (url, md5, ukuran) yang akan diunduh untuk satu aset."""
    files = ambil_json(f"/files/{id_aset}")
    hasil = []
    if jenis == "hdri":
        hasil.append(files["hdri"][RESOLUSI]["hdr"])
    else:
        for peta, fmt in PETA.items():
            if peta in files:
                hasil.append(files[peta][RESOLUSI][fmt])
    return [(f["url"], f["md5"], f["size"]) for f in hasil]


def unduh(url, tujuan, md5_harus):
    if os.path.exists(tujuan) and md5(tujuan) == md5_harus:
        print(f"  lewati  {os.path.relpath(tujuan, AKAR)}")
        return
    sementara = tujuan + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": AGEN})
    with urllib.request.urlopen(req, timeout=300) as r, open(sementara, "wb") as f:
        while blok := r.read(1 << 20):
            f.write(blok)
    if md5(sementara) != md5_harus:
        os.remove(sementara)
        raise RuntimeError(f"md5 tidak cocok: {url}")
    os.replace(sementara, tujuan)
    print(f"  unduh   {os.path.relpath(tujuan, AKAR)}")


def tulis_catatan(info):
    baris = [
        "# Daftar aset",
        "",
        "Semua aset dari Poly Haven, diunduh oleh `aset.py` ke folder `aset/`.",
        f"Resolusi {RESOLUSI}. Berkas ini ditulis ulang otomatis oleh `aset.py`.",
        "",
        "| Nama | Jenis | Kegunaan | Alamat halaman | Lisensi |",
        "|------|-------|----------|----------------|---------|",
    ]
    for id_aset, jenis, guna, nama in info:
        baris.append(f"| {nama} (`{id_aset}`) | {jenis} | {guna} | "
                     f"{HALAMAN}{id_aset} | {LISENSI} |")
    with open(CATATAN, "w", encoding="utf-8") as f:
        f.write("\n".join(baris) + "\n")
    print(f"Catatan ditulis: {os.path.relpath(CATATAN, AKAR)}")


def main():
    lihat = "--lihat" in sys.argv[1:]
    info = []
    total = 0
    for id_aset, jenis, guna in DAFTAR:
        nama = ambil_json(f"/info/{id_aset}")["name"]
        berkas = berkas_untuk(id_aset, jenis)
        ukuran = sum(s for _, _, s in berkas)
        total += ukuran
        print(f"{nama} ({id_aset}), {jenis}, {len(berkas)} berkas, "
              f"{ukuran / 1e6:.1f} MB, {HALAMAN}{id_aset}")
        if not lihat:
            folder = os.path.join(FOLDER, "hdri" if jenis == "hdri" else "tekstur", id_aset)
            os.makedirs(folder, exist_ok=True)
            for url, m, _ in berkas:
                unduh(url, os.path.join(folder, url.rsplit("/", 1)[1]), m)
        info.append((id_aset, jenis, guna, nama))
    print(f"Total {total / 1e6:.1f} MB")
    if not lihat:
        tulis_catatan(info)


main()
