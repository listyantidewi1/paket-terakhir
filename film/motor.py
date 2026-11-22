"""Motor bebek biru Mas Adit, dengan boks paket oranye dan satu paket berlabel.

Dipakai bersama dengan game Kurir Senja, jadi aturannya tetap:
    satuan meter, titik pusat (objek "Motor") di tanah di tengah antara
    kedua titik sentuh roda, depan menghadap +Y, kanan +X, atas +Z.

Susunan objek:
    Motor                      empty akar; properti "jarak_tempuh" (meter)
      Motor_<bahan>            badan, mesin, jok, boks, rak
      Motor_Kemudi             empty di kepala rangka (nanti untuk berbelok)
        Motor_Kemudi_<bahan>   setang, garpu, batok, spion, spakbor depan
        Motor_Lampu_Depan      lampu sorot (spot) ke depan
        Motor_Roda_Depan       empty di as roda depan, berputar
      Motor_Roda_Belakang      empty di as roda belakang, berputar
      Motor_Boks_Tutup         tutup boks, titik putar di engsel belakang
      Paket                    paket kardus berlabel di dalam boks

Roda tidak tergelincir: sudut roda (radian, sumbu X) = -jarak_tempuh / JARI_RODA,
artinya jumlah putaran = jarak / keliling roda. Pakai animasi_jalan() untuk
menggerakkan motor; fungsi itu mengisi jarak_tempuh dari lintasan sebenarnya.
"""

import math

import bpy
from mathutils import Vector

from . import bahan
from .geo import Gabung, HALUS

JARI_RODA = 0.29  # ban 70/90-17 dan 80/90-17: diameter luar sekitar 0,58 m
KELILING_RODA = 2 * math.pi * JARI_RODA
JARAK_SUMBU = 1.24  # jarak as depan ke as belakang
Y_DEPAN, Y_BELAKANG = JARAK_SUMBU / 2, -JARAK_SUMBU / 2
KEPALA = Vector((0.0, 0.40, 0.86))  # kepala rangka, titik putar kemudi
PLAT = "XX 0000 XX"  # bukan nomor sungguhan
LABEL = ("Penerima: Ayah", "Gg. Melati, Kota Senja")


def _bahan():
    if "motor_cat_biru" in bpy.data.materials:
        return
    b = bahan.polos("motor_cat_biru", (0.015, 0.09, 0.42), kasar=0.28, logam=0.35)
    bsdf = b.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.04
    bahan.polos("motor_plastik_hitam", (0.02, 0.02, 0.022), kasar=0.45)
    bahan.polos("motor_karet", (0.015, 0.015, 0.015), kasar=0.75)
    bahan.polos("motor_krom", (0.8, 0.8, 0.82), kasar=0.08, logam=1.0)
    bahan.polos("motor_velg", (0.12, 0.12, 0.13), kasar=0.3, logam=0.8)
    bahan.polos("motor_mesin", (0.3, 0.3, 0.31), kasar=0.45, logam=0.7)
    bahan.polos("motor_jok", (0.025, 0.022, 0.02), kasar=0.35)
    bahan.polos("motor_lampu_depan", (0.8, 0.8, 0.8), kasar=0.05, emisi=(1.0, 0.92, 0.8), kuat=6.0)
    bahan.polos("motor_lampu_belakang", (0.3, 0.0, 0.0), kasar=0.1, emisi=(1.0, 0.02, 0.01), kuat=6.0)
    bahan.polos("motor_sein", (0.6, 0.35, 0.05), kasar=0.1)
    bahan.polos("motor_cermin", (0.9, 0.9, 0.9), kasar=0.02, logam=1.0)
    bahan.polos("motor_plat", (0.85, 0.85, 0.83), kasar=0.4)
    bahan.polos("motor_huruf_plat", (0.01, 0.01, 0.01), kasar=0.5)
    bahan.polos("boks_oranye", (0.9, 0.28, 0.02), kasar=0.35)
    # Strip pemantul: sangat terang di bawah cahaya, sedikit berpendar
    # (pantulan balik ke arah kamera tidak bisa dihitung langsung oleh Cycles)
    bahan.polos("strip_pemantul", (0.85, 0.85, 0.8), kasar=0.12, logam=0.6, emisi=(1.0, 1.0, 0.95), kuat=0.25)
    bahan.polos("kardus", (0.36, 0.23, 0.12), kasar=0.85)
    bahan.polos("lakban", (0.55, 0.45, 0.3), kasar=0.3)
    bahan.polos("kertas_label", (0.88, 0.88, 0.84), kasar=0.7)


