"""Kota Senja pada malam hujan: Jl. Kenanga, jalan tepi kali, dan Gang Melati.

Tiga lokasi diletakkan berjauhan di sumbu X supaya tidak saling terlihat:
    Jl. Kenanga + perempatan Jl. Mawar   x sekitar 0     (shot 1 dan 3)
    Jalan kecil tepi kali                x sekitar KALI_X (shot 2)
    Gang Melati                          x sekitar GANG_X (shot 4 sampai 8)

Lalu lintas lajur kiri: kendaraan yang menuju +Y berjalan di x < 0.
Semua bilangan acak berasal dari random.Random(SEED).
"""

import math
import random

import bpy
from mathutils import Vector

from . import bahan
from .geo import Bingkai, Kanvas, animasi_linear, kabel, koleksi, teks

SEED = 1708

# Jl. Kenanga membentang di sumbu Y, aspal x -4..4, trotoar 2 m tiap sisi.
JALAN = 4.0
TROTOAR = 2.0
TINGGI_TROTOAR = 0.15
KANOPI = 1.4  # kanopi ruko menjorok 1.4 m, tiang lampu di luar jangkauannya
Y_MAWAR = 60.0  # sumbu Jl. Mawar (perempatan), aspal y 56..64
Y_GARIS_HENTI = 53.5
KALI_X = 300.0
GANG_X = -300.0
GANG_LEBAR = 3.0

# Titik penting untuk kamera di shot.py
TITIK = {
    "motor_kenanga": Vector((-2.0, -12.0, 0.0)),
    "motor_lampu_merah": Vector((-2.0, Y_GARIS_HENTI - 1.2, 0.0)),
    "lampu_lalu_lintas": Vector((-5.0, 54.6, 0.0)),
    "bangku_warung": Vector((-6.0, 49.2, TINGGI_TROTOAR)),
    "motor_kali": Vector((KALI_X - 2.6, 26.5, 0.0)),
    "tepi_kali": Vector((KALI_X + 0.6, 32.0, 0.0)),
    "mulut_gang": Vector((GANG_X, -12.0, 0.0)),
}


def bangun():
    rng = random.Random(SEED)
    scene = bpy.context.scene
    bahan.siapkan()
    # HDRI diputar: lampu sorot lapangan golf (azimut 60-135 derajat di HDRI) dan
    # pepohonan yang disorotnya jangan sampai berada di arah +Y, arah pandang shot 1, 2, 4.
    bahan.langit(scene, kuat=0.5, putar=math.radians(-150))
    kota = koleksi("Kota")
    _cahaya_bulan(kota)
    _tanah(kota)
    _kenanga(rng, kota)
    _kali(rng, kota)
    _gang_melati(rng, kota)


# ==========================================================================
# Bagian umum


def _cahaya_bulan(kota):
    """Cahaya langit malam yang lemah dan kebiruan: bayangan jadi biru, bukan cokelat."""
    data = bpy.data.lights.new("Cahaya_Bulan", type="SUN")
    data.color = (0.5, 0.65, 1.0)
    data.energy = 0.05
    data.angle = 0.2
    obj = bpy.data.objects.new("Cahaya_Bulan", data)
    obj.rotation_euler = (math.radians(35), 0, math.radians(-30))
    kota.objects.link(obj)


def _tanah(kota):
    k = Kanvas("Tanah", kota)
    k["tanah"].kotak((-450, -200, -0.3), (450, 250, -0.05))
    k.selesai()


def _lampu(kanvas, nama, lokasi, warna, daya, jenis="SPOT", sudut=150, lunak=0.15, tepi=0.6):
    data = bpy.data.lights.new(nama, type=jenis)
    data.color = warna
    data.energy = daya
    data.shadow_soft_size = lunak
    if jenis == "SPOT":
        data.spot_size = math.radians(sudut)
        data.spot_blend = tepi
    obj = kanvas.objek(nama, data)
    obj.location = lokasi
    return obj


def _lampu_jalan(k, nama, kaki, arah, tinggi=7.5, lengan=1.8, daya=2400, sudut=72):
    """Tiang lampu natrium; lengan menjulur ke arah jalan (vektor horizontal)."""
    kaki, arah = Vector(kaki), Vector(arah).normalized()
    k["logam_gelap"].silinder(kaki, 0.08, tinggi, n=10)
    ujung = kaki + arah * lengan
    lebar = Vector((-arah.y, arah.x, 0)) * 0.05
    k["logam_gelap"].kotak(kaki - lebar + Vector((0, 0, tinggi - 0.06)),
                           ujung + lebar + Vector((0, 0, tinggi + 0.02)))
    kepala = ujung + Vector((0, 0, tinggi - 0.1))
    k["logam_gelap"].kotak(kepala - Vector((0.3, 0.3, -0.02)), kepala + Vector((0.3, 0.3, 0.12)))
    k["lampu_natrium"].kotak(kepala - Vector((0.24, 0.12, 0.03)), kepala + Vector((0.24, 0.12, 0.02)))
    # Kerucut sempit: kolam cahaya oranye yang jelas di aspal, gelap di antaranya
    _lampu(k, nama, kepala - Vector((0, 0, 0.08)), bahan.NATRIUM, daya, sudut=sudut, tepi=0.4)


UKURAN_GENANGAN = 0.55  # pusat genangan tetap; hanya jari-jarinya diperkecil


def _genangan(k, rng, pusat, jari, z=0.004):
    k["genangan"].cakram(pusat, jari * UKURAN_GENANGAN, z, rng)


def _hujan(kol, nama, x0, x1, y0, y1, z0, jumlah, rng, tinggi=10.0, laju=9.0):
    """Garis hujan bersilang yang jatuh berulang tanpa sambungan.

    Mesh berisi tetesan dalam kotak setinggi `tinggi`, digandakan ke atas
    dengan modifier Array, lalu objeknya turun `tinggi` meter berulang-ulang.
    """
    k = Kanvas(nama, kol)
    g = k["hujan"]
    panjang, lebar, angin = 0.5, 0.004, 0.06
    for _ in range(jumlah):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        z = rng.uniform(z0, z0 + tinggi)
        p = panjang * rng.uniform(0.7, 1.2)
        g.poly([(x - lebar, y, z), (x + lebar, y, z), (x + lebar + angin, y, z + p), (x - lebar + angin, y, z + p),
                (x, y - lebar, z), (x, y + lebar, z), (x + angin, y + lebar, z + p), (x + angin, y - lebar, z + p)],
               [(0, 1, 2, 3), (4, 5, 6, 7)])
    k.selesai()
    obj = k.kol.objects[0]
    obj.visible_shadow = False
    mod = obj.modifiers.new("Ulang", "ARRAY")
    mod.use_relative_offset = False
    mod.use_constant_offset = True
    mod.constant_offset_displace = (0, 0, tinggi)
    mod.count = 2
    obj.keyframe_insert("location", index=2, frame=1)
    obj.location.z = -tinggi
    obj.keyframe_insert("location", index=2, frame=1 + tinggi / laju * 24)
    obj.location.z = 0
    animasi_linear(obj, siklus=True)


