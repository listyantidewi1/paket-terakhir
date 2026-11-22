"""Kucing oren yang basah kuyup (shot 3).

Aturan sama dengan motor dan kurir: meter, titik pusat armature "Kucing" di
tanah di bawah tengah badan, menghadap +Y, kanan +X (kiri .L di -X).

Tulang:
    akar > pinggul > punggung > leher > kepala
    punggung > kaki_depan_atas > kaki_depan_bawah > telapak_depan   (.L/.R)
    pinggul  > paha > betis > telapak_belakang                       (.L/.R)
    pinggul  > ekor_1 > ... > ekor_6
Kendali: ik_depan, ik_belakang (.L/.R) = posisi telapak; siku_depan,
lutut_belakang = arah tekuk.

Ekor: pose mengatur lengkung ekor (rotasi X); ayunan kiri-kanan (rotasi Z)
berasal dari driver sinus dengan amplitudo properti "ayun_ekor" (derajat,
bisa diberi keyframe). ayun_ekor = 0 berarti ekor benar-benar diam.

Bulu: hair curves per bagian tubuh, menempel kaku pada tulangnya (bone
parent), jadi ikut bergerak tanpa simulasi. Basah = helai menggumpal (clump),
warna lebih gelap, dan lebih licin. Jumlah helai dijaga kecil (lihat BULU)
supaya hemat memori untuk kartu grafis 4 GB.
"""

import math
import random

import bpy
from mathutils import Euler, Matrix, Vector

from . import bahan
from . import kurir
from .kurir import _Mesh

SEED = 3003
KEPADATAN = 9.0  # helai per cm2 (dikali faktor tiap bagian); 9/cm2 sudah tampak penuh setelah menggumpal
TITIK_PER_HELAI = 4


def _tulang():
    t = [
        ("akar", (0, 0, 0), (0, 0, 0.05), None, False),
        ("pinggul", (0, -0.12, 0.21), (0, 0.0, 0.22), "akar", True),
        ("punggung", (0, 0.0, 0.22), (0, 0.12, 0.23), "pinggul", True),
        ("leher", (0, 0.12, 0.23), (0, 0.16, 0.28), "punggung", True),
        ("kepala", (0, 0.16, 0.28), (0, 0.24, 0.3), "leher", True),
    ]
    ekor = Vector((0, -0.13, 0.21))
    induk = "pinggul"
    for i in range(6):
        sudut = math.radians(-20 - 8 * i)  # menjuntai ke belakang-bawah
        ujung = ekor + Vector((0, -math.cos(sudut), math.sin(sudut))) * 0.045
        t.append((f"ekor_{i + 1}", tuple(ekor), tuple(ujung), induk, True))
        ekor, induk = ujung, f"ekor_{i + 1}"
    for s, x in (("L", -1), ("R", 1)):
        xd, xb = x * 0.04, x * 0.045
        t += [
            (f"kaki_depan_atas.{s}", (xd, 0.11, 0.19), (xd, 0.1, 0.1), "punggung", True),
            (f"kaki_depan_bawah.{s}", (xd, 0.1, 0.1), (xd, 0.11, 0.015), f"kaki_depan_atas.{s}", True),
            (f"telapak_depan.{s}", (xd, 0.11, 0.015), (xd, 0.135, 0.005), f"kaki_depan_bawah.{s}", True),
            (f"paha.{s}", (xb, -0.1, 0.19), (xb, -0.06, 0.11), "pinggul", True),
            (f"betis.{s}", (xb, -0.06, 0.11), (xb, -0.13, 0.05), f"paha.{s}", True),
            (f"telapak_belakang.{s}", (xb, -0.13, 0.05), (xb, -0.11, 0.005), f"betis.{s}", True),
            (f"ik_depan.{s}", (xd, 0.11, 0.015), (xd, 0.135, 0.005), "akar", False),
            (f"ik_belakang.{s}", (xb, -0.13, 0.05), (xb, -0.11, 0.005), "akar", False),
            (f"siku_depan.{s}", (xd, -0.1, 0.1), (xd, -0.1, 0.15), "akar", False),
            (f"lutut_belakang.{s}", (xb, 0.2, 0.12), (xb, 0.2, 0.17), "akar", False),
        ]
    return t