# --------------------------------------------------------------------------
# Bentuk dasar (koordinat motor; dikonversi ke koordinat induk saat dibuat)


def _cincin_x(g, pusat, R, a, b, n=40, m=10):
    """Torus mengelilingi sumbu X (ban, bibir velg). a: setengah lebar, b: setengah tebal."""
    c = Vector(pusat)
    v = []
    for i in range(n):
        t = 2 * math.pi * i / n
        for j in range(m):
            s = 2 * math.pi * j / m
            r = R + b * math.cos(s)
            v.append(c + Vector((a * math.sin(s), r * math.cos(t), r * math.sin(t))))
    muka = [(i * m + j, i * m + (j + 1) % m, ((i + 1) % n) * m + (j + 1) % m, ((i + 1) % n) * m + j)
            for i in range(n) for j in range(m)]
    g.poly(v, muka)


def _roda(gs, as_roda, depan):
    """Ban, velg palang lima, tromol/cakram. gs: dict bahan -> Gabung."""
    c = Vector(as_roda)
    lebar_ban = 0.027 if depan else 0.031  # ban ramping khas bebek
    _cincin_x(gs["motor_karet"], c, JARI_RODA - 0.034, lebar_ban, 0.034, n=64, m=14)
    _cincin_x(gs["motor_velg"], c, 0.215, 0.028, 0.01, n=40, m=6)
    for i in range(5):
        t = 2 * math.pi * i / 5 + 0.3
        arah = Vector((0, math.cos(t), math.sin(t)))
        gs["motor_velg"].batang(c + arah * 0.05, c + arah * 0.208, 0.026)
    gs["motor_velg"].tabung(c + Vector((-0.065, 0, 0)), c + Vector((0.065, 0, 0)), 0.05, n=16)
    if depan:
        gs["motor_krom"].tabung(c + Vector((-0.075, 0, 0)), c + Vector((-0.07, 0, 0)), 0.11, n=24)
    else:
        gs["motor_mesin"].tabung(c + Vector((-0.07, 0, 0)), c + Vector((0.07, 0, 0)), 0.075, n=20)


# --------------------------------------------------------------------------


def _jadikan(gs, nama, induk, asal, kol, tumpul=0.0):
    """Buat satu objek per bahan, titik-titiknya relatif terhadap `asal` (koordinat motor)."""
    asal = Vector(asal)
    hasil = []
    for nama_bahan, g in gs.items():
        if not g.f:
            continue
        mesh = bpy.data.meshes.new(f"{nama}_{nama_bahan}")
        mesh.from_pydata([tuple(Vector(p) - asal) for p in g.v], [], g.f)
        mesh.validate()
        mesh.materials.append(bpy.data.materials[nama_bahan])
        if nama_bahan in HALUS or nama_bahan in ("motor_karet", "motor_velg"):
            mesh.shade_smooth()
        obj = bpy.data.objects.new(f"{nama}_{nama_bahan}", mesh)
        kol.objects.link(obj)
        obj.parent = induk
        if tumpul and nama_bahan not in ("motor_karet",):
            mod = obj.modifiers.new("Tumpul", "BEVEL")
            mod.width = tumpul
            mod.segments = 3
            mod.limit_method = "ANGLE"
        hasil.append(obj)
    return hasil


def _empty(nama, induk, lokasi, kol):
    obj = bpy.data.objects.new(nama, None)
    obj.empty_display_size = 0.15
    kol.objects.link(obj)
    obj.parent = induk
    obj.location = lokasi
    return obj