def _kabut(kol, nama, a, b, kerapatan):
    k = Kanvas(nama, kol)
    nama_bahan = f"kabut_{nama}"
    bahan.kabut(nama_bahan, kerapatan)
    k[nama_bahan].kotak(a, b)
    k.selesai()


def _rumah(k, rng, f, a0, a1, mundur, dalam, kaca_nyala=0.5, lampu_teras=True, nama=""):
    """Rumah satu atau dua lantai di kavling a0..a1, fasad di b = mundur."""
    w = a1 - a0
    ra0, ra1 = a0 + 0.3, a1 - 0.3
    dua_lantai = rng.random() < 0.2
    h = 6.2 if dua_lantai else rng.uniform(3.0, 3.6)
    dinding = f"plester_{rng.randrange(len(bahan.WARNA_DINDING))}"
    f.kotak(k[dinding], ra0, ra1, mundur, mundur + dalam, 0, h)
    f.kotak(k["beton"], ra0 - 0.02, ra1 + 0.02, mundur - 0.02, mundur + dalam, 0, 0.3)

    # Pintu, kusen, lampu teras
    lebar_isi = ra1 - ra0
    pintu = ra0 + rng.uniform(0.25, 0.4) * lebar_isi
    f.kotak(k["beton"], pintu - 0.55, pintu + 0.55, mundur - 0.06, mundur, 0.1, 2.35)
    f.kotak(k["kayu_pintu"], pintu - 0.45, pintu + 0.45, mundur - 0.08, mundur - 0.02, 0.1, 2.2)
    # Jendela
    jendela = [pintu + 1.6] if lebar_isi < 5.5 else [pintu + 1.5, pintu + 2.9]
    for i, j in enumerate(jendela):
        if j + 0.6 > ra1 - 0.2:
            continue
        kaca = "kaca_hangat" if rng.random() < kaca_nyala else "kaca_gelap"
        f.kotak(k["beton"], j - 0.62, j + 0.62, mundur - 0.07, mundur, 0.92, 2.28)
        f.kotak(k[kaca], j - 0.55, j + 0.55, mundur - 0.09, mundur - 0.03, 1.0, 2.2)
        if dua_lantai:
            kaca2 = "kaca_hangat" if rng.random() < kaca_nyala * 0.6 else "kaca_gelap"
            f.kotak(k[kaca2], j - 0.55, j + 0.55, mundur - 0.09, mundur - 0.03, 4.0, 5.2)
    if lampu_teras:
        bohlam = f.titik(pintu + 0.75, mundur - 0.15, 2.45)
        k["lampu_teras"].kotak(bohlam - Vector((0.05, 0.05, 0.05)), bohlam + Vector((0.05, 0.05, 0.05)))
        _lampu(k, f"Teras_{nama}", bohlam - Vector((0, 0, 0.1)), (1.0, 0.72, 0.45), 25, jenis="POINT", lunak=0.05)

    # Kanopi teras
    if rng.random() < 0.6:
        tinggi_kanopi = 2.65
        f.kotak(k["beton"], ra0, ra1, mundur - 1.6, mundur, tinggi_kanopi, tinggi_kanopi + 0.12)
        for a in (ra0 + 0.1, ra1 - 0.25):
            f.kotak(k["beton"], a, a + 0.15, mundur - 1.55, mundur - 1.4, 0, tinggi_kanopi)

    # Atap pelana genteng, bubungan sejajar atau tegak lurus jalan
    emper = 0.5
    miring = math.tan(math.radians(rng.uniform(26, 34)))
    if rng.random() < 0.5:
        naik = (dalam / 2 + emper) * miring
        b0, b1, bm = mundur - emper, mundur + dalam + emper, mundur + dalam / 2
        x0, x1 = ra0 - emper, ra1 + emper
        f.poly(k["genteng"], [(x0, b0, h), (x1, b0, h), (x1, bm, h + naik), (x0, bm, h + naik),
                              (x1, b1, h), (x0, b1, h)], [(0, 1, 2, 3), (3, 2, 4, 5)])
        tinggi_segitiga = (dalam / 2) * miring
        for a in (ra0, ra1):
            f.poly(k[dinding], [(a, mundur, h), (a, mundur + dalam, h), (a, bm, h + tinggi_segitiga)], [(0, 1, 2)])
    else:
        naik = (lebar_isi / 2 + emper) * miring
        am = (ra0 + ra1) / 2
        b0, b1 = mundur - emper, mundur + dalam + emper
        x0, x1 = ra0 - emper, ra1 + emper
        f.poly(k["genteng"], [(x0, b0, h), (am, b0, h + naik), (am, b1, h + naik), (x0, b1, h),
                              (x1, b0, h), (x1, b1, h)], [(0, 1, 2, 3), (1, 4, 5, 2)])
        tinggi_segitiga = (lebar_isi / 2) * miring
        for b in (mundur, mundur + dalam):
            f.poly(k[dinding], [(ra0, b, h), (ra1, b, h), (am, b, h + tinggi_segitiga)], [(0, 1, 2)])
    return h


# ==========================================================================
# Jl. Kenanga dan perempatan Jl. Mawar (shot 1 dan 3)


