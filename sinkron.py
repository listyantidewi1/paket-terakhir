"""Sinkronisasi suara film "Paket Terakhir Malam Ini".

Menaruh efek suara (sfx.py), gps.mp3, dan anak.mp3 di detik yang tepat, lalu
membuat suara/film.wav (stereo 48 kHz, tepat 75 detik, sekitar -14 LUFS) dan
suara/film.srt (ketiga kalimat).

Waktu kejadian tidak dikira-kira: diambil dari peristiwa yang dicatat kode
animasi di film/ (adegan.catat, bangun.shot1_motor) dan disimpan bangun.py ke
film.blend sebagai properti scene "peristiwa". Batas shot dari film/waktu.py.

Jalankan (setelah bangun.py dan sfx.py):
    blender --background --python sinkron.py

Tabrakan antara dua suara penting hanya diperingatkan di tabel, tidak digeser.
"""

import json
import math
import os
import sys
import wave

import numpy as np

AKAR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AKAR)

import aud  # noqa: E402  (modul suara Blender, untuk membaca MP3)
import bpy  # noqa: E402

from film.waktu import FPS, SHOTS  # noqa: E402

SUARA = os.path.join(AKAR, "suara")
SR = 48000
DURASI = SHOTS[-1].detik_selesai  # 75 detik
N = DURASI * SR
TARGET_LUFS = -14.0
BATAS_PUNCAK = -1.0  # dBFS
HENING_DB = -45.0  # "hampir nol" selama jeda shot 3
# Kalimat diturunkan dari puncak MP3 (sekitar -2 dan -4 dBFS) supaya setelah
# dinaikkan ke -14 LUFS puncaknya masih di bawah batas dan tidak kena limiter.
GPS_DB = -5.0
REDAM_HUJAN = -10.0  # hujan dikecilkan selama ada kalimat
REDAM_LATAR = -8.0  # kali dan mesin idle juga sedikit dikecilkan supaya kalimat GPS terdengar
ANAK_DB = -5.0


# --------------------------------------------------------------------------
# Peristiwa dari animasi

def baca_peristiwa():
    berkas = os.path.join(AKAR, "film.blend")
    bpy.ops.wm.open_mainfile(filepath=berkas)
    sc = bpy.context.scene
    if "peristiwa" not in sc:
        sys.exit("[sinkron] film.blend belum punya peristiwa; jalankan bangun.py dulu")
    assert sc.render.fps == FPS, "fps film.blend berbeda dari film/waktu.py"
    baru = max(os.path.getmtime(os.path.join(AKAR, "film", f))
               for f in os.listdir(os.path.join(AKAR, "film")) if f.endswith(".py"))
    if baru > os.path.getmtime(berkas):
        print("[sinkron] PERINGATAN: kode di film/ lebih baru dari film.blend; jalankan bangun.py lagi")
    hasil = {}
    for p in json.loads(sc["peristiwa"]):
        hasil.setdefault(p["nama"], []).append(p["frame"])
    return hasil


def detik(frame):
    """Awal frame (frame 1 = detik 0)."""
    return (frame - 1) / FPS


def shot_di(t):
    for s in SHOTS:
        if s.detik_mulai <= t < s.detik_selesai:
            return s.nomor
    return SHOTS[-1].nomor


# --------------------------------------------------------------------------
# Membaca berkas suara

_CACHE = {}


def baca(nama):
    """Array (n, 2) float, 48 kHz. WAV dari sfx.py atau MP3 lewat aud."""
    if nama in _CACHE:
        return _CACHE[nama]
    jalur = os.path.join(SUARA, nama)
    if nama.endswith(".mp3"):
        x = np.asarray(aud.Sound(jalur).resample(SR, False).data(), dtype=np.float64)
    else:
        with wave.open(jalur) as w:
            assert w.getframerate() == SR and w.getsampwidth() == 2, nama
            x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float64) / 32768
            x = x.reshape(-1, w.getnchannels())
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    _CACHE[nama] = x
    return x


def batas_bunyi(x, ambang_db=-40.0, jendela=0.01):
    """Detik awal dan akhir bagian yang terdengar (RMS 10 ms di atas ambang relatif puncak)."""
    m = int(jendela * SR)
    mono = x.mean(axis=1)
    k = len(mono) // m
    rms = np.sqrt(np.mean(mono[: k * m].reshape(k, m) ** 2, axis=1)) + 1e-12
    db = 20 * np.log10(rms / rms.max())
    ada = np.nonzero(db > ambang_db)[0]
    return ada[0] * m / SR, (ada[-1] + 1) * m / SR