def _teks_datar(nama, isi, induk, lokasi, rotasi, ukuran, nama_bahan, kol):
    kurva = bpy.data.curves.new(nama, type="FONT")
    kurva.body = isi
    kurva.align_x = "CENTER"
    kurva.align_y = "CENTER"
    kurva.size = ukuran
    kurva.extrude = 0.0005
    kurva.materials.append(bpy.data.materials[nama_bahan])
    obj = bpy.data.objects.new(nama, kurva)
    kol.objects.link(obj)
    obj.parent = induk
    obj.location = lokasi
    obj.rotation_euler = rotasi
    return obj


def _gabungan(*nama):
    return {n: Gabung() for n in nama}


def buat_motor(kol, nama="Motor"):
    """Bangun motor di titik asal dunia. Kembalikan empty akar `nama`."""
    _bahan()
    akar = bpy.data.objects.new(nama, None)
    akar.empty_display_type = "ARROWS"
    akar.empty_display_size = 0.5
    kol.objects.link(akar)
    akar["jarak_tempuh"] = 0.0
    akar["jari_roda"] = JARI_RODA
    akar["kecepatan"] = 0.0  # m/s, diisi animasi_jalan; menggerakkan angin untuk ponco
    _angin(kol, akar)

    _badan(kol, akar)
    kemudi = _empty("Motor_Kemudi", akar, KEPALA, kol)
    _kemudi(kol, kemudi)
    roda_depan = _empty("Motor_Roda_Depan", kemudi, Vector((0, Y_DEPAN, JARI_RODA)) - KEPALA, kol)
    roda_belakang = _empty("Motor_Roda_Belakang", akar, (0, Y_BELAKANG, JARI_RODA), kol)
    for pivot, depan in ((roda_depan, True), (roda_belakang, False)):
        gs = _gabungan("motor_karet", "motor_velg", "motor_krom", "motor_mesin")
        _roda(gs, (0, 0, 0), depan)
        _jadikan(gs, pivot.name, pivot, (0, 0, 0), kol)
        _pasang_driver_roda(pivot, akar)
    _boks_dan_paket(kol, akar)
    return akar


def _angin(kol, akar):
    """Angin laju: bertiup dari depan ke belakang motor, kuat sebanding kecepatan kuadrat."""
    # Medan gaya hanya bisa dibuat lewat operator; lalu dipindah ke koleksi motor
    bpy.ops.object.effector_add(type="WIND")
    angin = bpy.context.object
    angin.name = "Motor_Angin"
    for k in list(angin.users_collection):
        k.objects.unlink(angin)
    kol.objects.link(angin)
    angin.parent = akar
    angin.location = (0, 1.2, 1.0)
    angin.rotation_euler = (math.radians(90), 0, 0)  # sumbu +Z angin menunjuk ke -Y (belakang)
    angin.field.type = "WIND"
    angin.field.flow = 0.5
    angin.field.noise = 1.0
    angin.field.seed = 7
    fc = angin.field.driver_add("strength")
    var = fc.driver.variables.new()
    var.name, var.type = "v", "SINGLE_PROP"
    var.targets[0].id = akar
    var.targets[0].data_path = '["kecepatan"]'
    fc.driver.expression = "v * v * 1.2"


def _pasang_driver_roda(roda, akar):
    fc = roda.driver_add("rotation_euler", 0)
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "jarak"
    var.type = "SINGLE_PROP"
    var.targets[0].id = akar
    var.targets[0].data_path = '["jarak_tempuh"]'
    # Ekspresi sederhana (tanpa Python): sudut = -jarak / jari-jari
    drv.expression = f"-jarak / {JARI_RODA}"


def _jadikan_halus(gs, nama, induk, asal, kol, tumpul=0.0, subdiv=1, tebal=0.0):
    """Seperti _jadikan, ditambah modifier supaya tepi halus.

    Urutan: Solidify (panel tipis) -> Bevel (tepi membulat) -> Subdivision.
    """
    hasil = _jadikan(gs, nama, induk, asal, kol)
    for obj in hasil:
        obj.data.shade_smooth()
        if tebal:
            sol = obj.modifiers.new("Tebal", "SOLIDIFY")
            sol.thickness = tebal
            sol.offset = -1
        if tumpul:
            bev = obj.modifiers.new("Tumpul", "BEVEL")
            bev.width = tumpul
            bev.segments = 3
            bev.limit_method = "ANGLE"
        if subdiv:
            sub = obj.modifiers.new("Halus", "SUBSURF")
            sub.levels = subdiv
            sub.render_levels = subdiv
    return hasil