def _kenanga(rng, kota):
    kol = koleksi("Jl_Kenanga", kota)
    k = Kanvas("Kenanga", kol)
    Y0, Y1 = -90.0, 140.0
    xt = JALAN + TROTOAR
    ym0, ym1 = Y_MAWAR - 4, Y_MAWAR + 4

    # Aspal: Kenanga utuh, Mawar dua potong (tidak tumpang tindih di perempatan)
    k["aspal_basah"].kotak((-JALAN, Y0, -0.2), (JALAN, Y1, 0))
    for x0, x1 in ((-90, -JALAN), (JALAN, 90)):
        k["aspal_basah"].kotak((x0, ym0, -0.2), (x1, ym1, 0))

    # Trotoar
    t = TINGGI_TROTOAR
    for s in (-1, 1):
        for y0, y1 in ((Y0, ym0 - TROTOAR), (ym1 + TROTOAR, Y1)):
            k["trotoar"].kotak((s * JALAN, y0, -0.2), (s * xt, y1, t))
        for y0, y1 in ((ym0 - TROTOAR, ym0), (ym1, ym1 + TROTOAR)):
            k["trotoar"].kotak((s * JALAN, y0, -0.2), (s * 90, y1, t))

    # Marka: garis tengah putus-putus, garis henti, zebra cross
    for y in range(int(Y0), int(Y1), 8):
        if ym0 - 3 < y < ym1 + 1:
            continue
        k["marka"].kotak((-0.06, y, 0), (0.06, y + 3, 0.004))
    for x in range(-90, 90, 8):
        if -JALAN - 3 < x < JALAN + 1:
            continue
        k["marka"].kotak((x, Y_MAWAR - 0.06, 0), (x + 3, Y_MAWAR + 0.06, 0.004))
    k["marka"].kotak((-JALAN, Y_GARIS_HENTI - 0.15, 0), (0, Y_GARIS_HENTI + 0.15, 0.004))
    x = -JALAN + 0.3
    while x < JALAN - 0.3:
        k["marka"].kotak((x, Y_GARIS_HENTI + 0.5, 0), (x + 0.45, ym0 - 0.3, 0.004))
        x += 0.9

    # Polisi tidur kuning-hitam
    _polisi_tidur(k, y=6.0, x0=-JALAN, x1=JALAN)

    # Genangan: di depan kamera shot 1, di garis henti (shot 3), dan di tepi trotoar
    for (x, y), r in [((-1.3, -18.0), 1.3), ((-2.6, -9.0), 0.8), ((1.2, 4.0), 1.6),
                      ((-1.8, 22.0), 1.4), ((-2.4, 49.5), 1.1), ((-0.8, 46.0), 0.9)]:
        _genangan(k, rng, (x, y), r)
    for _ in range(14):
        s = rng.choice((-1, 1))
        _genangan(k, rng, (s * rng.uniform(3.0, 3.6), rng.uniform(Y0 + 10, Y1 - 10)), rng.uniform(0.4, 0.9))

    # Deretan ruko berkanopi
    deret = [
        Bingkai((-xt, Y0, t), (0, 1, 0), (-1, 0, 0)), Bingkai((xt, Y0, t), (0, 1, 0), (1, 0, 0)),
        Bingkai((-xt, ym1 + TROTOAR, t), (0, 1, 0), (-1, 0, 0)),
        Bingkai((xt, ym1 + TROTOAR, t), (0, 1, 0), (1, 0, 0)),
        Bingkai((-90, ym0 - TROTOAR, t), (1, 0, 0), (0, -1, 0)),
        Bingkai((18, ym0 - TROTOAR, t), (1, 0, 0), (0, -1, 0)),
        Bingkai((-90, ym1 + TROTOAR, t), (1, 0, 0), (0, 1, 0)),
        Bingkai((18, ym1 + TROTOAR, t), (1, 0, 0), (0, 1, 0)),
    ]
    panjang = [ym0 - TROTOAR - 12 - Y0, ym0 - TROTOAR - Y0, Y1 - ym1 - TROTOAR, Y1 - ym1 - TROTOAR,
               72, 72, 72, 72]
    jalan = ["KENANGA"] * 4 + ["MAWAR"] * 4
    for f, p, j in zip(deret, panjang, jalan):
        _deret_ruko(k, rng, f, p, j)

    _warung(k, rng, xt, ym0 - TROTOAR, t)
    _lampu_lalu_lintas(kol, k)

    # Lampu jalan natrium: kiri dan kanan berselang-seling
    n = 0
    for y in range(int(Y0) + 6, int(Y1), 28):
        if ym0 - 4 < y < ym1 + 4:
            continue
        _lampu_jalan(k, f"Natrium_{n:02d}", (-JALAN - 0.3, y, t), (1, 0, 0))
        n += 1
        if ym0 - 4 < y + 14 < ym1 + 4:
            continue
        _lampu_jalan(k, f"Natrium_{n:02d}", (JALAN + 0.3, y + 14, t), (-1, 0, 0))
        n += 1
    for x in (-70, -40, 30, 58):
        _lampu_jalan(k, f"Natrium_{n:02d}", (x, ym0 - 0.3, t), (0, 1, 0))
        n += 1
    # Dua lampu di sudut perempatan: menerangi warung, bangku, dan garis henti
    _lampu_jalan(k, "Natrium_Sudut_0", (-JALAN - 0.3, 44.0, t), (1, 0, 0), sudut=125)
    _lampu_jalan(k, "Natrium_Sudut_1", (JALAN + 0.3, 69.0, t), (-1, 0, 0), sudut=105)

    # Tiang listrik dan kabel melintang
    pasangan = []
    tiang = []
    for y in range(int(Y0) + 10, int(Y1), 32):
        if ym0 - 3 < y < ym1 + 3:
            y += 9
        kaki = Vector((JALAN + 0.4, y, t))
        k["tiang_beton"].silinder(kaki, 0.12, 9.0, n=8)
        k["logam_gelap"].kotak(kaki + Vector((-0.8, -0.05, 8.6)), kaki + Vector((0.4, 0.05, 8.7)))
        tiang.append(kaki)
    for a, b in zip(tiang, tiang[1:]):
        for dx, dz in ((-0.7, 8.75), (0.0, 8.75), (0.35, 8.75), (0.0, 7.6)):
            pasangan.append((a + Vector((dx, 0, dz)), b + Vector((dx, 0, dz)), 0.45))
    for kaki in tiang:
        for _ in range(rng.randint(1, 3)):
            ujung = Vector((-xt - 0.1, kaki.y + rng.uniform(-6, 6), t + rng.uniform(5.5, 7.5)))
            pasangan.append((kaki + Vector((-0.7, 0, 8.6)), ujung, rng.uniform(0.4, 0.9)))
    kabel(k, "Kabel_Kenanga", pasangan, "kabel")

    k.selesai()
    _hujan(kol, "Hujan_Kenanga", -14, 14, -30, 62, 0.0, 26000, rng)
    _kabut(kol, "Kabut_Kenanga", (-100, -100, -1), (100, 150, 40), 0.005)