def puncak(x):
    return int(np.argmax(np.abs(x).max(axis=1))) / SR


# --------------------------------------------------------------------------
# Penempatan

TRAK = []  # dict: nama, data (n,2) sepanjang film, kelompok, penting, mulai, selesai, asal


def _fade(x, masuk, keluar):
    n = len(x)
    a, b = min(int(masuk * SR), n // 2), min(int(keluar * SR), n // 2)
    if a:
        x[:a] *= np.linspace(0, 1, a)[:, None]
    if b:
        x[n - b:] *= np.linspace(1, 0, b)[:, None]
    return x


def taruh(label, berkas, t, gain_db=0.0, jangkar="awal", potong=None, sampai=None,
          masuk=0.003, keluar=0.02, kelompok="efek", penting=False, asal="", hingga=None):
    """Taruh berkas di detik t film.

    jangkar: titik suara yang jatuh tepat di t: "awal", "puncak" (sampel terkeras),
    atau "akhir". potong: (a, b) detik di dalam berkas. sampai: untuk loop,
    diulang dari t sampai detik ini. hingga: dipotong (fade 30 ms) di detik ini,
    misalnya di potongan shot. Bagian di luar 0..75 detik dibuang.
    """
    x = baca(berkas)
    if potong:
        x = x[int(potong[0] * SR): None if potong[1] is None else int(potong[1] * SR)]
    if sampai is not None:
        n = int(round((sampai - t) * SR))
        x = np.tile(x, (n // len(x) + 1, 1))[:n]
    x = _fade(x.copy() * 10 ** (gain_db / 20), masuk, keluar)
    geser = {"awal": 0.0, "puncak": puncak(x), "akhir": len(x) / SR}[jangkar]
    i0 = int(round((t - geser) * SR))
    data = np.zeros((N, 2))
    a, b = max(i0, 0), min(i0 + len(x), N)
    if b <= a:
        return None
    data[a:b] = x[a - i0: b - i0]
    if hingga is not None:
        h = int(hingga * SR)
        f = int(0.03 * SR)
        data[h - f:h] *= np.linspace(1, 0, f)[:, None]
        data[h:] = 0
        b = min(b, h)
    if sampai is None and penting:
        ba, bb = batas_bunyi(x)  # waktu terdengar, untuk tabel dan tabrakan
        mulai, selesai = max(i0 / SR + ba, 0), min(i0 / SR + bb, b / SR)
    else:
        mulai, selesai = a / SR, b / SR
    trak = dict(nama=label, data=data, kelompok=kelompok, penting=penting,
                mulai=mulai, selesai=selesai, asal=asal, berkas=berkas, i0=i0)
    TRAK.append(trak)
    return trak


# --------------------------------------------------------------------------
# Kekerasan: ITU-R BS.1770-4 (K-weighting, blok 400 ms, gate -70 dan -10)

def _respon(b, a, w):
    z = np.exp(-1j * w)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)


def lufs(x):
    n = len(x)
    w = 2 * np.pi * np.fft.rfftfreq(n, 1 / SR) / SR
    # Koefisien BS.1770 untuk 48 kHz: rak frekuensi tinggi dan RLB high-pass.
    # Hanya besaran respons yang dipakai: energi tidak bergantung pada fase.
    h = (_respon((1.53512485958697, -2.69169618940638, 1.19839281085285),
                 (1.0, -1.69065929318241, 0.73248077421585), w)
         * _respon((1.0, -2.0, 1.0), (1.0, -1.99004745483398, 0.99007225036621), w))
    y = np.fft.irfft(np.fft.rfft(x, axis=0) * np.abs(h)[:, None], n, axis=0)
    blok, langkah = int(0.4 * SR), int(0.1 * SR)
    kuadrat = np.cumsum(np.vstack([np.zeros((1, 2)), y ** 2]), axis=0)
    awal = np.arange(0, n - blok + 1, langkah)
    z = (kuadrat[awal + blok] - kuadrat[awal]) / blok  # rata-rata kuadrat per kanal
    l = -0.691 + 10 * np.log10(z.sum(axis=1) + 1e-20)
    z = z[l > -70]
    rel = -0.691 + 10 * np.log10(z.sum(axis=1).mean()) - 10
    l = -0.691 + 10 * np.log10(z.sum(axis=1) + 1e-20)
    return -0.691 + 10 * np.log10(z[l > rel].sum(axis=1).mean())


def batasi_puncak(x, batas_db):
    """Limiter sederhana: gain per blok 5 ms, serang seketika, lepas 50 ms."""
    batas = 10 ** (batas_db / 20)
    m = int(0.005 * SR)
    k = -(-len(x) // m)
    pad = np.zeros((k * m, 2))
    pad[: len(x)] = x
    pk = np.abs(pad).reshape(k, m * 2).max(axis=1)
    g = np.minimum(1.0, batas / np.maximum(pk, 1e-12))
    g = np.minimum(g, np.minimum(np.r_[g[1:], 1.0], np.r_[1.0, g[:-1]]))  # lihat ke depan dan belakang
    for i in range(1, k):  # lepas pelan
        g[i] = min(g[i], g[i - 1] + (1 - g[i - 1]) * (m / (0.05 * SR)))
    gs = np.interp(np.arange(k * m), np.arange(k) * m + m / 2, g)[: len(x)]
    return x * gs[:, None], gs


# --------------------------------------------------------------------------
# Susunan suara

def susun(P):
    S = {s.nomor: s for s in SHOTS}

    def mulai(n):
        return S[n].detik_mulai

    def akhir(n):
        return S[n].detik_selesai

    import film.adegan as A  # konstanta jadwal yang tidak dicatat sebagai peristiwa
    satu = {k: detik(v[0]) for k, v in P.items()}
    kalimat = []

    # ---- Ambien hujan: deras di shot 1-4, rintik di shot 5-8
    taruh("hujan deras", "hujan_deras.wav", 0, -3, sampai=mulai(5) + 0.15, masuk=0, keluar=0.3,
          kelompok="hujan", asal="shot 1-4")
    taruh("hujan rintik", "hujan_rintik.wav", mulai(5) - 0.15, -2, sampai=73.0, masuk=0.3, keluar=2.0,
          kelompok="hujan", asal="shot 5-8, habis saat fade ke hitam detik 73")

    # ---- Shot 1: motor lewat kamera, menyibak genangan, menjauh
    lewat = satu["motor_lewat_kamera"]
    taruh("motor gas menjauh", "motor_gas_menjauh.wav", lewat, -8, jangkar="puncak",
          keluar=0.4, asal="motor_lewat_kamera", hingga=akhir(1))
    for nama in ("ban_genangan_depan", "ban_genangan_belakang"):
        for f in P.get(nama, []):
            jauh = detik(f) > lewat + 2  # kejadian di ujung shot, motor sudah jauh
            taruh(f"ban genangan ({nama[13:]})", "ban_menyibak_genangan.wav", detik(f),
                  (-18 if jauh else -7) - (3 if "belakang" in nama else 0), asal=f"{nama} f{f:.0f}",
                  hingga=akhir(1))
    taruh("klakson samar", "klakson_samar.wav", 4.0, -14, asal="ambien jauh, tanpa peristiwa")

    # ---- Shot 2
    rem, kanan = satu["motor_berhenti_kali"], satu["motor_belok_kanan"]
    kiri, hp = satu["motor_belok_kiri"], satu["lihat_hp"]
    taruh("kali gemuruh (dekat HP)", "kali_gemuruh.wav", mulai(2), -16, sampai=detik(A.POTONG_KALI),
          masuk=0.02, keluar=0.02, kelompok="kali", asal="close-up HP, kali masih jauh")
    taruh("kali gemuruh", "kali_gemuruh.wav", detik(A.POTONG_KALI), -6, sampai=akhir(2),
          masuk=0.02, keluar=0.02, kelompok="kali", asal="kamera di seberang kali (POTONG_KALI)")
    taruh("motor idle (melaju)", "motor_idle.wav", mulai(2), -8, sampai=rem, masuk=0.02, keluar=0.3,
          kelompok="latar", asal="shot 2 sampai motor_berhenti_kali")
    lambat = len(baca("motor_melambat.wav")) / SR - (rem - kanan) - 0.3  # hanya dari belok kanan sampai rem
    taruh("motor melambat", "motor_melambat.wav", rem, -9, jangkar="akhir", potong=(lambat, None), masuk=0.3,
          asal="motor_belok_kanan sampai motor_berhenti_kali")
    taruh("motor idle (diam)", "motor_idle.wav", rem - 0.2, -10, sampai=kiri + 0.3, masuk=0.2, keluar=0.3,
          kelompok="latar", asal="motor_berhenti_kali sampai motor_belok_kiri")
    taruh("motor gas menjauh (kiri)", "motor_gas_menjauh.wav", kiri, -7, keluar=0.3,
          asal="motor_belok_kiri", hingga=akhir(2))
    taruh("ban decit rem", "ban_decit_rem.wav", rem, -9, jangkar="akhir", penting=True,
          asal="berakhir di motor_berhenti_kali")
    taruh("kerikil jatuh ke air", "kerikil_jatuh_air.wav", rem + 0.15, -6, penting=True,
          asal="motor_berhenti_kali + 0,15 dtk")
    # GPS: berkas yang sama dua kali, jadi intonasinya identik.
    g0, g1 = batas_bunyi(baca("gps.mp3"))
    gps1 = mulai(2) + 1.0  # di close-up HP, layar sudah terbaca
    if gps1 - g0 + g1 > kanan:
        print("[sinkron] PERINGATAN: GPS pertama belum selesai saat motor mulai belok kanan")
    taruh("GPS: Belok kanan (1)", "gps.mp3", gps1 - g0, GPS_DB, penting=True, kelompok="kalimat",
          asal="close-up HP, selesai sebelum motor_belok_kanan")
    taruh("GPS: Belok kanan (2)", "gps.mp3", hp - g0, GPS_DB, penting=True, kelompok="kalimat",
          asal="lihat_hp (motor diam di tepi kali)")
    kalimat += [(gps1, gps1 + g1 - g0, "Belok kanan."), (hp, hp + g1 - g0, "Belok kanan.")]

    # ---- Shot 3
    hijau = satu["lampu_hijau"]
    taruh("motor idle", "motor_idle.wav", mulai(3), -11, sampai=akhir(3), masuk=0.02, keluar=0.02,
          asal="motor diam di lampu merah")
    taruh("detak penyeberangan", "penyeberangan_detak.wav", mulai(3), -10, sampai=hijau, masuk=0.02,
          keluar=0.01, asal="sampai lampu_hijau")
    tit = taruh("tit lampu hijau", "penyeberangan_tit.wav", hijau, -4, penting=True, asal="lampu_hijau")
    hening = (tit["selesai"], tit["selesai"] + 1.0)
    taruh("kucing meong", "kucing_meong.wav", satu["kucing_mendarat"] + 0.25, -6, penting=True,
          asal="kucing_mendarat + 0,25 dtk")
    satu_langkah = (0.10, 0.55)  # langkah pertama di langkah_sepatu_basah.wav
    for f in P["langkah"]:
        taruh("langkah sepatu basah", "langkah_sepatu_basah.wav", detik(f), -8, jangkar="puncak",
              potong=satu_langkah, asal=f"langkah f{f:.0f}")
    bangku = satu["kucing_di_bangku"]
    taruh("bangku kayu berderit", "bangku_kayu_derit.wav", bangku, -8, penting=True, asal="kucing_di_bangku")
    taruh("kucing mendengkur", "kucing_dengkur.wav", bangku + 1.3, -12, masuk=0.4, keluar=0.8,
          asal="kucing_di_bangku + 1,3 dtk", hingga=akhir(3))

    # ---- Shot 4: motor pelan di gang, berhenti, mesin mati di awal shot 5
    henti, mati = satu["motor_berhenti_gang"], satu["mesin_mati"]
    taruh("motor pelan", "motor_idle.wav", mulai(4), -9, sampai=henti - 2.0, masuk=0.02, keluar=0.5)
    taruh("motor melambat", "motor_melambat.wav", henti, -7, jangkar="akhir", masuk=0.5,
          asal="berakhir di motor_berhenti_gang")
    taruh("motor idle", "motor_idle.wav", henti - 0.1, -11, sampai=mati, masuk=0.1, keluar=0.01,
          asal="motor_berhenti_gang sampai mesin_mati")
    taruh("mesin mati", "motor_mati.wav", mati, -7, penting=True, asal="mesin_mati (awal shot 5)")
    taruh("talang menetes", "talang_tetes.wav", mulai(4), -10, sampai=akhir(4), masuk=0.02, keluar=0.02)
    taruh("rantai pagar berderit", "rantai_pagar_derit.wav", mulai(4) + 2.0, -10, asal="ambien gang")
    taruh("TV samar (riuh teredam)", "riuh_keluarga_teredam.wav", mulai(4) + 0.5, -24, masuk=1, keluar=1,
          asal="ambien gang")

    # ---- Shot 6-7: ketukan, langkah kecil, kunci, pintu, kalimat anak, lilin
    satu_ketuk = (0.05, 0.40)  # ketukan pertama di ketuk_pintu_tiga.wav, dengan gemanya
    for i, f in enumerate(P["ketuk"]):
        taruh(f"ketuk pintu {i + 1}", "ketuk_pintu_tiga.wav", detik(f), -4 - i, jangkar="puncak",
              potong=satu_ketuk, keluar=0.05, penting=True, asal=f"ketuk f{f:.0f}")
    buka, terbuka = satu["pintu_mulai_buka"], satu["pintu_terbuka"]
    kunci = taruh("kunci diputar", "kunci_diputar.wav", buka, -6, jangkar="akhir", penting=True,
                  asal="berakhir di pintu_mulai_buka")
    taruh("langkah kecil berlari", "langkah_kecil_berlari.wav", kunci["i0"] / SR - 0.05, -9,
          jangkar="akhir", asal="berhenti tepat sebelum kunci diputar")
    a0, a1 = batas_bunyi(baca("anak.mp3"))
    t_anak = terbuka + 0.5
    taruh("Anak: Selamat ulang tahun, Ayah!", "anak.mp3", t_anak - a0, ANAK_DB, penting=True,
          kelompok="kalimat", asal="pintu_terbuka + 0,5 dtk")
    kalimat.append((t_anak, t_anak + a1 - a0, "Selamat ulang tahun, Ayah!"))
    taruh("lilin berdesis", "lilin_desis.wav", t_anak + (a1 - a0) + 1.5, -10, penting=True,
          asal="1,5 dtk setelah kalimat anak")

    # ---- Shot 8: riuh di balik pintu, pintu menutup, hujan sendirian, hening di judul
    tutup = satu["pintu_tertutup"]
    taruh("riuh keluarga teredam", "riuh_keluarga_teredam.wav", mulai(8), -12, sampai=tutup,
          masuk=0.3, keluar=0.15, asal="sampai pintu_tertutup")
    taruh("pintu menutup", "pintu_menutup.wav", tutup, -4, jangkar="puncak", penting=True,
          asal="bunyi terkeras di pintu_tertutup")

    return kalimat, hening


# --------------------------------------------------------------------------

def campur(kalimat, hening):
    t = np.arange(N) / SR

    def selubung(rentang, db, landai):
        g = np.ones(N)
        for a, b in rentang:
            # 1 di luar rentang, 10^(db/20) di dalam, landai linear di kedua sisi
            naik = np.clip((t - (a - landai)) / landai, 0, 1)
            turun = np.clip(((b + landai) - t) / landai, 0, 1)
            g = np.minimum(g, 1 - (1 - 10 ** (db / 20)) * np.minimum(naik, turun))
        return g

    selama = [(a, b) for a, b, _ in kalimat]
    redam = {"hujan": selubung(selama, REDAM_HUJAN, 0.25),
             "kali": selubung(selama, REDAM_LATAR, 0.25), "latar": selubung(selama, REDAM_LATAR, 0.25)}
    x = np.zeros((N, 2))
    for tr in TRAK:
        x += tr["data"] * (redam[tr["kelompok"]][:, None] if tr["kelompok"] in redam else 1)
    x *= selubung([hening], HENING_DB, 0.04)[:, None]
    # Kalimat terhadap semua suara lain selama kalimat (RMS, sebelum master)
    for a, b, teks in kalimat:
        i, j = int(a * SR), int(b * SR)
        ucap = sum(tr["data"][i:j] for tr in TRAK if tr["kelompok"] == "kalimat")
        rms = lambda y: 10 * math.log10(np.mean(y ** 2) + 1e-20)  # noqa: E731
        print(f"[sinkron] '{teks}' {a:.2f} dtk: {rms(ucap) - rms(x[i:j] - ucap):+.1f} dB di atas suara lain")
    return x


def tabrakan():
    penting = sorted((tr for tr in TRAK if tr["penting"]), key=lambda tr: tr["mulai"])
    hasil = []
    for i, a in enumerate(penting):
        for b in penting[i + 1:]:
            if b["mulai"] < a["selesai"] and a["selesai"] - b["mulai"] > 0.02:
                hasil.append((a, b, a["selesai"] - b["mulai"]))
    return hasil


def jam(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    P = baca_peristiwa()
    kalimat, hening = susun(P)
    x = campur(kalimat, hening)

    # Kekerasan -14 LUFS, puncak dibatasi -1 dBFS, ulangi supaya tetap tepat
    awal = lufs(x)
    g_total = np.ones(N)
    for _ in range(4):
        x *= 10 ** ((TARGET_LUFS - lufs(x)) / 20)
        x, g = batasi_puncak(x, BATAS_PUNCAK)
        g_total *= g
    g_min = g_total.min()
    akhir = lufs(x)
    pk = 20 * math.log10(np.abs(x).max())
    g_db = 20 * np.log10(g_total)
    for tr in TRAK:
        if tr["penting"]:
            tr["limiter"] = float(g_db[int(tr["mulai"] * SR): int(tr["selesai"] * SR) + 1].min())
    assert len(x) == N

    with wave.open(os.path.join(SUARA, "film.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).round().astype("<i2").tobytes())
    with open(os.path.join(SUARA, "film.srt"), "w", encoding="utf-8") as f:
        for i, (a, b, teks) in enumerate(sorted(kalimat), 1):
            f.write(f"{i}\n{jam(a)} --> {jam(b)}\n{teks}\n\n")

    # Tabel
    bentrok = tabrakan()
    kena = {id(tr) for a, b, _ in bentrok for tr in (a, b)}
    print()
    print(f"{'suara':34s} {'shot':>4s} {'mulai':>7s} {'selesai':>8s} {'limiter':>7s}  asal waktu")
    print("-" * 100)
    for tr in sorted(TRAK, key=lambda tr: (tr["mulai"], tr["nama"])):
        tanda = " !" if id(tr) in kena else ("*" if tr["penting"] else "")
        lim = f"{tr['limiter']:5.1f}dB" if "limiter" in tr else ""
        print(f"{tr['nama'] + tanda:34s} {shot_di(tr['mulai']):>4d} {tr['mulai']:7.2f} {tr['selesai']:8.2f} {lim:>7s}  {tr['asal']}")
    print(f"{'(hening, semua suara ' + str(int(HENING_DB)) + ' dB)':34s} {shot_di(hening[0]):>4d} "
          f"{hening[0]:7.2f} {hening[1]:8.2f} {'':7s}  1 dtk setelah tit selesai")
    for a, b, teks in kalimat:
        print(f"{'(hujan -10, kali/mesin -8: ' + teks[:5] + ')':34s} {shot_di(a):>4d} {a:7.2f} {b:8.2f} {'':7s}  selama kalimat")
    print("* = suara penting: mulai/selesai = bagian yang terdengar; limiter = tekanan terdalam di master")
    print()
    if bentrok:
        for a, b, lama in bentrok:
            print(f"[sinkron] PERINGATAN TABRAKAN: '{a['nama']}' ({a['mulai']:.2f}-{a['selesai']:.2f}) "
                  f"dan '{b['nama']}' ({b['mulai']:.2f}-{b['selesai']:.2f}) tumpang tindih {lama:.2f} dtk "
                  "(tidak digeser)")
    else:
        print("[sinkron] tidak ada suara penting yang bertabrakan")
    # Pastikan hening benar-benar hening dan kalimat terdengar di atas hujan
    i0, i1 = int(hening[0] * SR) + 2000, int(hening[1] * SR) - 2000
    rms_hening = 20 * math.log10(np.sqrt(np.mean(x[i0:i1] ** 2)) + 1e-12)
    print(f"[sinkron] hening shot 3: {hening[0]:.2f}-{hening[1]:.2f} dtk, RMS {rms_hening:.1f} dBFS")
    print(f"[sinkron] kekerasan sebelum {awal:.1f} LUFS, akhir {akhir:.2f} LUFS, puncak {pk:.1f} dBFS, "
          f"limiter paling dalam {20 * math.log10(g_min):.1f} dB")
    print(f"[sinkron] suara/film.wav: {len(x) / SR:.3f} dtk, 48 kHz stereo 16-bit; suara/film.srt: {len(kalimat)} kalimat")


main()