# Bagian tubuh: (tulang, a, b, rx, ry, bahan, faktor bulu, panjang bulu, arah alir)
# arah alir: -1 = bulu rebah ke belakang (melawan arah tulang), +1 = searah tulang
def _bagian():
    b = [
        ("pinggul", (0, -0.155, 0.2), (0, 0.01, 0.212), 0.062, 0.072, "kucing_kulit", 1.0, 0.018, -1),
        ("punggung", (0, -0.01, 0.214), (0, 0.13, 0.228), 0.058, 0.07, "kucing_kulit", 1.0, 0.018, -1),
        ("leher", (0, 0.11, 0.228), (0, 0.17, 0.285), 0.042, 0.042, "kucing_kulit", 1.0, 0.016, -1),
        ("kepala", (0, 0.158, 0.302), (0, 0.248, 0.3), 0.05, 0.046, "kucing_kulit", 0.9, 0.009, -1),
        ("kepala", (0, 0.228, 0.284), (0, 0.268, 0.282), 0.024, 0.02, "kucing_kulit", 0.9, 0.006, -1),
    ]
    for s, x in (("L", -1), ("R", 1)):
        xd, xb = x * 0.04, x * 0.045
        b += [
            ("kepala", (x * 0.03, 0.19, 0.33), (x * 0.036, 0.195, 0.372), 0.017, 0.006, "kucing_kulit", 0.6, 0.004, 1),
            (f"kaki_depan_atas.{s}", (xd, 0.11, 0.19), (xd, 0.1, 0.1), 0.021, 0.021, "kucing_kulit", 1.0, 0.012, 1),
            (f"kaki_depan_bawah.{s}", (xd, 0.1, 0.1), (xd, 0.11, 0.015), 0.016, 0.016, "kucing_kulit", 1.0, 0.009, 1),
            (f"telapak_depan.{s}", (xd, 0.105, 0.012), (xd, 0.14, 0.008), 0.017, 0.012, "kucing_kulit", 0.8, 0.005, 1),
            (f"paha.{s}", (xb, -0.105, 0.2), (xb, -0.06, 0.11), 0.032, 0.03, "kucing_kulit", 1.0, 0.016, 1),
            (f"betis.{s}", (xb, -0.06, 0.11), (xb, -0.13, 0.05), 0.019, 0.019, "kucing_kulit", 1.0, 0.01, 1),
            (f"telapak_belakang.{s}", (xb, -0.133, 0.05), (xb, -0.1, 0.006), 0.015, 0.014, "kucing_kulit", 0.8, 0.005, 1),
        ]
    for i in range(6):
        b.append((f"ekor_{i + 1}", None, None, 0.016 - 0.001 * i, 0.016 - 0.001 * i, "kucing_kulit", 1.1, 0.02, 1))
    return b