def _polisi_tidur(k, y, x0, x1, lebar=0.9, tinggi=0.08, n=8):
    titik = []
    for x in (x0, x1):
        for i in range(n + 1):
            t = i / n
            titik.append((x, y - lebar / 2 + lebar * t, tinggi * math.sin(math.pi * t)))
    m = n + 1
    muka = [(i, i + 1, m + i + 1, m + i) for i in range(n)]
    muka += [tuple(range(m)), tuple(range(m, 2 * m))]
    k["polisi_tidur"].poly(titik, muka)


def _deret_ruko(k, rng, f, panjang, nama_jalan):
    a = 0.0
    nomor = 1
    while a < panjang - 2.5:
        lebar = min(rng.uniform(4.0, 5.0), panjang - a)
        a0, a1 = a, a + lebar
        lantai = rng.choice((2, 2, 3))
        h = 3.6 + 3.2 * (lantai - 1)
        dinding = f"plester_{rng.randrange(len(bahan.WARNA_DINDING))}"
        f.kotak(k[dinding], a0, a1, 0, 12, 0, h)
        f.kotak(k[dinding], a0, a1, -0.1, 0.3, h, h + 0.7)  # dinding pembatas atap
        f.kotak(k["beton"], a0, a0 + 0.25, -0.15, 0, 0, h)  # pilaster
        f.kotak(k["rolling_door"], a0 + 0.35, a1 - 0.1, -0.04, 0, 0, 3.0)
        # Papan nama di depan kanopi
        papan = rng.randrange(5)
        jenis = f"papan_nyala_{papan}" if rng.random() < 0.2 else f"papan_{papan}"
        f.kotak(k[jenis], a0 + 0.1, a1 - 0.1, -KANOPI - 0.06, -KANOPI + 0.02, 3.25, 3.95)
        # Jendela lantai atas
        jendela, ac_dinding = [], []
        for lt in range(1, lantai):
            dasar = 3.6 + 3.2 * (lt - 1)
            for j0, j1 in ((a0 + 0.6, a0 + lebar / 2 - 0.3), (a0 + lebar / 2 + 0.3, a1 - 0.5)):
                r = rng.random()
                kaca = "kaca_hangat" if r < 0.25 else "kaca_dingin" if r < 0.35 else "kaca_gelap"
                f.kotak(k["beton"], j0 - 0.08, j1 + 0.08, -0.18, 0, dasar + 0.8, dasar + 0.9)
                f.kotak(k[kaca], j0, j1, -0.05, 0, dasar + 0.9, dasar + 2.4)
                jendela.append((j0, j1, dasar))
            if rng.random() < 0.4:  # unit AC
                ac = rng.uniform(a0 + 0.6, a1 - 1.4)
                f.kotak(k["beton"], ac, ac + 0.8, -0.35, 0, dasar + 0.3, dasar + 0.85)
                ac_dinding.append((ac, dasar))
        # Detail memakai rng sendiri (dari posisi unit) supaya urutan rng utama tetap
        asal = f.titik(a0, 0, 0)
        rd = random.Random(f"ruko {asal.x:.2f} {asal.y:.2f}")
        _detail_ruko(k, rd, f, a0, a1, h, papan, jendela, ac_dinding, nama_jalan, nomor)
        nomor += 1
        a = a1


NAMA_TOKO = [
    "TOKO KELONTONG", "SEMBAKO", "FOTOKOPI", "SERVIS HP", "TOKO BANGUNAN", "BENGKEL MOTOR",
    "LAUNDRY KILOAN", "TOKO EMAS", "ALAT TULIS", "WARUNG MAKAN", "MIE AYAM", "BAKSO",
    "PERCETAKAN", "ELEKTRONIK", "JAHIT & PERMAK", "PULSA & TOKEN", "TOKO OBAT", "SALON",
    "MATERIAL", "TOKO PLASTIK", "SPAREPART", "KACAMATA", "TOKO SEPATU", "TAMBAL BAN",
]


