"""Efek suara film dari kode (numpy), disimpan sebagai WAV 48 kHz di suara/.

Jalankan dengan Python bawaan Blender:
    blender --background --python sfx.py

Tidak ada suara dari internet: semua disintesis dari noise, nada, dan filter
(FFT). Bilangan acak memakai seed tetap, jadi hasilnya selalu sama.

Suara latar yang perlu diulang (hujan, kali, mesin idle, detak penyeberangan,
tetes talang) dibuat melingkar: noise difilter di domain frekuensi dan semua
pola berulang tepat sepanjang berkas, jadi ujungnya menyambung mulus ke awal.
"""

import math
import os
import wave

import numpy as np

AKAR = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(AKAR, "suara")
SR = 48000
SEED = 4848
rng = np.random.default_rng(SEED)


# --------------------------------------------------------------------------
# Alat bantu


def waktu(dur):
    return np.arange(int(dur * SR)) / SR


def noise(n):
    return rng.standard_normal(n)


def saring(x, gain_fn, melingkar=False):
    """Filter linear lewat FFT. gain_fn(frekuensi Hz) -> penguatan (array).
    melingkar=True: konvolusi sirkular (untuk loop); False: diberi bantalan."""
    n = len(x)
    pad = 0 if melingkar else n
    X = np.fft.rfft(x, n + pad)
    f = np.fft.rfftfreq(n + pad, 1 / SR)
    y = np.fft.irfft(X * gain_fn(f), n + pad)
    return y[:n]


def pita(lo, hi, curam=2.0):
    """Penguatan band-pass halus (Butterworth kira-kira)."""
    def g(f):
        f = np.maximum(f, 1e-3)
        a = 1.0 if lo <= 0 else 1 / np.sqrt(1 + (lo / f) ** (2 * curam))
        b = 1.0 if hi is None else 1 / np.sqrt(1 + (f / hi) ** (2 * curam))
        return a * b
    return g


def puncak(*resonansi):
    """Penguatan berupa puncak-puncak resonansi: (frekuensi, lebar, tinggi)."""
    def g(f):
        hasil = np.zeros_like(f)
        for fc, lebar, tinggi in resonansi:
            hasil += tinggi * np.exp(-0.5 * ((f - fc) / lebar) ** 2)
        return hasil
    return g


def merah_muda(f):
    return 1 / np.sqrt(np.maximum(f, 20.0))


def coklat(f):
    return 1 / np.maximum(f, 20.0)