POSE = {
    "berdiri": {
        "pinggul": (0, -0.12, 0.21), "pinggul_rot": (0, 0, 0),
        "ik": {"ik_depan.L": (-0.04, 0.11, 0.015), "ik_depan.R": (0.04, 0.11, 0.015),
               "ik_belakang.L": (-0.045, -0.13, 0.05), "ik_belakang.R": (0.045, -0.13, 0.05)},
        "ekor": (-10, 8),  # (lengkung pangkal, lengkung tiap ruas) derajat
    },
    # Siap melompat: pantat turun, badan rendah, kepala menatap sasaran
    "jongkok": {
        "pinggul": (0, -0.1, 0.13), "pinggul_rot": (8, 0, 0),
        "fk": {"leher": (10, 0, 0), "kepala": (-12, 0, 0)},
        "ik": {"ik_depan.L": (-0.04, 0.13, 0.015), "ik_depan.R": (0.04, 0.13, 0.015),
               "ik_belakang.L": (-0.05, -0.1, 0.045), "ik_belakang.R": (0.05, -0.1, 0.045)},
        "ekor": (-25, 6),
    },
    # Di udara: kaki depan terjulur ke depan, kaki belakang menjejak ke belakang
    "lompat": {
        "pinggul": (0, -0.12, 0.24), "pinggul_rot": (18, 0, 0),
        "fk": {"kepala": (-15, 0, 0)},
        "ik": {"ik_depan.L": (-0.04, 0.22, 0.2), "ik_depan.R": (0.04, 0.22, 0.2),
               "ik_belakang.L": (-0.045, -0.26, 0.12), "ik_belakang.R": (0.045, -0.26, 0.12)},
        "ekor": (5, -4),
    },
    # Duduk: pantat di alas, badan tegak, kaki depan lurus, ekor melingkar ke depan
    "duduk": {
        "pinggul": (0, -0.1, 0.05), "pinggul_rot": (48, 0, 0),
        "fk": {"leher": (-20, 0, 0), "kepala": (-28, 0, 0)},
        "ik": {"ik_depan.L": (-0.035, 0.05, 0.015), "ik_depan.R": (0.035, 0.05, 0.015),
               "ik_belakang.L": (-0.06, -0.04, 0.03), "ik_belakang.R": (0.06, -0.04, 0.03),
               "lutut_belakang.L": (-0.12, 0.25, 0.15), "lutut_belakang.R": (0.12, 0.25, 0.15)},
        "ekor": (-70, 0), "ekor_sisi": 28,  # menyapu ke samping lalu melingkar ke depan
    },
    # Duduk rapi di bangku: seperti duduk, ekor membungkus kaki depan
    "duduk_rapi": {
        "pinggul": (0, -0.1, 0.05), "pinggul_rot": (50, 0, 0),
        "fk": {"leher": (-22, 0, 0), "kepala": (-26, 0, 0)},
        "ik": {"ik_depan.L": (-0.03, 0.05, 0.015), "ik_depan.R": (0.03, 0.05, 0.015),
               "ik_belakang.L": (-0.06, -0.04, 0.03), "ik_belakang.R": (0.06, -0.04, 0.03),
               "lutut_belakang.L": (-0.12, 0.25, 0.15), "lutut_belakang.R": (0.12, 0.25, 0.15)},
        "ekor": (-75, 0), "ekor_sisi": 38,
    },
    # Digendong: badan mendatar, kaki tergantung lemas
    "digendong": {
        "pinggul": (0, -0.12, 0.21), "pinggul_rot": (0, 0, 0),
        "fk": {"kepala": (-10, 0, 0)},
        "ik": {"ik_depan.L": (-0.035, 0.12, 0.05), "ik_depan.R": (0.035, 0.12, 0.05),
               "ik_belakang.L": (-0.045, -0.15, 0.07), "ik_belakang.R": (0.045, -0.15, 0.07)},
        "ekor": (-35, 10),
    },
}


# --------------------------------------------------------------------------