def _detail_ruko(k, rd, f, a0, a1, h, papan, jendela, ac_dinding, nama_jalan, nomor):
    """Rolling door bergaris, kanopi seng, papan nama, teralis, talang, AC luar."""
    # Rolling door: lembaran bergelombang, rel samping, palang bawah, kotak gulungan
    d0, d1 = a0 + 0.35, a1 - 0.1
    pintu = rd.choice(("rolling_door", "rolling_door", "rolling_door_biru"))
    n = 150
    titik = []
    for a in (d0, d1):
        for i in range(n + 1):
            c = 3.0 * i / n
            titik.append((a, -0.045 - 0.012 * (0.5 + 0.5 * math.sin(2 * math.pi * c / 0.08)), c))
    f.poly(k[pintu], titik, [(i, i + 1, n + 2 + i, n + 1 + i) for i in range(n)])
    for a in (d0 - 0.06, d1):
        f.kotak(k["logam_gelap"], a, a + 0.06, -0.09, 0, 0, 3.0)
    f.kotak(k["logam_gelap"], d0, d1, -0.075, -0.03, 0, 0.07)
    for a in (d0 + 0.3, d1 - 0.36):
        f.kotak(k["logam_gelap"], a, a + 0.06, -0.1, -0.07, 0.1, 0.2)
    f.kotak(k[pintu], d0 - 0.06, d1 + 0.06, -0.34, 0, 3.0, 3.26)

    # Kanopi seng bergelombang, miring dari fasad ke depan, dengan siku besi
    seng = rd.choice(("seng_karat", "seng_galvanis", "seng_galvanis"))
    z_dalam, z_luar = 3.55, 3.28
    periode, tinggi_gel = 0.076, 0.009
    n = max(2, int((a1 - a0) / (periode / 8)))
    titik = []
    for b, z in ((0.0, z_dalam), (-KANOPI, z_luar)):
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            titik.append((a, b, z + tinggi_gel * math.sin(2 * math.pi * (a - a0) / periode)))
    f.poly(k[seng], titik, [(i, i + 1, n + 2 + i, n + 1 + i) for i in range(n)])
    f.kotak(k["seng_galvanis"], a0, a1, -0.05, 0, z_dalam, z_dalam + 0.08)
    f.kotak(k["logam_gelap"], a0, a1, -KANOPI + 0.02, -KANOPI + 0.08, z_luar - 0.07, z_luar - 0.01)
    for a in (a0 + 0.12, a1 - 0.18):
        f.batang(k["logam_gelap"], (a, 0.0, 2.95), (a, -KANOPI + 0.05, z_luar - 0.05), 0.04)

    # Papan nama: jenis usaha dan alamat, tanpa merek
    nama = rd.choice(NAMA_TOKO)
    huruf = "huruf_gelap" if papan in (2, 4) else "huruf_putih"
    lebar = a1 - a0 - 0.6
    ukuran = min(0.34, lebar / (len(nama) * 0.62))
    am = (a0 + a1) / 2
    b_teks = -KANOPI - 0.07
    teks(k, f"Papan_{nama_jalan}_{nomor}", nama, f.titik(am, b_teks, 3.67), f.muka, ukuran, huruf)
    teks(k, f"Alamat_{nama_jalan}_{nomor}", f"JL. {nama_jalan} No. {nomor}", f.titik(am, b_teks, 3.38),
         f.muka, 0.11, huruf)

    # Kusen dan teralis jendela lantai atas
    teralis = rd.choice(("teralis_gelap", "teralis_putih"))
    for j0, j1, dasar in jendela:
        z0, z1 = dasar + 0.9, dasar + 2.4
        for c0, c1 in ((z0 - 0.04, z0), (z1, z1 + 0.04)):
            f.kotak(k["kusen"], j0 - 0.04, j1 + 0.04, -0.08, 0, c0, c1)
        for a in (j0 - 0.04, j1, (j0 + j1) / 2 - 0.02):
            f.kotak(k["kusen"], a, a + 0.04, -0.08, 0, z0, z1)
        bt0, bt1 = -0.17, -0.15
        for c in (z0 + 0.02, (z0 + z1) / 2, z1 - 0.02):
            f.kotak(k[teralis], j0 - 0.06, j1 + 0.06, bt0, bt1, c - 0.015, c + 0.015)
        for a in (j0 - 0.06, j1 + 0.03):
            f.kotak(k[teralis], a, a + 0.03, bt0, bt1, z0, z1)
        a = j0 + 0.08
        while a < j1 - 0.04:
            f.kotak(k[teralis], a, a + 0.016, bt0 + 0.002, bt1 - 0.002, z0, z1)
            a += 0.11
        if rd.random() < 0.5:  # hiasan lengkung sederhana: belah ketupat di tengah
            am_j, cm = (j0 + j1) / 2, (z0 + z1) / 2
            for s in (-1, 1):
                f.batang(k[teralis], (am_j - 0.25, bt0, cm), (am_j, bt0, cm + s * 0.25), 0.014)
                f.batang(k[teralis], (am_j + 0.25, bt0, cm), (am_j, bt0, cm + s * 0.25), 0.014)

    # Talang air di tepi atap dan pipa turun di depan pilaster
    f.kotak(k["pvc"], a0, a1, -0.24, -0.1, h + 0.38, h + 0.5)
    if rd.random() < 0.75:
        f.silinder(k["pvc"], a0 + 0.12, -0.21, 0.0, 0.045, h + 0.42)
        f.kotak(k["pvc"], a0 + 0.06, a0 + 0.18, -0.27, -0.15, 0.0, 0.08)

    # AC luar: selubung putih, kipas, kisi, siku, dan pipa ke dinding
    for ac, dasar in ac_dinding:
        _unit_ac(k, f, ac - 0.005, -0.355, dasar + 0.295, 0.81, 0.355, 0.56)
    if rd.random() < 0.3:  # AC di atas kanopi seng
        ac = rd.uniform(a0 + 0.5, a1 - 1.3)
        _unit_ac(k, f, ac, -0.85, 3.58, 0.8, 0.3, 0.55)
        for a in (ac + 0.08, ac + 0.68):
            f.kotak(k["logam_gelap"], a, a + 0.04, -0.82, -0.58, 3.4, 3.58)


def _unit_ac(k, f, a, b_depan, c, lebar, dalam, tinggi):
    f.kotak(k["plastik_ac"], a, a + lebar, b_depan, b_depan + dalam, c, c + tinggi)
    cm = c + tinggi / 2
    am = a + lebar * 0.62
    f.lingkaran(k["logam_gelap"], am, b_depan - 0.004, cm, tinggi * 0.38)
    f.lingkaran(k["plastik_ac"], am, b_depan - 0.008, cm, tinggi * 0.08)
    for i in range(5):  # kisi kiri
        z = c + 0.08 + i * (tinggi - 0.16) / 4
        f.kotak(k["logam_gelap"], a + 0.05, a + lebar * 0.3, b_depan - 0.01, b_depan, z, z + 0.015)
    f.kotak(k["logam_gelap"], a + 0.05, a + 0.09, b_depan - 0.02, 0, c - 0.05, c)  # siku
    f.kotak(k["logam_gelap"], a + lebar - 0.09, a + lebar - 0.05, b_depan - 0.02, 0, c - 0.05, c)
    for dz in (0.12, 0.2):
        f.kotak(k["pipa_ac"], a + lebar, a + lebar + 0.04, b_depan + 0.1, 0, c + dz, c + dz + 0.03)


def _warung(k, rng, xt, y_batas, t):
    """Warung kayu yang sudah tutup di sudut perempatan, dengan bangku kayu."""
    # Kavling sudut: paving dan rumah dua lantai di belakang warung
    k["trotoar"].kotak((-18, y_batas - 12, -0.2), (-xt, y_batas, t))
    f = Bingkai((-xt, y_batas - 12, t), (0, 1, 0), (-1, 0, 0))
    f.kotak(k["plester_4"], 0, 12, 7.0, 12, 0, 6.8)
    f.kotak(k["kaca_hangat"], 3, 5, 6.95, 7.0, 4.0, 5.4)

    x0, x1 = -10.5, -6.6  # badan warung
    y0, y1 = 47.0, 53.0
    k["kayu"].kotak((x0, y0, t), (x1, y1, t + 2.5))
    # Papan penutup (warung tutup)
    y = y0 + 0.1
    while y < y1 - 0.2:
        k["kayu_pintu" if int((y - y0) / 0.3) % 2 else "kayu"].kotak((x1, y, t + 0.3), (x1 + 0.04, y + 0.28, t + 2.3))
        y += 0.3
    # Atap seng miring menjorok ke trotoar, dua tiang kayu
    k["seng_karat"].poly([(x0 - 0.2, y0 - 0.3, t + 2.95), (-4.9, y0 - 0.3, t + 2.5),
                          (-4.9, y1 + 0.3, t + 2.5), (x0 - 0.2, y1 + 0.3, t + 2.95)], [(0, 1, 2, 3)])
    for y in (y0 - 0.1, y1 + 0.02):
        k["kayu"].kotak((-5.05, y, t), (-4.95, y + 0.08, t + 2.5))
    # Bangku kayu panjang di emperan
    bx, by = -6.0, 49.2
    k["kayu"].kotak((bx - 0.2, by - 1.2, t + 0.42), (bx + 0.2, by + 1.2, t + 0.47))
    for dy in (-1.05, 1.0):
        for dx in (-0.17, 0.12):
            k["kayu"].kotak((bx + dx, by + dy, t), (bx + dx + 0.05, by + dy + 0.05, t + 0.42))
    # Papan nama warung
    k["papan_4"].kotak((x1 + 0.02, 48.5, t + 2.0), (x1 + 0.06, 51.5, t + 2.4))
    teks(k, "Tulisan_Warung", "WARUNG", (x1 + 0.08, 50.0, t + 2.2), (1, 0, 0), 0.3, "huruf_nomor")
    # Genteng plastik terbalik, ember, kardus: cukup satu ember
    k["pot"].kotak((bx + 0.3, by + 1.5, t), (bx + 0.6, by + 1.8, t + 0.3))