def _kotak_runcing(g, depan, belakang):
    """Kotak yang mengecil: depan/belakang = (y, setengah_lebar, z_bawah, z_atas)."""
    (yd, ld, zd0, zd1), (yb, lb, zb0, zb1) = depan, belakang
    g.poly([(-lb, yb, zb0), (lb, yb, zb0), (lb, yb, zb1), (-lb, yb, zb1),
            (-ld, yd, zd0), (ld, yd, zd0), (ld, yd, zd1), (-ld, yd, zd1)],
           [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])


def _permukaan(g, titik_fn, nu, nv):
    """Lembaran grid; titik_fn(u, v) dengan u, v dari 0 ke 1."""
    v = [titik_fn(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)]
    m = nu + 1
    g.poly(v, [(j * m + i, j * m + i + 1, (j + 1) * m + i + 1, (j + 1) * m + i)
               for j in range(nv) for i in range(nu)])


def _sayap(g, as_roda, r, lebar, t0, t1, n=18):
    """Spakbor melengkung: membusur di atas roda, penampangnya cembung dan
    tepinya melipat turun membungkus ban."""
    c = Vector(as_roda)

    def titik(u, v):
        t = math.radians(t0 + (t1 - t0) * v)
        x = (u * 2 - 1) * lebar
        q = x / lebar
        rr = r + 0.022 * (1 - q * q) - 0.03 * q ** 4
        return c + Vector((x * (1 - 0.15 * q * q), rr * math.cos(t), rr * math.sin(t)))
    _permukaan(g, titik, 6, n)