def _bahan():
    if "kucing_kulit" in bpy.data.materials:
        return
    bahan.polos("kucing_kulit", (0.42, 0.17, 0.04), kasar=0.45)  # kulit oren di sela bulu
    bahan.polos("kucing_mata", (0.25, 0.3, 0.02), kasar=0.03, emisi=(0.6, 0.65, 0.1), kuat=0.05)
    bahan.polos("kucing_hidung", (0.45, 0.2, 0.2), kasar=0.3)
    b = bpy.data.materials.new("kucing_bulu")
    if b.node_tree is None:
        b.use_nodes = True
    nt = b.node_tree
    nt.nodes.clear()
    rambut = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    rambut.parametrization = "COLOR"
    # Soket berubah menurut parametrisasi; atur yang tersedia saja.
    # (Variasi warna per helai sudah ada di atribut "warna".)
    for soket, nilai in (("Roughness", 0.22), ("Radial Roughness", 0.3), ("Coat", 0.15)):  # basah: licin
        if soket in rambut.inputs:
            rambut.inputs[soket].default_value = nilai
    warna = nt.nodes.new("ShaderNodeAttribute")
    warna.attribute_name = "warna"
    nt.links.new(warna.outputs["Color"], rambut.inputs["Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(rambut.outputs[0], out.inputs["Surface"])


def _armature(kol, nama):
    data = bpy.data.armatures.new(nama)
    arm = bpy.data.objects.new(nama, data)
    kol.objects.link(arm)
    data.display_type = "STICK"
    lapisan = bpy.context.view_layer
    for o in lapisan.objects:
        o.select_set(False)
    lapisan.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = data.edit_bones
    for nm, kepala, ekor, induk, deform in _tulang():
        b = eb.new(nm)
        b.head, b.tail = kepala, ekor
        b.roll = 0.0
        b.use_deform = deform
        if induk:
            b.parent = eb[induk]
            b.use_connect = (Vector(kepala) - eb[induk].tail).length < 1e-6
    bpy.ops.object.mode_set(mode="OBJECT")
    pb = arm.pose.bones
    for p in pb:
        p.rotation_mode = "XYZ"
    for s in ("L", "R"):
        for rantai, ujung, sasaran, tiang in (("kaki_depan_bawah", "telapak_depan", "ik_depan", "siku_depan"),
                                              ("betis", "telapak_belakang", "ik_belakang", "lutut_belakang")):
            ik = pb[f"{rantai}.{s}"].constraints.new("IK")
            ik.target, ik.subtarget = arm, f"{sasaran}.{s}"
            ik.pole_target, ik.pole_subtarget = arm, f"{tiang}.{s}"
            ik.pole_angle = math.radians(-90)
            ik.chain_count = 2
            rot = pb[f"{ujung}.{s}"].constraints.new("COPY_ROTATION")
            rot.target, rot.subtarget = arm, f"{sasaran}.{s}"
    # Ayunan ekor: sinus berjalan dari pangkal ke ujung
    arm["ayun_ekor"] = 0.0
    for i in range(6):
        fc = pb[f"ekor_{i + 1}"].driver_add("rotation_euler", 2)
        var = fc.driver.variables.new()
        var.name, var.type = "a", "SINGLE_PROP"
        var.targets[0].id = arm
        var.targets[0].data_path = '["ayun_ekor"]'
        sisi = fc.driver.variables.new()
        sisi.name, sisi.type = "s", "SINGLE_PROP"
        sisi.targets[0].id = arm
        sisi.targets[0].data_path = '["ekor_sisi"]'
        fc.driver.expression = f"(s + a * sin(frame * 0.21 - {0.7 * i:.2f})) * 0.01745"
    arm["ekor_sisi"] = 0.0
    return arm


def _tubuh(kol, arm):
    m = _Mesh(["kucing_kulit", "kucing_mata", "kucing_hidung"])
    bagian = _bagian()
    tulang = {b.name: b for b in arm.data.bones}
    for tl, a, b, rx, ry, nb, *_ in bagian:
        if a is None:
            a, b = tulang[tl].head_local, tulang[tl].tail_local
        m.lonjong(a, b, rx, ry, tl, nb, lebih=0.01 if tl.startswith("ekor") else 0.006, n=12, m=8)
    for x in (-1, 1):
        m.lonjong((x * 0.021, 0.24, 0.306), (x * 0.023, 0.25, 0.306), 0.009, 0.009, "kepala", "kucing_mata",
                  lebih=0.004, n=10, m=6)
    m.lonjong((0, 0.262, 0.293), (0, 0.27, 0.292), 0.007, 0.005, "kepala", "kucing_hidung", lebih=0.002, n=8, m=5)
    tubuh = m.objek("Kucing_Tubuh", kol, arm)
    sub = tubuh.modifiers.new("Halus", "SUBSURF")
    sub.levels = sub.render_levels = 1
    return tubuh


def _warna_bulu(p, n, tl, rng):
    """Tabi oren: belang gelap melintang, perut/dada/telapak krem. Basah = lebih gelap."""
    oren, gelap, krem = Vector((0.62, 0.24, 0.05)), Vector((0.3, 0.09, 0.02)), Vector((0.62, 0.45, 0.28))
    if tl.startswith(("telapak",)) or (tl in ("pinggul", "punggung", "leher") and n.z < -0.45):
        w = krem
    elif tl == "kepala" and p.y > 0.235 and p.z < 0.295:
        w = krem  # moncong
    else:
        u = p.y if tl in ("pinggul", "punggung", "leher", "kepala") else p.z + p.y * 0.5
        if tl.startswith("ekor"):
            u = p.y * 1.6
        belang = 0.5 + 0.5 * math.sin(u * 95 + (0.6 if tl == "kepala" else 0))
        w = oren.lerp(gelap, max(0.0, belang - 0.35) * 1.5)
    w = w * rng.uniform(0.85, 1.1) * 0.8  # basah: lebih gelap
    return (w.x, w.y, w.z, 1.0)


def _bulu(kol, arm):
    """Satu objek hair curves per bagian tubuh, menempel kaku pada tulangnya."""
    rng = random.Random(SEED)
    tulang = {b.name: b for b in arm.data.bones}
    total = 0
    objek = []
    for indeks, (tl, a, b, rx, ry, _, faktor, panjang, alir) in enumerate(_bagian()):
        if a is None:
            a, b = tulang[tl].head_local, tulang[tl].tail_local
        a, b = Vector(a), Vector(b)
        d = (b - a).normalized()
        pusat = (a + b) / 2
        setengah = (b - a).length / 2 + 0.006
        ux = Vector((1, 0, 0)) - d * d.x
        ux = ux.normalized() if ux.length > 1e-4 else Vector((0, 1, 0))
        uy = d.cross(ux).normalized()
        # Luas permukaan elipsoid kira-kira (rumus Knud Thomsen), dalam cm2
        p_ = 1.6075
        luas = 4 * math.pi * (((setengah * rx) ** p_ + (setengah * ry) ** p_ + (rx * ry) ** p_) / 3) ** (1 / p_) * 1e4
        n_gumpal = max(4, int(luas * KEPADATAN * faktor / 7))
        posisi, warna, jari = [], [], []
        for _ in range(n_gumpal):
            # titik dasar gumpalan, merata menurut luas (sampel sin t)
            while True:
                t = rng.uniform(0.15, math.pi - 0.15)
                if rng.random() < math.sin(t):
                    break
            s = rng.uniform(0, 2 * math.pi)
            arah_n = (d * (math.cos(t) * rx * ry) + ux * (math.sin(t) * math.cos(s) * setengah * ry)
                      + uy * (math.sin(t) * math.sin(s) * setengah * rx)).normalized()
            alir_v = d * alir
            dasar_g = pusat + d * (setengah * math.cos(t)) + ux * (rx * math.sin(t) * math.cos(s)) \
                + uy * (ry * math.sin(t) * math.sin(s))
            arah = (arah_n * 0.45 + alir_v).normalized()
            pj = panjang * rng.uniform(0.75, 1.2)
            ujung_g = dasar_g + arah * pj + arah_n * pj * 0.25
            w = _warna_bulu(dasar_g, arah_n, tl, rng)
            for _ in range(7):  # 7 helai per gumpalan: basah, menyatu di ujung
                geser = (ux * rng.uniform(-1, 1) + uy * rng.uniform(-1, 1) + d * rng.uniform(-1, 1)) * 0.0035
                dasar = dasar_g + geser
                dasar = pusat + (dasar - pusat)  # tetap di dekat permukaan
                ujung = dasar + arah * pj * rng.uniform(0.85, 1.05) + arah_n * pj * 0.25
                ujung = ujung.lerp(ujung_g, 0.7)
                for k in range(TITIK_PER_HELAI):
                    f = k / (TITIK_PER_HELAI - 1)
                    tekuk = arah_n * (pj * 0.15 * math.sin(f * math.pi))
                    posisi.append(dasar.lerp(ujung, f) + tekuk)
                    jari.append(0.00045 * (1 - 0.8 * f))
                warna.append(w)
        n_helai = len(warna)
        total += n_helai
        cv = bpy.data.hair_curves.new(f"Kucing_Bulu_{indeks:02d}_{tl}")
        cv.add_curves([TITIK_PER_HELAI] * n_helai)
        # posisi relatif terhadap ekor tulang (ruang induk tulang)
        tulang_b = tulang[tl]
        ke_tulang = (tulang_b.matrix_local @ Matrix.Translation((0, tulang_b.length, 0))).inverted()
        datar = []
        for p in posisi:
            q = ke_tulang @ p
            datar += [q.x, q.y, q.z]
        cv.position_data.foreach_set("vector", datar)
        cv.attributes.new("radius", "FLOAT", "POINT").data.foreach_set("value", jari)
        aw = cv.attributes.new("warna", "FLOAT_COLOR", "CURVE")
        aw.data.foreach_set("color", [c for w in warna for c in w])
        cv.materials.append(bpy.data.materials["kucing_bulu"])
        obj = bpy.data.objects.new(cv.name, cv)
        kol.objects.link(obj)
        obj.parent = arm
        obj.parent_type = "BONE"
        obj.parent_bone = tl
        objek.append(obj)
    arm["jumlah_helai_bulu"] = total
    return objek


def buat_kucing(kol, nama="Kucing"):
    """Bangun kucing berdiri di titik asal. Kembalikan armature."""
    _bahan()
    arm = _armature(kol, nama)
    tubuh = _tubuh(kol, arm)
    _bulu(kol, arm)
    kurir.pasang_tumbukan(tubuh, 0.005)  # ponco kurir tidak menembus kucing yang digendong
    terapkan_pose(arm, "berdiri")
    return arm


def terapkan_pose(arm, nama, frame=None, ayun=None):
    """Pasang pose kucing; jika frame diberikan, simpan sebagai keyframe."""
    p = POSE[nama]
    pb, tl = arm.pose.bones, arm.data.bones
    for b in pb:
        b.location = (0, 0, 0)
        b.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

    def rot(derajat):
        return Euler([math.radians(a) for a in derajat]).to_matrix().to_4x4()

    pb["pinggul"].matrix = (Matrix.Translation(p["pinggul"]) @ rot(p.get("pinggul_rot", (0, 0, 0)))
                            @ tl["pinggul"].matrix_local.to_3x3().to_4x4())
    bpy.context.view_layer.update()
    for nm, r in p.get("fk", {}).items():
        pb[nm].rotation_euler = [math.radians(a) for a in r]
    pangkal, ruas = p.get("ekor", (0, 0))
    for i in range(6):
        pb[f"ekor_{i + 1}"].rotation_euler.x = math.radians(pangkal if i == 0 else ruas)
    istirahat = POSE["berdiri"]["ik"]
    for nm in [b.name for b in tl if b.name.startswith(("ik_", "siku", "lutut"))]:
        pos = p["ik"].get(nm, istirahat.get(nm, tl[nm].head_local))
        pb[nm].matrix = Matrix.Translation(pos) @ tl[nm].matrix_local.to_3x3().to_4x4()
    arm["ekor_sisi"] = p.get("ekor_sisi", 0.0)
    if ayun is not None:
        arm["ayun_ekor"] = ayun
    bpy.context.view_layer.update()
    if frame is not None:
        for b in pb:
            b.keyframe_insert("location", frame=frame)
            b.keyframe_insert("rotation_euler", index=0, frame=frame)
            b.keyframe_insert("rotation_euler", index=1, frame=frame)
            if not b.name.startswith("ekor"):
                b.keyframe_insert("rotation_euler", index=2, frame=frame)
        arm.keyframe_insert('["ekor_sisi"]', frame=frame)
        arm.keyframe_insert('["ayun_ekor"]', frame=frame)