def luruh(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def tempel(dasar, potongan, mulai, gain=1.0, melingkar=False):
    """Tambahkan potongan suara ke dasar mulai sampel `mulai`."""
    i = int(mulai)
    n = len(potongan)
    if melingkar:
        idx = (np.arange(n) + i) % len(dasar)
        np.add.at(dasar, idx, potongan * gain)
    else:
        akhir = min(len(dasar), i + n)
        if i < len(dasar):
            dasar[i:akhir] += potongan[: akhir - i] * gain


def gema(x, rt=0.4, campur=0.25, gelap=4000):
    """Gema ruang sederhana: konvolusi dengan noise yang meluruh."""
    n_ir = int(rt * SR)
    ir = noise(n_ir) * luruh(n_ir, rt / 6.9)
    ir = saring(ir, pita(0, gelap))
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    basah = np.fft.irfft(np.fft.rfft(x, len(x) + n_ir) * np.fft.rfft(ir, len(x) + n_ir), len(x) + n_ir)[: len(x)]
    return x * (1 - campur) + basah * campur


def jauh(x, jarak):
    """Suara dari kejauhan: lebih pelan dan lebih gelap."""
    return saring(x, pita(0, 9000 / (1 + jarak / 6))) / (1 + jarak / 4)


def fade(x, masuk=0.01, keluar=0.05):
    n = len(x)
    a, b = int(masuk * SR), int(keluar * SR)
    x = x.copy()
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def normal(x, puncak_db):
    m = np.max(np.abs(x)) + 1e-12
    return x / m * 10 ** (puncak_db / 20)


HASIL = []


def simpan(nama, x, puncak_db=-6.0, ulang=False):
    """Simpan WAV 16-bit. x: (n,) mono atau (n, 2) stereo."""
    x = normal(np.asarray(x, dtype=np.float64), puncak_db)
    if not ulang:  # suara sekali bunyi: tanpa klik di awal/akhir
        x = fade(x, 0.003, 0.02) if x.ndim == 1 else np.stack([fade(x[:, 0], 0.003, 0.02), fade(x[:, 1], 0.003, 0.02)], 1)
    data = np.clip(x, -1, 1)
    saluran = 1 if data.ndim == 1 else 2
    jalur = os.path.join(FOLDER, nama)
    with wave.open(jalur, "wb") as w:
        w.setnchannels(saluran)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((data * 32767).astype("<i2").tobytes())
    pk = 20 * math.log10(np.max(np.abs(data)) + 1e-12)
    rms = 20 * math.log10(np.sqrt(np.mean(data ** 2)) + 1e-12)
    HASIL.append((nama, len(data) / SR, pk, rms, "loop" if ulang else ""))


# --------------------------------------------------------------------------
# Hujan dan kali (loop mulus)


def hujan(dur, kepadatan, kerasnya, rintik_besar):
    n = int(dur * SR)
    kanal = []
    for _ in range(2):  # stereo: dua kanal tak berkorelasi
        desis = saring(noise(n), lambda f: merah_muda(f) * pita(400, 9000)(f), melingkar=True)
        desis /= np.std(desis)
        # Tetes: impuls acak dikonvolusi dengan klik pendek yang meluruh (sirkular)
        tetes = np.zeros(n)
        jumlah = int(kepadatan * dur)
        pos = rng.integers(0, n, jumlah)
        tetes[pos] = rng.uniform(0.2, 1.0, jumlah) ** 2
        klik = noise(int(0.006 * SR)) * luruh(int(0.006 * SR), 0.0012)
        tetes = np.real(np.fft.ifft(np.fft.fft(tetes) * np.fft.fft(klik, n)))
        tetes = saring(tetes, pita(1500, 12000), melingkar=True)
        tetes /= np.std(tetes) + 1e-9
        # Tetes besar yang jarang (genangan, atap)
        besar = np.zeros(n)
        for p in rng.integers(0, n, int(rintik_besar * dur)):
            m = int(0.04 * SR)
            plop = np.sin(2 * np.pi * rng.uniform(900, 2200) * np.arange(m) / SR) * luruh(m, 0.008)
            tempel(besar, plop, p, rng.uniform(0.3, 1.0), melingkar=True)
        kanal.append(desis * kerasnya + tetes * 0.35 + besar * 0.25)
    return np.stack(kanal, 1)


def kali(dur):
    n = int(dur * SR)
    kanal = []
    for _ in range(2):
        gemuruh = saring(noise(n), lambda f: coklat(f) * pita(30, 700)(f), melingkar=True)
        gemuruh /= np.std(gemuruh)
        riak = saring(noise(n), lambda f: merah_muda(f) * pita(600, 3500)(f), melingkar=True)
        riak /= np.std(riak)
        # Ayunan pelan arus; periodik tepat sepanjang loop
        t = np.arange(n) / n
        ayun = 1 + 0.25 * np.sin(2 * np.pi * 3 * t + rng.uniform(0, 6)) + 0.12 * np.sin(2 * np.pi * 7 * t)
        kanal.append(gemuruh * ayun + riak * 0.18 * ayun ** 2)
    return np.stack(kanal, 1)


# --------------------------------------------------------------------------
# Motor bebek (satu silinder empat langkah: letupan tiap dua putaran)


def mesin(rpm, beban=None, melingkar=False):
    """rpm: array per sampel. beban: 0..1 (gas), mempengaruhi kekasaran.
    melingkar=True: noise difilter sirkular (untuk loop idle tanpa sambungan)."""
    n = len(rpm)
    beban = np.zeros(n) if beban is None else beban
    f = rpm / 120.0  # frekuensi letupan
    fase = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros(n)
    for k in range(1, 70):
        frek = k * f
        a = (1.0 / k ** 0.9) * (1 + 0.6 * (k % 2 == 1)) * (frek < 9000)
        x += a * np.sin(k * fase + rng.uniform(0, 2 * np.pi))
    # Letupan knalpot: noise yang berdenyut mengikuti siklus mesin
    denyut = (0.5 + 0.5 * np.cos(fase)) ** 6
    letup = saring(noise(n), pita(150, 2500), melingkar) * denyut
    # Ketukan klep (tiap putaran engkol)
    klep = saring(noise(n), pita(3000, 8000), melingkar) * (0.5 + 0.5 * np.cos(2 * fase + 1.0)) ** 20
    return x * 0.6 + letup * (0.8 + 1.2 * beban) + klep * 0.15


def motor_idle(dur=6.0):
    """Idle 1320 rpm: 11 letupan per detik, 66 letupan pas dalam 6 detik (loop mulus)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    rpm = 1320 + 25 * np.sin(2 * np.pi * t / dur * 3)  # goyangan idle, periodik dalam loop
    # sambungan loop: fase harmonik berakhir tepat kelipatan 2pi (jumlah letupan bulat)
    return mesin(rpm, melingkar=True)


def motor_gas_menjauh(dur=6.0):
    t = waktu(dur)
    naik = np.clip(t / 1.4, 0, 1)
    rpm = 1320 + (6800 - 1320) * (1 - (1 - naik) ** 2)
    rpm[t > 1.6] *= 1 - 0.18 * np.clip((t[t > 1.6] - 1.6) / 0.25, 0, 1)  # ganti gigi
    rpm[t > 1.85] = 5600 + 900 * np.clip((t[t > 1.85] - 1.85) / 1.5, 0, 1)
    beban = np.clip(t / 0.3, 0, 1)
    x = mesin(rpm, beban)
    # Menjauh: makin pelan dan makin gelap; efek Doppler kecil sudah tersirat di rpm
    jarak = np.clip(t - 0.8, 0, None) * 7.0
    dekat = x / (1 + jarak / 4)
    gelap = saring(x, pita(0, 1200)) / (1 + jarak / 4)
    w = np.clip(jarak / 25, 0, 1)
    return dekat * (1 - w) + gelap * w


def motor_melambat(dur=4.0):
    t = waktu(dur)
    rpm = 1320 + (5200 - 1320) * np.exp(-t / 0.9)
    x = mesin(rpm, np.zeros_like(t))
    # Letupan balik knalpot saat gas dilepas
    for p in rng.uniform(0.15, 1.6, 6):
        m = int(0.05 * SR)
        pop = saring(noise(m), pita(80, 1500)) * luruh(m, 0.012)
        tempel(x, pop * 3, p * SR)
    return x


def motor_mati(dur=2.6):
    t = waktu(dur)
    rpm = np.where(t < 0.9, 1320.0, 1320 * np.exp(-(t - 0.9) / 0.25))
    x = mesin(rpm) * np.clip(1.4 - (t - 0.9) / 0.9, 0, 1)
    # Bunyi kunci kontak diputar
    m = int(0.02 * SR)
    tempel(x, saring(noise(m), pita(2000, 9000)) * luruh(m, 0.003) * 2, 0.85 * SR)
    # Mesin panas berdetak pelan setelah mati
    for p in (1.9, 2.3):
        tempel(x, np.sin(2 * np.pi * 4200 * np.arange(800) / SR) * luruh(800, 0.002) * 0.2, p * SR)
    return x


# --------------------------------------------------------------------------
# Jalan, kali, kota


def ban_genangan(dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    selubung = np.exp(-((t - 0.35) / 0.18) ** 2) + 0.4 * np.exp(-((t - 0.75) / 0.25) ** 2)
    x = saring(noise(n), pita(250, 5000)) * selubung
    # Percikan butir air
    for p in rng.uniform(0.25, 1.2, 40):
        m = int(0.03 * SR)
        f0 = rng.uniform(1500, 4500)
        tempel(x, np.sin(2 * np.pi * f0 * np.arange(m) / SR) * luruh(m, 0.004) * 0.3, p * SR)
    return x


def ban_decit(dur=1.3):
    t = waktu(dur)
    f0 = 880 + 120 * np.sin(2 * np.pi * 6 * t) + 40 * saring(noise(len(t)), pita(0, 30)) * 50
    fase = 2 * np.pi * np.cumsum(f0) / SR
    nada = np.sin(fase) + 0.5 * np.sin(2 * fase + 0.3) + 0.25 * np.sin(3 * fase)
    kasar = saring(noise(len(t)), pita(600, 4000)) * 0.6
    selubung = np.clip(t / 0.05, 0, 1) * np.clip((dur - t) / 0.35, 0, 1)
    return (nada + kasar) * selubung


def kerikil_air(dur=1.6):
    x = np.zeros(int(dur * SR))
    for p in (0.05, 0.18, 0.31, 0.47, 0.8):
        m = int(0.12 * SR)
        tt = np.arange(m) / SR
        f = rng.uniform(500, 900) * (1 + 3 * tt / 0.12)  # gelembung: nada naik cepat
        plop = np.sin(2 * np.pi * np.cumsum(f) / SR) * luruh(m, 0.03)
        klik = saring(noise(400), pita(2000, 8000)) * luruh(400, 0.0008)
        tempel(x, plop * rng.uniform(0.4, 1.0), p * SR)
        tempel(x, klik * 0.6, p * SR)
    return gema(x, 0.5, 0.2)


def klakson_samar(dur=1.6):
    t = waktu(dur)
    nada = np.zeros_like(t)
    for f0 in (415.0, 495.0):  # dua nada klakson
        fase = 2 * np.pi * f0 * t
        nada += np.sign(np.sin(fase)) * 0.5 + np.sin(fase)
    selubung = ((t > 0.1) & (t < 0.45)) | ((t > 0.6) & (t < 1.15))
    selubung = saring(selubung.astype(float), pita(0, 40))
    x = nada * selubung
    return gema(jauh(x, 60), 1.2, 0.4, 2500)


def penyeberangan_detak(dur=2.0):
    """Detak lampu penyeberangan: 2 detak per detik, loop mulus 2 detik."""
    n = int(dur * SR)
    x = np.zeros(n)
    m = int(0.025 * SR)
    detak = saring(noise(m), puncak((1800, 300, 1), (3500, 500, 0.6))) * luruh(m, 0.004)
    for i in range(4):  # digeser 1/8 periode: sambungan loop jatuh di saat hening
        tempel(x, detak, i * n // 4 + n // 8, melingkar=True)
    return x


def penyeberangan_tit(dur=0.5):
    t = waktu(dur)
    nada = np.sin(2 * np.pi * 2800 * t) + 0.3 * np.sin(2 * np.pi * 5600 * t)
    return nada * ((t > 0.02) & (t < 0.2))


def talang_tetes(dur=8.0):
    """Tetes dari talang ke genangan, jarang dan tak teratur; loop mulus."""
    n = int(dur * SR)
    x = np.zeros(n)
    p = 0.2  # tetes pertama tidak di sambungan; gema tetes terakhir habis sebelum akhir
    while p < dur - 0.4:
        m = int(0.08 * SR)
        tt = np.arange(m) / SR
        f = rng.uniform(1100, 1900) * (1 + 1.5 * tt / 0.08)
        tempel(x, np.sin(2 * np.pi * np.cumsum(f) / SR) * luruh(m, 0.015) * rng.uniform(0.5, 1), p * SR, melingkar=True)
        p += rng.uniform(0.35, 1.1)
    return gema(x, 0.3, 0.15)


# --------------------------------------------------------------------------
# Kucing


def kucing_meong(dur=0.8):
    """Meong pendek: deret harmonik dengan nada naik-turun lewat dua formant bergerak."""
    t = waktu(dur)
    u = t / dur
    f0 = 520 + 260 * np.sin(np.pi * np.clip(u * 1.2, 0, 1)) - 120 * u
    f1 = 700 + 600 * np.sin(np.pi * u)          # "mi-a-u"
    f2 = 1700 + 300 * np.sin(np.pi * u) - 600 * u ** 2
    fase = 2 * np.pi * np.cumsum(f0) / SR
    x = np.zeros_like(t)
    for k in range(1, 30):
        fk = k * f0
        a = np.exp(-0.5 * ((fk - f1) / 220) ** 2) + 0.6 * np.exp(-0.5 * ((fk - f2) / 300) ** 2) + 0.05
        x += a * np.sin(k * fase) * (fk < 9000)
    selubung = np.clip(u / 0.12, 0, 1) * np.clip((1 - u) / 0.3, 0, 1)
    return x * selubung + saring(noise(len(t)), pita(2000, 6000)) * 0.02 * selubung


def kucing_dengkur(dur=3.0):
    t = waktu(dur)
    napas = np.sin(np.pi * (t % 1.5) / 1.5) ** 0.7  # tarik dan hembus napas
    f = np.where((t % 1.5) < 0.75, 27.0, 23.0)
    denyut = (0.5 + 0.5 * np.cos(2 * np.pi * np.cumsum(f) / SR)) ** 4
    getar = saring(noise(len(t)), pita(60, 900)) * denyut
    return getar * napas * fade(np.ones_like(t), 0.2, 0.4)


# --------------------------------------------------------------------------
# Langkah, kayu, logam, pintu


def langkah_basah(dur=3.2, jumlah=5, jarak=0.55):
    x = np.zeros(int(dur * SR))
    for i in range(jumlah):
        p = 0.15 + i * jarak + rng.uniform(-0.03, 0.03)
        m = int(0.18 * SR)
        hak = saring(noise(m), pita(60, 400)) * luruh(m, 0.02)  # hentakan tumit
        cecek = saring(noise(m), pita(900, 4500)) * luruh(m, 0.05) * (np.arange(m) > 0.02 * SR)  # air terperas
        tempel(x, hak * 1.2 + cecek * 0.6 * rng.uniform(0.7, 1.2), p * SR)
    return x


def derit(dur, f_awal, f_akhir, resonansi, kasar=0.3):
    """Derit stick-slip: deret impuls dengan laju berubah, lewat resonansi bahan."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f_awal + (f_akhir - f_awal) * (t / dur) + 15 * np.sin(2 * np.pi * 3 * t)
    fase = np.cumsum(f) / SR
    impuls = np.diff(np.floor(fase), prepend=0) * rng.uniform(0.6, 1.0, n)
    x = saring(impuls, puncak(*resonansi)) + saring(noise(n), pita(1000, 6000)) * kasar * 0.02
    return x * np.sin(np.pi * t / dur) ** 0.5


def bangku_kayu():
    return derit(1.2, 70, 130, [(420, 60, 1), (950, 90, 0.7), (1800, 150, 0.4)])


def rantai_pagar(dur=2.2):
    x = derit(dur, 140, 90, [(1850, 120, 1), (3100, 200, 0.5)], kasar=0.5) * 0.6
    for p in rng.uniform(0.1, dur - 0.3, 9):  # denting mata rantai (logam tak harmonis)
        m = int(0.25 * SR)
        tt = np.arange(m) / SR
        denting = sum(np.sin(2 * np.pi * f * tt) * a for f, a in ((2310, 1), (3870, 0.6), (5420, 0.4), (6950, 0.2)))
        tempel(x, denting * luruh(m, 0.04) * rng.uniform(0.1, 0.3), p * SR)
    return x


def ketuk_kayu():
    m = int(0.35 * SR)
    tt = np.arange(m) / SR
    badan = sum(np.sin(2 * np.pi * f * tt + rng.uniform(0, 6)) * a * luruh(m, d)
                for f, a, d in ((165, 1.0, 0.06), (410, 0.7, 0.035), (960, 0.4, 0.02), (1900, 0.2, 0.01)))
    klik = saring(noise(m), pita(800, 5000)) * luruh(m, 0.002)
    return badan + klik * 0.8


def ketuk_pintu(dur=1.6):
    x = np.zeros(int(dur * SR))
    for i, p in enumerate((0.1, 0.42, 0.74)):
        tempel(x, ketuk_kayu(), p * SR, 1.0 - 0.08 * i)
    return gema(x, 0.5, 0.18)


def langkah_kecil(dur=1.6):
    """Langkah kaki anak berlari di dalam rumah, terdengar dari balik pintu."""
    x = np.zeros(int(dur * SR))
    p = 0.05
    while p < dur - 0.2:
        m = int(0.08 * SR)
        x_step = saring(noise(m), pita(80, 900)) * luruh(m, 0.012)
        tempel(x, x_step * rng.uniform(0.6, 1.0) * (0.5 + 0.5 * p / dur), p * SR)  # mendekat
        p += rng.uniform(0.13, 0.17)
    return saring(gema(x, 0.6, 0.3, 2500), pita(0, 1800))


def kunci_diputar(dur=1.0):
    x = np.zeros(int(dur * SR))
    for p, a in ((0.08, 0.6), (0.22, 0.4), (0.36, 1.0), (0.5, 0.5)):
        m = int(0.04 * SR)
        tt = np.arange(m) / SR
        logam = sum(np.sin(2 * np.pi * f * tt) for f in (2600, 4300, 6100)) * luruh(m, 0.006)
        tempel(x, (logam + saring(noise(m), pita(3000, 10000)) * luruh(m, 0.002)) * a, p * SR)
    return x


def pintu_menutup(dur=1.5):
    x = np.zeros(int(dur * SR))
    m = int(0.5 * SR)
    tt = np.arange(m) / SR
    dentum = (np.sin(2 * np.pi * 70 * tt) + 0.6 * np.sin(2 * np.pi * 140 * tt)) * luruh(m, 0.08)
    dentum += saring(noise(m), pita(60, 600)) * luruh(m, 0.03)
    tempel(x, dentum, 0.1 * SR)
    tempel(x, kunci_diputar(0.2)[: int(0.05 * SR)] * 0.6, 0.12 * SR)  # lidah kunci masuk
    for p in (0.25, 0.33):  # sedikit getar daun pintu
        tempel(x, ketuk_kayu() * 0.15, p * SR)
    return gema(x, 0.7, 0.25)


# --------------------------------------------------------------------------
# Lilin dan keluarga


def lilin_desis(dur=0.9):
    t = waktu(dur)
    desis = saring(noise(len(t)), pita(2500, 12000)) * np.exp(-t / 0.25)
    letik = np.zeros_like(t)
    for p in rng.uniform(0.02, 0.5, 14):
        tempel(letik, noise(200) * luruh(200, 0.0006), p * SR, rng.uniform(0.3, 1.0))
    return desis + saring(letik, pita(1500, 10000)) * 0.8


def suara_tanpa_kata(dur, f_dasar, rng_lokal):
    """Satu suara orang tanpa kata: nada dan vokal acak yang berganti tiap suku kata."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    suku = np.cumsum(rng_lokal.uniform(0.12, 0.3, 200))
    idx = np.searchsorted(suku, t)
    f0 = f_dasar * (1 + 0.12 * rng_lokal.standard_normal(201))[idx]
    f0 = saring(f0 - f0.mean(), pita(0, 8)) + f0.mean()
    vokal = rng_lokal.integers(0, 5, 201)[idx]
    formant = np.array([[700, 1200], [400, 2000], [300, 2300], [500, 900], [350, 800]])
    f1 = saring(formant[vokal, 0].astype(float), pita(0, 15))
    f2 = saring(formant[vokal, 1].astype(float), pita(0, 15))
    fase = 2 * np.pi * np.cumsum(f0) / SR
    x = np.zeros(n)
    for k in range(1, 25):
        fk = k * f0
        a = np.exp(-0.5 * ((fk - f1) / 150) ** 2) + 0.5 * np.exp(-0.5 * ((fk - f2) / 220) ** 2)
        x += a * np.sin(k * fase)
    # Jeda antarkalimat
    hidup = saring((np.sin(2 * np.pi * t / rng_lokal.uniform(1.5, 2.5) + rng_lokal.uniform(0, 6)) > -0.4).astype(float), pita(0, 6))
    return x * hidup


def riuh_keluarga(dur=6.0):
    """Riuh keluarga teredam di balik pintu: beberapa suara tanpa kata, tawa kecil, sangat gelap."""
    r = np.random.default_rng(SEED + 7)
    x = sum(suara_tanpa_kata(dur, f, r) * a for f, a in ((120, 1.0), (210, 0.8), (290, 0.6), (330, 0.5)))
    t = waktu(dur)
    for p in (1.8, 4.1):  # tawa kecil: ha-ha bernada tinggi
        for j in range(4):
            m = int(0.09 * SR)
            tt = np.arange(m) / SR
            ha = sum(np.sin(2 * np.pi * 380 * k * tt) * np.exp(-0.5 * ((380 * k - 800) / 300) ** 2) for k in range(1, 10))
            tempel(x, ha * np.sin(np.pi * tt / tt[-1]) * 0.8, (p + j * 0.13) * SR)
    teredam = saring(x, pita(0, 550, 3))  # dinding dan pintu kayu memotong frekuensi tinggi
    return gema(teredam, 0.6, 0.35, 1500)


# --------------------------------------------------------------------------


def main():
    os.makedirs(FOLDER, exist_ok=True)
    simpan("hujan_deras.wav", hujan(20.0, kepadatan=2600, kerasnya=1.0, rintik_besar=6), -10, ulang=True)
    simpan("hujan_rintik.wav", hujan(20.0, kepadatan=500, kerasnya=0.35, rintik_besar=2), -16, ulang=True)
    simpan("kali_gemuruh.wav", kali(20.0), -10, ulang=True)
    simpan("motor_idle.wav", motor_idle(), -8, ulang=True)
    simpan("motor_gas_menjauh.wav", motor_gas_menjauh(), -3)
    simpan("motor_melambat.wav", motor_melambat(), -5)
    simpan("motor_mati.wav", motor_mati(), -6)
    simpan("ban_menyibak_genangan.wav", ban_genangan(), -4)
    simpan("ban_decit_rem.wav", ban_decit(), -3)
    simpan("kerikil_jatuh_air.wav", kerikil_air(), -8)
    simpan("klakson_samar.wav", klakson_samar(), -18)
    simpan("penyeberangan_detak.wav", penyeberangan_detak(), -12, ulang=True)
    simpan("penyeberangan_tit.wav", penyeberangan_tit(), -10)
    simpan("kucing_meong.wav", kucing_meong(), -6)
    simpan("kucing_dengkur.wav", kucing_dengkur(), -14)
    simpan("langkah_sepatu_basah.wav", langkah_basah(), -6)
    simpan("bangku_kayu_derit.wav", bangku_kayu(), -8)
    simpan("rantai_pagar_derit.wav", rantai_pagar(), -12)
    simpan("talang_tetes.wav", talang_tetes(), -14, ulang=True)
    simpan("ketuk_pintu_tiga.wav", ketuk_pintu(), -3)
    simpan("langkah_kecil_berlari.wav", langkah_kecil(), -12)
    simpan("kunci_diputar.wav", kunci_diputar(), -8)
    simpan("pintu_menutup.wav", pintu_menutup(), -4)
    simpan("lilin_desis.wav", lilin_desis(), -14)
    simpan("riuh_keluarga_teredam.wav", riuh_keluarga(), -16)

    print("SFX | nama file | durasi (dtk) | puncak (dBFS) | RMS (dBFS) | catatan")
    for nama, dur, pk, rms, cat in HASIL:
        print(f"SFX | {nama} | {dur:.2f} | {pk:.1f} | {rms:.1f} | {cat}")


main()