def _kerucut(g, p0, p1, r0, r1, n=20):
    p0, p1 = Vector(p0), Vector(p1)
    sumbu = (p1 - p0).normalized()
    bantu = Vector((0, 0, 1)) if abs(sumbu.z) < 0.9 else Vector((1, 0, 0))
    u = sumbu.cross(bantu).normalized()
    w = sumbu.cross(u).normalized()
    ring = [u * math.cos(2 * math.pi * i / n) + w * math.sin(2 * math.pi * i / n) for i in range(n)]
    muka = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    muka += [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    g.poly([p0 + q * r0 for q in ring] + [p1 + q * r1 for q in ring], muka)


def _pipa(g, titik, r, n=16):
    """Pipa bersambung lewat beberapa titik (leher knalpot)."""
    for a, b in zip(titik, titik[1:]):
        g.tabung(a, b, r, n=n)


def _badan(kol, akar):
    # Bodi belakang di bawah jok: membulat, menyempit dan naik ke belakang
    gs = _gabungan("motor_cat_biru")
    _kotak_runcing(gs["motor_cat_biru"], (-0.02, 0.16, 0.47, 0.79), (-0.87, 0.105, 0.6, 0.8))
    _jadikan_halus(gs, "Motor_Bodi_Belakang", akar, (0, 0, 0), kol, tumpul=0.06, subdiv=2)
    # Dek tengah (terowongan rangka di antara kaki), menyambung tameng ke bodi
    gs = _gabungan("motor_cat_biru")
    _kotak_runcing(gs["motor_cat_biru"], (0.31, 0.085, 0.34, 0.55), (-0.06, 0.12, 0.34, 0.6))
    _jadikan_halus(gs, "Motor_Dek", akar, (0, 0, 0), kol, tumpul=0.05, subdiv=2)

    # Pelindung kaki: lembaran melengkung di depan lutut, membungkus ke samping
    gs = _gabungan("motor_cat_biru")

    def tameng(u, v):
        x = (u * 2 - 1) * 0.22
        q = x / 0.22
        z = 0.3 + 0.56 * v
        y = 0.31 + 0.05 * (1 - q * q) - 0.06 * v - 0.05 * q ** 4
        return (x * (1 - 0.12 * v), y, z)
    _permukaan(gs["motor_cat_biru"], tameng, 8, 6)
    _jadikan_halus(gs, "Motor_Tameng", akar, (0, 0, 0), kol, subdiv=2, tebal=0.025)
    # Penutup depan (hidung) di depan kepala rangka
    gs = _gabungan("motor_cat_biru")
    _kotak_runcing(gs["motor_cat_biru"], (0.47, 0.085, 0.52, 0.86), (0.31, 0.115, 0.5, 0.86))
    _jadikan_halus(gs, "Motor_Hidung", akar, (0, 0, 0), kol, tumpul=0.05, subdiv=2)

    # Jok panjang empuk: sedikit lebih lebar di belakang, tepi membulat
    gs = _gabungan("motor_jok")
    _kotak_runcing(gs["motor_jok"], (0.05, 0.12, 0.78, 0.865), (-0.81, 0.14, 0.78, 0.875))
    _jadikan_halus(gs, "Motor_Jok", akar, (0, 0, 0), kol, tumpul=0.045, subdiv=2)

    # Spakbor belakang
    gs = _gabungan("motor_plastik_hitam")
    _sayap(gs["motor_plastik_hitam"], (0, Y_BELAKANG, JARI_RODA), 0.33, 0.07, 95, 200)
    _jadikan_halus(gs, "Motor_Spakbor_Belakang", akar, (0, 0, 0), kol, subdiv=2, tebal=0.005)

    # Bagian lain: mesin, lengan ayun, knalpot, pijakan, lampu, plat, rak
    gs = _gabungan("motor_plastik_hitam", "motor_mesin", "motor_krom", "motor_lampu_belakang",
                   "motor_sein", "motor_plat", "motor_karet")
    hitam, mesin, krom = gs["motor_plastik_hitam"], gs["motor_mesin"], gs["motor_krom"]
    gs["motor_lampu_belakang"].kotak((-0.09, -0.895, 0.69), (0.09, -0.86, 0.77))
    for x in (-0.13, 0.11):
        gs["motor_sein"].kotak((x, -0.9, 0.7), (x + 0.02, -0.87, 0.74))
    hitam.kotak((-0.03, -0.98, 0.5), (0.03, -0.86, 0.66))
    gs["motor_plat"].kotak((-0.12, -1.005, 0.42), (0.12, -0.995, 0.535))
    # Mesin bebek: silinder mendatar ke depan, bak mesin, sirip pendingin
    mesin.kotak((-0.14, -0.18, 0.18), (0.14, 0.14, 0.42))
    mesin.kotak((-0.08, 0.1, 0.2), (0.08, 0.3, 0.34))
    for i in range(5):
        y = 0.13 + i * 0.035
        mesin.kotak((-0.1, y, 0.19), (0.1, y + 0.012, 0.35))
    # Knalpot di kanan bawah: leher turun dari kepala silinder, lewat bawah
    # mesin ke kanan, lalu peredam yang membesar ke belakang dan ujung krom
    _pipa(krom, [(0.03, 0.3, 0.24), (0.05, 0.31, 0.16), (0.12, 0.2, 0.12), (0.17, 0.0, 0.16),
                 (0.185, -0.17, 0.25)], 0.021)
    _kerucut(hitam, (0.185, -0.17, 0.25), (0.2, -0.72, 0.35), 0.042, 0.056)
    _kerucut(krom, (0.2, -0.72, 0.35), (0.2, -0.8, 0.365), 0.05, 0.026)
    _kerucut(hitam, (0.197, -0.26, 0.27), (0.21, -0.55, 0.32), 0.058, 0.062, n=20)  # pelindung panas
    # Lengan ayun, sokbreker belakang, tutup rantai
    for x in (-0.1, 0.1):
        mesin.batang((x, -0.12, 0.33), (x, Y_BELAKANG, JARI_RODA), 0.04)
        krom.tabung((x * 1.3, -0.56, 0.33), (x * 1.4, -0.7, 0.72), 0.022)
        hitam.tabung((x * 1.3, -0.58, 0.38), (x * 1.38, -0.68, 0.62), 0.034)
    hitam.kotak((-0.17, -0.62, 0.25), (-0.13, -0.05, 0.36))
    # Pijakan kaki: bulat berkaret, dengan dudukan logam
    for y, z, panjang in ((0.06, 0.29, 0.17), (-0.42, 0.33, 0.12)):
        for s in (-1, 1):
            x0 = s * (0.15 if y > 0 else 0.17)
            mesin.tabung((s * 0.1, y, z), (x0, y, z), 0.014)
            gs["motor_karet"].tabung((x0, y, z), (x0 + s * panjang, y, z), 0.019, n=12)
    # Rak belakang di atas jok (dudukan boks)
    hitam.kotak((-0.19, -0.97, 0.87), (0.19, -0.5, 0.89))
    for y in (-0.95, -0.55):
        hitam.batang((-0.17, y, 0.88), (-0.15, y, 0.74), 0.025)
        hitam.batang((0.17, y, 0.88), (0.15, y, 0.74), 0.025)
    _jadikan(gs, "Motor", akar, (0, 0, 0), kol, tumpul=0.006)
    for obj in akar.children:
        if obj.type == "MESH" and obj.name.endswith(("_motor_krom", "_motor_karet", "_motor_plastik_hitam")):
            obj.data.shade_smooth()

    # Tulisan plat dan lampu belakang
    _teks_datar("Motor_Plat_Belakang_Teks", PLAT, akar, (0, -1.006, 0.478),
                (math.pi / 2, 0, 0), 0.05, "motor_huruf_plat", kol)  # menghadap -Y
    data = bpy.data.lights.new("Motor_Lampu_Belakang", type="POINT")
    data.color = (1.0, 0.03, 0.02)
    data.energy = 3.0
    data.shadow_soft_size = 0.03
    lampu = bpy.data.objects.new("Motor_Lampu_Belakang", data)
    kol.objects.link(lampu)
    lampu.parent = akar
    lampu.location = (0, -0.93, 0.73)
    lampu.visible_camera = False


def _kemudi(kol, kemudi):
    # Batok kepala: membulat, lampu depan di mukanya
    gs = _gabungan("motor_cat_biru")
    _kotak_runcing(gs["motor_cat_biru"], (0.535, 0.15, 0.885, 0.99), (0.34, 0.175, 0.875, 1.0))
    _jadikan_halus(gs, "Motor_Kemudi_Batok", kemudi, KEPALA, kol, tumpul=0.045, subdiv=2)
    # Sayap depan: melengkung menutupi bagian atas roda depan
    gs = _gabungan("motor_cat_biru")
    _sayap(gs["motor_cat_biru"], (0, Y_DEPAN, JARI_RODA), 0.33, 0.068, 35, 160)  # tidak melewati ujung ban
    _jadikan_halus(gs, "Motor_Kemudi_Sayap", kemudi, KEPALA, kol, subdiv=2, tebal=0.006)

    gs = _gabungan("motor_plastik_hitam", "motor_krom", "motor_karet",
                   "motor_lampu_depan", "motor_cermin", "motor_sein", "motor_plat")
    hitam, krom = gs["motor_plastik_hitam"], gs["motor_krom"]
    # Garpu depan: tabung krom atas, pelindung hitam bawah, menuju as depan
    for x in (-0.075, 0.075):
        atas, bawah = Vector((x, 0.41, 0.84)), Vector((x, Y_DEPAN, JARI_RODA))
        krom.tabung(atas, atas.lerp(bawah, 0.55), 0.018, n=14)
        hitam.tabung(atas.lerp(bawah, 0.5), bawah, 0.026, n=14)
    gs["motor_lampu_depan"].kotak((-0.105, 0.52, 0.9), (0.105, 0.546, 0.972))
    hitam.kotak((-0.1, 0.37, 0.995), (0.1, 0.45, 1.03))
    for x in (-0.19, 0.15):
        gs["motor_sein"].kotak((x, 0.47, 0.92), (x + 0.04, 0.53, 0.95))
    # Setang, karet pegangan, tuas rem, spion
    krom.tabung((-0.33, 0.4, 0.99), (0.33, 0.4, 0.99), 0.012, n=12)
    for s in (-1, 1):
        gs["motor_karet"].tabung((s * 0.21, 0.4, 0.99), (s * 0.34, 0.4, 0.99), 0.017, n=14)
        hitam.batang((s * 0.18, 0.43, 1.0), (s * 0.3, 0.47, 0.99), 0.012)
        hitam.tabung((s * 0.2, 0.42, 1.0), (s * 0.27, 0.38, 1.22), 0.007)
        hitam.kotak((s * 0.27 - 0.07, 0.37, 1.18), (s * 0.27 + 0.07, 0.4, 1.27))
        gs["motor_cermin"].kotak((s * 0.27 - 0.06, 0.365, 1.19), (s * 0.27 + 0.06, 0.371, 1.26))
    # Plat nomor depan di sayap
    gs["motor_plat"].kotak((-0.12, 0.69, 0.46), (0.12, 0.7, 0.575))
    _jadikan(gs, "Motor_Kemudi", kemudi, KEPALA, kol, tumpul=0.006)
    for obj in kemudi.children:
        if obj.type == "MESH" and obj.name.endswith(("_motor_krom", "_motor_karet", "_motor_plastik_hitam")):
            obj.data.shade_smooth()
    _teks_datar("Motor_Plat_Depan_Teks", PLAT, kemudi, Vector((0, 0.701, 0.518)) - KEPALA,
                (math.pi / 2, 0, math.pi), 0.05, "motor_huruf_plat", kol)  # menghadap +Y

    # Lampu sorot depan: menghadap +Y, sedikit menunduk
    data = bpy.data.lights.new("Motor_Lampu_Depan", type="SPOT")
    data.color = (1.0, 0.93, 0.82)
    data.energy = 400.0
    data.spot_size = math.radians(45)
    data.spot_blend = 0.5
    data.shadow_soft_size = 0.05
    lampu = bpy.data.objects.new("Motor_Lampu_Depan", data)
    kol.objects.link(lampu)
    lampu.parent = kemudi
    lampu.location = Vector((0, 0.55, 0.94)) - KEPALA
    lampu.rotation_euler = (math.radians(84), 0, 0)  # -Z lampu diarahkan ke +Y, turun 6 derajat
    lampu.visible_camera = False


def _boks_dan_paket(kol, akar):
    """Boks oranye berdinding (terbuka di atas) dengan tutup berengsel, dan paketnya."""
    x0, x1, y0, y1, z0, z1 = -0.22, 0.22, -0.97, -0.52, 0.89, 1.3
    t = 0.015
    gs = _gabungan("boks_oranye", "strip_pemantul")
    o = gs["boks_oranye"]
    o.kotak((x0, y0, z0), (x1, y1, z0 + t))
    o.kotak((x0, y0, z0), (x0 + t, y1, z1))
    o.kotak((x1 - t, y0, z0), (x1, y1, z1))
    o.kotak((x0, y0, z0), (x1, y0 + t, z1))
    o.kotak((x0, y1 - t, z0), (x1, y1, z1))
    p = gs["strip_pemantul"]
    for z in (0.97, 1.2):  # dua strip di tiap sisi dan belakang
        p.kotak((x0 - 0.002, y0 + 0.02, z), (x0, y1 - 0.02, z + 0.035))
        p.kotak((x1, y0 + 0.02, z), (x1 + 0.002, y1 - 0.02, z + 0.035))
        p.kotak((x0 + 0.02, y0 - 0.002, z), (x1 - 0.02, y0, z + 0.035))
    _jadikan(gs, "Motor_Boks", akar, (0, 0, 0), kol, tumpul=0.006)

    # Tutup: titik putar di engsel belakang-atas, supaya bisa dibuka (putar sumbu X)
    engsel = Vector((0, y0, z1))
    gs = _gabungan("boks_oranye", "strip_pemantul")
    gs["boks_oranye"].kotak((x0 - 0.008, y0 - 0.008, z1), (x1 + 0.008, y1 + 0.008, z1 + 0.035))
    gs["strip_pemantul"].kotak((x0 + 0.02, y1 + 0.008, z1 + 0.008), (x1 - 0.02, y1 + 0.01, z1 + 0.027))
    tutup = _empty("Motor_Boks_Tutup", akar, engsel, kol)
    _jadikan(gs, "Motor_Boks_Tutup", tutup, engsel, kol, tumpul=0.006)

    # Paket kardus berlakban, label kertas di atas. Titik pusat di dasar paket.
    dasar = Vector((0, -0.745, z0 + t))
    pk = bpy.data.objects.new("Paket", None)
    pk.empty_display_size = 0.1
    kol.objects.link(pk)
    pk.parent = akar
    pk.location = dasar
    gs = _gabungan("kardus", "lakban", "kertas_label")
    gs["kardus"].kotak(dasar + Vector((-0.15, -0.13, 0)), dasar + Vector((0.15, 0.13, 0.16)))
    gs["lakban"].kotak(dasar + Vector((-0.151, -0.025, 0.0)), dasar + Vector((0.151, 0.025, 0.1605)))
    gs["kertas_label"].kotak(dasar + Vector((-0.12, -0.11, 0.1605)), dasar + Vector((0.02, -0.03, 0.1615)))
    _jadikan(gs, "Paket", pk, dasar, kol)
    for i, (isi, ukuran) in enumerate(zip(LABEL, (0.018, 0.011))):
        _teks_datar(f"Paket_Label_{i}", isi, pk, (-0.05, -0.055 - 0.028 * i, 0.162), (0, 0, 0),
                    ukuran, "motor_huruf_plat", kol)


# --------------------------------------------------------------------------


def taruh(motor, lokasi, arah_derajat=0.0):
    """Letakkan motor diam. arah_derajat: 0 = menghadap +Y, positif = belok kiri."""
    motor.location = lokasi
    motor.rotation_euler = (0, 0, math.radians(arah_derajat))


def animasi_jalan(motor, kunci, halus=True, permukaan=None):
    """Gerakkan motor lewat titik kunci, dan isi jarak_tempuh frame demi frame.

    kunci: daftar (frame, (x, y, z), arah_derajat), frame naik.
    halus: True = percepat/perlambat (smoothstep) di antara kunci,
           False = kecepatan tetap (linear).
    permukaan: fungsi (x, y) -> tinggi jalan (polisi tidur). Bila ada, motor
           naik dan mengangguk mengikuti tinggi di bawah roda depan dan belakang.
    Jarak dijumlahkan dari perpindahan nyata tiap frame, jadi putaran roda
    selalu cocok dengan jalannya motor.

    Mengembalikan daftar (frame, lokasi, arah_derajat) per frame.
    """
    jarak = 0.0
    sebelum = None
    jalur = []
    for (f0, p0, a0), (f1, p1, a1) in zip(kunci, kunci[1:]):
        p0, p1 = Vector(p0), Vector(p1)
        for f in range(int(f0), int(f1) + 1):
            if sebelum is not None and f == sebelum[0]:
                continue
            t = (f - f0) / (f1 - f0)
            if halus:
                t = t * t * (3 - 2 * t)
            p = p0.lerp(p1, t)
            arah = math.radians(a0 + (a1 - a0) * t)
            angguk = 0.0
            if permukaan is not None:
                maju = Vector((-math.sin(arah), math.cos(arah), 0))
                depan, belakang = p + maju * Y_DEPAN, p + maju * Y_BELAKANG
                h_depan, h_belakang = permukaan(depan.x, depan.y), permukaan(belakang.x, belakang.y)
                p = p + Vector((0, 0, (h_depan + h_belakang) / 2))
                angguk = math.atan2(h_depan - h_belakang, JARAK_SUMBU)
            langkah = (p - sebelum[1]).length if sebelum is not None else 0.0
            jarak += langkah
            motor["kecepatan"] = langkah * bpy.context.scene.render.fps
            motor.keyframe_insert('["kecepatan"]', frame=f)
            motor.location = p
            motor.rotation_euler = (angguk, 0, arah)
            motor["jarak_tempuh"] = jarak
            motor.keyframe_insert("location", frame=f)
            motor.keyframe_insert("rotation_euler", frame=f)
            motor.keyframe_insert('["jarak_tempuh"]', frame=f)
            sebelum = (f, p)
            jalur.append((f, p.copy(), math.degrees(arah)))
    # Di antara frame bulat juga linear (motion blur, sub-frame). Setelah kunci
    # terakhir motor tetap diam (ekstrapolasi konstan), tidak melaju ke shot lain.
    from bpy_extras import anim_utils
    ad = motor.animation_data
    for fc in anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot).fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return jalur