def _lampu_lalu_lintas(kol, k):
    kaki = TITIK["lampu_lalu_lintas"] + Vector((0, 0, TINGGI_TROTOAR))
    k["logam_abu"].silinder(kaki, 0.07, 3.3, n=10)
    rumah_lampu = Kanvas("Lampu_Lalu_Lintas", kol)
    rumah_lampu["ll_kotak"].kotak(kaki + Vector((-0.18, -0.36, 2.25)), kaki + Vector((0.18, -0.08, 3.35)))
    # Papan latar dan bingkai, keduanya hitam
    v = lambda x, y, z: kaki + Vector((x, y, z))  # noqa: E731
    rumah_lampu["ll_papan"].kotak(v(-0.3, -0.08, 2.12), v(0.3, -0.05, 3.48))
    for a, b in (((-0.3, 2.12), (0.3, 2.17)), ((-0.3, 3.43), (0.3, 3.48)),
                 ((-0.3, 2.12), (-0.25, 3.48)), ((0.25, 2.12), (0.3, 3.48))):
        rumah_lampu["ll_bingkai"].kotak(v(a[0], -0.09, a[1]), v(b[0], -0.08, b[1]))
    # Tudung setengah tabung di atas tiap lensa bulat
    for z in (3.1, 2.8, 2.5):
        _tudung(rumah_lampu["ll_kotak"], v(0, -0.36, z), panjang=0.22)
    # Penyangga ke tiang
    rumah_lampu["logam_abu"].kotak(v(-0.04, -0.08, 2.95), v(0.04, 0.0, 3.0))
    rumah_lampu["logam_abu"].kotak(v(-0.04, -0.08, 2.5), v(0.04, 0.0, 2.55))
    rumah_lampu.selesai()
    # Tiga lensa menghadap -Y (ke kendaraan yang datang). Objek terpisah supaya
    # nanti bisa dianimasikan (merah ke hijau di shot 3).
    for nama, z, bhn in (("LL_Merah", 3.1, "ll_merah_nyala"), ("LL_Kuning", 2.8, "ll_kuning_mati"),
                         ("LL_Hijau", 2.5, "ll_hijau_mati")):
        lensa = Kanvas(nama, kol)
        lensa[bhn].silinder((0, 0, 0), 0.11, 0.04, n=16)
        lensa.selesai()
        obj = lensa.kol.objects[0]
        obj.name = nama
        obj.rotation_euler = (math.pi / 2, 0, 0)
        obj.location = kaki + Vector((0, -0.37, z))
    # Cahaya merah ke aspal basah. Tidak terlihat kamera: bolanya berada di
    # dalam tudung dan tampak sebagai gumpalan putih di depan lensa.
    cahaya = _lampu(k, "LL_Cahaya", kaki + Vector((0, -0.6, 3.1)), (1.0, 0.05, 0.03), 40, jenis="POINT", lunak=0.05)
    cahaya.visible_camera = False
    # Light linking: cahaya ini tidak menerangi tiang, kotak, tudung, dan lensa
    # (jaraknya hanya 23 cm dari tudung sehingga tudung menyala merah berlebihan).
    kecuali = bpy.data.collections.new("LL_Tidak_Disinari")
    for obj in list(kol.all_objects):
        if obj.name.startswith(("LL_Merah", "LL_Kuning", "LL_Hijau", "Lampu_Lalu_Lintas")):
            kecuali.objects.link(obj)
    cahaya.light_linking.receiver_collection = kecuali
    for item in kecuali.collection_objects:
        item.light_linking.link_state = "EXCLUDE"


def _tudung(g, pusat, panjang, r_dalam=0.125, r_luar=0.14, n=14):
    """Tudung lampu: setengah tabung (sedikit lebih dari 180 derajat) menjorok ke -Y."""
    titik = []
    for i in range(n + 1):
        t = math.radians(-12 + (180 + 24) * i / n)
        for r in (r_luar, r_dalam):
            for dy in (0.0, -panjang):
                titik.append(pusat + Vector((r * math.cos(t), dy, r * math.sin(t))))
    muka = []
    for i in range(n):
        a, b = 4 * i, 4 * (i + 1)
        muka += [(a, b, b + 1, a + 1), (a + 2, a + 3, b + 3, b + 2), (a + 1, b + 1, b + 3, a + 3)]
    muka += [(0, 1, 3, 2), (4 * n, 4 * n + 2, 4 * n + 3, 4 * n + 1)]
    g.poly(titik, muka)


# ==========================================================================
# Jalan kecil dengan kali di sisi kanan (shot 2)


def _kali(rng, kota):
    kol = koleksi("Tepi_Kali", kota)
    k = Kanvas("Kali", kol)
    X = KALI_X
    Y0, Y1 = -45.0, 80.0
    yt0, yt1 = 30.0, 34.0  # simpang tiga: jalan berbelok ke kiri

    # Jalan sempit 4 m menuju +Y, berakhir di simpang tiga; cabang ke kiri (-X)
    k["aspal_basah"].kotak((X - 4, Y0, -0.2), (X, yt1, 0))
    k["aspal_basah"].kotak((X - 50, yt0, -0.2), (X - 4, yt1, 0))
    for (x, y), r in [((X - 2.8, 18.0), 1.0), ((X - 1.2, 27.5), 1.4), ((X - 3.0, 31.5), 0.9),
                      ((X - 9.0, 32.0), 1.2)]:
        _genangan(k, rng, (x, y), r)

    # Sisi kiri: bahu tanah, tembok bata, rumah-rumah gelap di belakang
    k["tanah"].kotak((X - 5.7, Y0, -0.2), (X - 4, yt0, 0.02))
    k["bata"].kotak((X - 6.0, Y0, 0), (X - 5.7, yt0 - 0.3, 2.2))
    k["bata"].kotak((X - 50, yt0 - 0.6, 0), (X - 5.7, yt0 - 0.3, 2.2))
    k["bata"].kotak((X - 50, yt1 + 0.3, 0), (X + 0.6, yt1 + 0.6, 2.2))
    k["tanah"].kotak((X - 50, yt1, -0.2), (X + 0.6, yt1 + 0.3, 0.02))
    for f, panjang in ((Bingkai((X - 6.5, Y0, 0), (0, 1, 0), (-1, 0, 0)), yt0 - Y0 - 1),
                       (Bingkai((X - 50, yt1 + 1.0, 0), (1, 0, 0), (0, 1, 0)), 50)):
        a = 0.0
        while a < panjang - 5:
            lebar = rng.uniform(6, 8)
            _rumah(k, rng, f, a, a + lebar, 0.5, 8, kaca_nyala=0.3, lampu_teras=False)
            a += lebar

    # Tepi kali: beton tanpa pagar, rata dengan jalan
    tepi = X + 0.7
    k["beton_kali"].kotak((X, Y0, -3.2), (tepi, Y1, 0.05))
    k["beton_kali"].kotak((tepi, Y0, -3.4), (X + 9.3, Y1, -3.2))  # dasar kali
    air = -0.8  # kali deras dan tinggi karena hujan
    k["air_kali"].poly([(tepi, Y0, air), (X + 9.3, Y0, air), (X + 9.3, Y1, air), (tepi, Y1, air)],
                       [(0, 1, 2, 3)])
    k["beton_kali"].kotak((X + 9.3, Y0, -3.4), (X + 9.7, Y1, 0.4))
    k["tanah"].kotak((X + 9.7, Y0, -0.2), (X + 40, Y1, 0.4))
    # Seberang kali: semak dan rumah dengan beberapa lampu (terpantul di air)
    for _ in range(40):
        x, y = rng.uniform(X + 10, X + 13), rng.uniform(Y0, Y1)
        r = rng.uniform(0.5, 1.3)
        k["daun"].bola((x, y, 0.4 + r * 0.5), (r, r * 1.2, r * 0.8))
    f = Bingkai((X + 14, Y1, 0.4), (0, -1, 0), (1, 0, 0))
    a = 0.0
    while a < Y1 - Y0 - 8:
        lebar = rng.uniform(6, 9)
        _rumah(k, rng, f, a, a + lebar, 0.5, 8, kaca_nyala=0.35, nama=f"Seberang_{int(a)}")
        a += lebar

    # Lampu: satu natrium redup di jalan kecil, satu di cabang kiri
    _lampu_jalan(k, "Natrium_Kali_0", (X - 4.5, 4.0, 0), (1, 0, 0), daya=900)
    # Kerucut lebar: kolam cahaya jatuh di aspal simpang tiga di depan kamera shot 2
    _lampu_jalan(k, "Natrium_Kali_1", (X - 4.5, yt1 + 0.1, 0), (1, -0.3, 0), daya=2600, sudut=115)
    _lampu_jalan(k, "Natrium_Kali_2", (X - 24.0, yt1 + 0.1, 0), (0, -1, 0), daya=900)

    # Kabel dari tiang di sisi kiri ke seberang kali
    pasangan = []
    for y in (-10.0, 22.0):
        kaki = Vector((X - 5.0, y, 0))
        k["tiang_beton"].silinder(kaki, 0.12, 8.5, n=8)
        for dz in (8.2, 7.8):
            pasangan.append((kaki + Vector((0, 0, dz)), Vector((X + 15, y + 6, dz - 1.5)), 0.6))
        pasangan.append((kaki + Vector((0, 0, 8.2)), Vector((X - 5.0, y + 32, 8.2)), 0.5))
    kabel(k, "Kabel_Kali", pasangan, "kabel")

    k.selesai()
    _hujan(kol, "Hujan_Kali", X - 8, X + 12, -2, 46, -0.8, 12000, rng)
    _kabut(kol, "Kabut_Kali", (X - 60, -60, -4), (X + 60, 100, 30), 0.006)


# ==========================================================================
# Gang Melati (shot 4 sampai 8)


def _gang_melati(rng, kota):
    kol = koleksi("Gang_Melati", kota)
    k = Kanvas("Gang", kol)
    X = GANG_X
    gx0, gx1 = X - GANG_LEBAR / 2, X + GANG_LEBAR / 2
    Y0, Y1 = -12.0, 70.0

    # Jalan di mulut gang (Jl. Melati) dan lantai gang
    k["aspal_basah"].kotak((X - 40, Y0 - 8, -0.2), (X + 40, Y0, 0))
    k["paving_gang"].kotak((gx0, Y0, -0.2), (gx1, Y1, 0.05))
    for _ in range(9):
        _genangan(k, rng, (rng.uniform(gx0 + 0.4, gx1 - 0.4), rng.uniform(Y0 + 1, 34)),
                  rng.uniform(0.35, 0.8), z=0.054)

    # Gapura "GANG MELATI"
    for x in (gx0 - 0.4, gx1 + 0.05):
        k["cat_hijau_tembok"].kotak((x, Y0 + 0.6, 0), (x + 0.35, Y0 + 0.95, 3.6))
    k["papan_gapura"].kotak((gx0 - 0.5, Y0 + 0.6, 3.05), (gx1 + 0.5, Y0 + 0.95, 3.65))
    teks(k, "Tulisan_Gapura", "GANG MELATI", (X, Y0 + 0.58, 3.35), (0, -1, 0), 0.38, "huruf_gapura")

    # Sepuluh rumah: nomor ganjil di kiri, genap di kanan
    for sisi, asal_x, n, nomor_awal in ((-1, gx0, (-1, 0, 0), 1), (1, gx1, (1, 0, 0), 2)):
        f = Bingkai((asal_x, Y0 + 1.5, 0.05), (0, 1, 0), n)
        a = 0.0
        for i in range(5):
            lebar = rng.uniform(6.0, 7.5)
            nomor = nomor_awal + 2 * i
            _pagar_hijau(k, rng, f, a, a + lebar, nomor)
            _rumah(k, rng, f, a, a + lebar, rng.uniform(2.2, 3.2), rng.uniform(7, 9), nama=f"No{nomor:02d}")
            # Tembok batas antar kavling
            f.kotak(k["bata"], a, a + 0.12, 0.2, 12, 0, 1.8)
            a += lebar
        f.kotak(k["bata"], a, a + 0.12, 0.2, 12, 0, 1.8)
        # Ujung gang: tembok bata tinggi sampai Y1
        f.kotak(k["bata"], a, Y1 - Y0 - 1.5, 0, 0.25, 0, 2.6)
    k["bata"].kotak((gx0, Y1 - 0.25, 0), (gx1, Y1, 2.6))

    # Lampu dinding redup di gang dan kabel melintang
    for i, y in enumerate((3.0, 24.0)):
        s = 1 if i % 2 else -1
        x = X + s * (GANG_LEBAR / 2 + 0.1)
        k["logam_gelap"].silinder((x, y, 0.05), 0.06, 5.5, n=8)
        kepala = Vector((x - s * 0.6, y, 5.3))
        k["lampu_natrium"].kotak(kepala - Vector((0.2, 0.08, 0.03)), kepala + Vector((0.2, 0.08, 0.02)))
        k["logam_gelap"].kotak(Vector((min(x, kepala.x), y - 0.04, 5.35)), Vector((max(x, kepala.x), y + 0.04, 5.42)))
        _lampu(k, f"Natrium_Gang_{i}", kepala - Vector((0, 0, 0.08)), bahan.NATRIUM, 450, sudut=110, tepi=0.35)
    pasangan = []
    for y in range(int(Y0) + 4, 34, 7):
        z = rng.uniform(5.0, 6.0)
        pasangan.append(((gx0 - 2.5, y, z), (gx1 + 2.5, y + rng.uniform(-2, 2), z - 0.3), rng.uniform(0.2, 0.5)))
    kabel(k, "Kabel_Gang", pasangan, "kabel")

    k.selesai()
    _hujan(kol, "Hujan_Gang", gx0 - 6, gx1 + 6, Y0 - 6, 36, 0.0, 12000, rng)
    _kabut(kol, "Kabut_Gang", (X - 50, Y0 - 30, -1), (X + 50, Y1 + 20, 25), 0.006)


def _pagar_hijau(k, rng, f, a0, a1, nomor):
    """Pagar besi hijau di atas dinding rendah hijau, gerbang, dan nomor rumah."""
    b0, b1 = 0.0, 0.2
    gerbang0 = a0 + rng.uniform(0.25, 0.45) * (a1 - a0)
    gerbang1 = gerbang0 + 2.4
    tiang = [a0 + 0.05, gerbang0 - 0.3, gerbang1, a1 - 0.35]
    for a in tiang:
        f.kotak(k["cat_hijau_tembok"], a, a + 0.3, b0 - 0.05, b1 + 0.05, 0, 1.6)
        f.kotak(k["beton"], a - 0.03, a + 0.33, b0 - 0.08, b1 + 0.08, 1.6, 1.68)
    for s0, s1 in ((a0 + 0.35, gerbang0 - 0.3), (gerbang1 + 0.3, a1 - 0.35)):
        f.kotak(k["cat_hijau_tembok"], s0, s1, b0, b1, 0, 0.45)
        f.kotak(k["cat_hijau"], s0, s1, 0.08, 0.12, 1.32, 1.37)
        a = s0 + 0.08
        while a < s1 - 0.05:
            f.kotak(k["cat_hijau"], a, a + 0.025, 0.088, 0.112, 0.45, 1.4)
            a += 0.12
    # Gerbang besi
    f.kotak(k["cat_hijau"], gerbang0, gerbang1, 0.08, 0.12, 0.05, 0.12)
    f.kotak(k["cat_hijau"], gerbang0, gerbang1, 0.08, 0.12, 1.35, 1.42)
    a = gerbang0 + 0.05
    while a < gerbang1 - 0.05:
        f.kotak(k["cat_hijau"], a, a + 0.025, 0.088, 0.112, 0.05, 1.42)
        a += 0.1
    # Halaman
    f.kotak(k["beton"], a0, a1, b1, 3.4, -0.05, 0.08)

    # Nomor rumah pada tiang pertama
    ap = tiang[0] + 0.15
    f.kotak(k["plat_nomor"], ap - 0.14, ap + 0.14, b0 - 0.08, b0 - 0.05, 1.12, 1.32)
    teks(k, f"Nomor_{nomor:02d}", str(nomor), f.titik(ap, b0 - 0.085, 1.22), f.muka, 0.15, "huruf_nomor")
    # Tanaman yang sebagian menutupi nomor: semak dari bawah atau sulur dari atas
    gaya = rng.choice(("semak", "semak", "sulur", "sulur", "sedikit"))
    if gaya == "semak":
        for _ in range(9):
            pa = ap + rng.uniform(-0.45, 0.15)
            pc = rng.uniform(0.5, 1.2)
            r = rng.uniform(0.18, 0.32)
            k["daun"].bola(f.titik(pa, b0 - 0.3 - rng.uniform(0, 0.2), pc), (r, r, r * 0.9))
    elif gaya == "sulur":
        for _ in range(12):
            pa = ap + rng.uniform(-0.05, 0.35)
            pc = rng.uniform(1.18, 1.75)
            r = rng.uniform(0.07, 0.14)
            k["daun"].bola(f.titik(pa, b0 - 0.12, pc), (r, r, r * 1.6))
    else:
        for _ in range(4):
            r = rng.uniform(0.1, 0.18)
            k["daun"].bola(f.titik(ap + rng.uniform(0.12, 0.3), b0 - 0.15, rng.uniform(1.0, 1.3)), (r, r, r))
    # Pot tanaman di atas dinding pagar
    for _ in range(rng.randint(1, 3)):
        a = rng.uniform(a0 + 0.6, a1 - 0.6)
        if gerbang0 - 0.4 < a < gerbang1 + 0.4:
            continue
        f.kotak(k["pot"], a - 0.12, a + 0.12, 0.02, 0.18, 1.45, 1.7)
        k["daun"].bola(f.titik(a, 0.1, 1.85), (0.25, 0.25, 0.22))
