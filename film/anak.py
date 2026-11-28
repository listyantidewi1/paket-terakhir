"""Anak kecil di ambang pintu: hanya siluet gelap, membawa kue dengan tiga lilin.

Wajah anak tidak pernah terlihat:
- tubuh memakai bahan hampir hitam dan sangat kasar (tidak ada detail);
- cahaya rumah datang dari belakang anak (lihat dunia_kota._isi_rumah_tujuan);
- api lilin tidak menjadi sumber cahaya bagi permukaan lain (visibilitas
  sinar dimatikan), dan lampu lilin memakai light linking: hanya menerangi
  kue, piring, dan lilin, bukan anak.

Api lilin bergoyang dengan pola tetap (random.Random(SEED)).
Titik pusat "Anak" di lantai di antara kedua kaki, menghadap +Y lokal.
"""

import math
import random

import bpy
from mathutils import Vector

from . import bahan
from .geo import Gabung, Kanvas

SEED = 1997
TINGGI_KUE = 0.74  # tinggi permukaan piring kue dari lantai
POSISI_KUE = Vector((0, 0.24, TINGGI_KUE))  # disodorkan sedikit ke depan
CONDONG = 7.0  # derajat badan condong ke depan (poros di pinggul)


def _condong(derajat, poros=Vector((0, 0, 0.5))):
    """Fungsi titik -> titik: badan atas diputar ke depan (+Y) di sekitar pinggul."""
    from mathutils import Matrix
    r = Matrix.Rotation(math.radians(-derajat), 3, "X")
    return lambda p: poros + r @ (Vector(p) - poros)


def _loft(g, ruas, n=16, tutup_bawah=True):
    """Tabung lembut melewati beberapa titik: [(pusat, jari_u, jari_w, gelombang), ...].

    Penampang tegak lurus arah ruas; gelombang membuat tepi kain tidak rata.
    """
    titik, muka = [], []
    for k, (c, ru, rw, gel) in enumerate(ruas):
        a = ruas[max(k - 1, 0)][0]
        b = ruas[min(k + 1, len(ruas) - 1)][0]
        sumbu = (b - a).normalized()
        bantu = Vector((1, 0, 0)) if abs(sumbu.x) < 0.9 else Vector((0, 1, 0))
        u = (bantu - sumbu * bantu.dot(sumbu)).normalized()
        w = sumbu.cross(u)
        for i in range(n):
            t = 2 * math.pi * i / n
            r = 1 + gel / max(ru, 1e-3) * math.sin(5 * t + 0.7 * k) if gel else 1
            titik.append(c + (u * math.cos(t) * ru + w * math.sin(t) * rw) * r)
    for k in range(len(ruas) - 1):
        for i in range(n):
            p, q = k * n, (k + 1) * n
            muka.append((p + i, p + (i + 1) % n, q + (i + 1) % n, q + i))
    if tutup_bawah:
        muka.append(tuple(reversed(range(n))))
    muka.append(tuple(range((len(ruas) - 1) * n, len(ruas) * n)))
    g.poly(titik, muka)


def _bahan():
    if "siluet" in bpy.data.materials:
        return
    b = bahan.polos("siluet", (0.002, 0.002, 0.002), kasar=1.0)
    # Tanpa kilap: tidak memantulkan ruangan yang terang ke arah kamera
    b.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.0
    bahan.polos("kue_krim", (0.85, 0.78, 0.66), kasar=0.45)
    bahan.polos("kue_coklat", (0.12, 0.05, 0.025), kasar=0.6)
    bahan.polos("kue_piring", (0.8, 0.8, 0.78), kasar=0.2)
    bahan.polos("lilin_merah", (0.8, 0.12, 0.15), kasar=0.4)
    bahan.polos("lilin_biru", (0.12, 0.3, 0.8), kasar=0.4)
    bahan.polos("lilin_kuning", (0.9, 0.75, 0.15), kasar=0.4)
    bahan.polos("api_lilin", (0.0, 0.0, 0.0), emisi=(1.0, 0.62, 0.22), kuat=18.0)


def buat_anak(kol, lokasi, arah_derajat):
    """Siluet anak (sekitar 1,1 m) memegang kue di depan dada. Kembalikan (anak, api, lampu).

    Tubuh digerakkan rangka "Anak_Rangka" (anak dari "Anak"); kue, lilin, dan
    lampu lilin menempel di tulang badan. Jalan dengan jalan().
    """
    _bahan()
    akar = bpy.data.objects.new("Anak", None)
    kol.objects.link(akar)
    akar.location = lokasi
    akar.rotation_euler = (0, 0, math.radians(arah_derajat))

    # Anak umur enam tahun (sekitar 112 cm): kepala besar (seperlima tinggi),
    # badan pendek, baju tidur longgar yang ujungnya bergelombang, celana tidur
    # lebar, lutut sedikit menekuk, badan condong ke depan menyodorkan kue.
    k = Kanvas("Anak_Siluet", kol)
    g = k["siluet"]
    condong = _condong(CONDONG)
    kaki = {}  # sisi -> (rentang titik celana, rentang titik sandal); untuk bobot rangka
    for x in (-0.065, 0.065):  # celana tidur: pinggul, lutut (sedikit ke depan), pergelangan
        sisi = "L" if x < 0 else "R"
        a = len(g.v)
        _loft(g, [(Vector((x, -0.012, 0.55)), 0.075, 0.075, 0.0), (Vector((x, 0.02, 0.42)), 0.068, 0.07, 0.003),
                  (Vector((x, 0.055, 0.29)), 0.062, 0.064, 0.004), (Vector((x, 0.035, 0.17)), 0.062, 0.064, 0.004),
                  (Vector((x, 0.01, 0.05)), 0.066, 0.068, 0.007)])
        b = len(g.v)
        g.bola((x * 1.05, 0.045, 0.032), (0.045, 0.085, 0.032), rimbun=0)  # sandal rumah
        kaki[sisi] = (range(a, b), range(b, len(g.v)))
    g.bola((0, 0.0, 0.53), (0.13, 0.095, 0.08), rimbun=0)  # pinggul
    # Baju tidur: lebar dan longgar, ujung bawah bergelombang
    _loft(g, [(condong(Vector((0, 0, z))), rx, ry, gel) for z, rx, ry, gel in (
        (0.43, 0.185, 0.14, 0.018), (0.5, 0.17, 0.127, 0.01), (0.6, 0.152, 0.11, 0.004),
        (0.72, 0.143, 0.1, 0.0), (0.79, 0.135, 0.092, 0.0), (0.83, 0.1, 0.075, 0.0), (0.855, 0.05, 0.048, 0.0))],
          tutup_bawah=True)
    g.tabung(condong(Vector((0, 0, 0.83))), condong(Vector((0, 0.008, 0.9))), 0.034, n=10)  # leher
    kepala = condong(Vector((0, 0.012, 1.0)))
    g.bola(kepala, (0.1, 0.106, 0.112), rimbun=0)  # kepala besar
    g.bola(kepala + Vector((0, -0.012, 0.018)), (0.107, 0.11, 0.102), rimbun=0)  # rambut
    rr = random.Random(SEED + 1)
    for _ in range(16):  # ujung rambut bergumpal kecil di tepi siluet
        a = rr.uniform(-0.2, 3.34)
        g.bola(kepala + Vector((0.106 * math.cos(a), -0.02 - 0.05 * rr.random(), 0.018 + 0.08 * math.sin(a))),
               (0.022, 0.022, 0.02), rimbun=0)
    for x in (-1, 1):  # lengan baju longgar: bahu, siku menjauh dari badan, tangan di bawah piring
        bahu = condong(Vector((x * 0.125, 0.0, 0.8)))
        siku = Vector((x * 0.175, bahu.y + 0.07, 0.65))
        tangan = Vector((x * 0.125, POSISI_KUE.y + 0.01, POSISI_KUE.z - 0.012))
        _loft(g, [(bahu, 0.05, 0.05, 0.0), (siku, 0.047, 0.047, 0.0),
                  (siku.lerp(tangan, 0.85), 0.045, 0.045, 0.003)])
        g.bola(tangan, (0.03, 0.04, 0.022), rimbun=0)
    k.selesai()
    rangka = _rangka(kol, akar)
    for o in k.kol.objects:
        o.parent = akar
        _bobot(o, rangka, kaki)
        sub = o.modifiers.new("Halus", "SUBSURF")
        sub.levels = sub.render_levels = 2

    # Kue di atas piring, tiga lilin
    kue = Kanvas("Anak_Kue", kol)
    pusat = POSISI_KUE.copy()
    kue["kue_piring"].tabung(pusat, pusat + Vector((0, 0, 0.01)), 0.14, n=28)
    kue["kue_coklat"].tabung(pusat + Vector((0, 0, 0.01)), pusat + Vector((0, 0, 0.05)), 0.105, n=28)
    kue["kue_krim"].tabung(pusat + Vector((0, 0, 0.05)), pusat + Vector((0, 0, 0.085)), 0.108, n=28)
    lilin_pos = []
    for i, nama_bahan in enumerate(("lilin_merah", "lilin_biru", "lilin_kuning")):
        s = 2 * math.pi * i / 3 + 0.4
        p = pusat + Vector((0.05 * math.cos(s), 0.05 * math.sin(s), 0.085))
        kue[nama_bahan].tabung(p, p + Vector((0, 0, 0.065)), 0.0055, n=8)
        lilin_pos.append(p + Vector((0, 0, 0.065)))
    kue.selesai()
    for o in kue.kol.objects:
        _ke_badan(o, rangka)

    # Api dan lampu lilin; lampu hanya menerangi kue (light linking)
    terima = bpy.data.collections.new("Kue_Diterangi_Lilin")
    for o in kue.kol.objects:
        terima.objects.link(o)
    api_list, lampu_list = [], []
    for i, p in enumerate(lilin_pos):
        g = Gabung()
        g.bola((0, 0, 0.012), (0.0045, 0.0045, 0.013), rimbun=0)
        mesh = bpy.data.meshes.new(f"Api_Lilin_{i}")
        mesh.from_pydata(g.v, [], g.f)
        mesh.materials.append(bpy.data.materials["api_lilin"])
        mesh.shade_smooth()
        api = bpy.data.objects.new(f"Api_Lilin_{i}", mesh)
        kol.objects.link(api)
        api.location = p + Vector((0, 0, 0.002))
        _ke_badan(api, rangka)
        # Api terlihat kamera, tetapi tidak menerangi permukaan lain (wajah anak)
        api.visible_diffuse = False
        api.visible_glossy = False
        api.visible_transmission = False
        api.visible_volume_scatter = False
        api.visible_shadow = False
        data = bpy.data.lights.new(f"Lampu_Lilin_{i}", type="POINT")
        data.color = (1.0, 0.6, 0.25)
        data.energy = 0.6
        data.shadow_soft_size = 0.004
        lampu = bpy.data.objects.new(f"Lampu_Lilin_{i}", data)
        kol.objects.link(lampu)
        lampu.location = p + Vector((0, 0, 0.014))
        _ke_badan(lampu, rangka)
        lampu.light_linking.receiver_collection = terima
        api_list.append(api)
        lampu_list.append(lampu)
    for item in terima.collection_objects:
        item.light_linking.link_state = "INCLUDE"
    return akar, api_list, lampu_list


# --------------------------------------------------------------------------
# Rangka dan langkah

PANGGUL_X = 0.065  # jarak kaki dari tengah
UJUNG_KAKI = 0.11  # ujung sandal di depan pergelangan (y)


def _titik_kaki(sisi):
    x = -PANGGUL_X if sisi == "L" else PANGGUL_X
    return {"pinggul": Vector((x, -0.012, 0.55)), "lutut": Vector((x, 0.055, 0.29)),
            "tumit": Vector((x, 0.01, 0.05)), "ujung": Vector((x * 1.05, UJUNG_KAKI, 0.03))}


BADAN = (Vector((0, 0, 0.5)), Vector((0, 0, 0.85)))  # poros goyang badan di pinggul


def _rangka(kol, akar):
    """Tulang: badan (pinggul ke leher), paha, betis, telapak per kaki.

    Telapak menempel pada tulang sasaran "ik" (tanpa induk), dan betis memakai
    IK ke sasaran itu. Selama sasaran diam, telapak benar-benar diam di lantai
    dan lutut menekuk sendiri mengikuti pinggul.
    """
    data = bpy.data.armatures.new("Anak_Rangka")
    arm = bpy.data.objects.new("Anak_Rangka", data)
    kol.objects.link(arm)
    arm.parent = akar
    data.display_type = "STICK"
    lapisan = bpy.context.view_layer
    for o in lapisan.objects:
        o.select_set(False)
    lapisan.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = data.edit_bones

    def tulang(nama, kepala, ekor, induk=None, deform=True, sambung=False):
        b = eb.new(nama)
        b.head, b.tail, b.roll = kepala, ekor, 0.0
        b.use_deform = deform
        if induk:
            b.parent = eb[induk]
            b.use_connect = sambung
        return b
    tulang("badan", *BADAN)
    for s in ("L", "R"):
        t = _titik_kaki(s)
        tulang(f"paha.{s}", t["pinggul"], t["lutut"], "badan")
        tulang(f"betis.{s}", t["lutut"], t["tumit"], f"paha.{s}", sambung=True)
        tulang(f"ik.{s}", t["tumit"], t["tumit"] + Vector((0, 0, 0.1)), deform=False)
        tulang(f"telapak.{s}", t["tumit"], t["ujung"], f"ik.{s}")
        tulang(f"lutut.{s}", t["lutut"] + Vector((0, 0.5, 0)), t["lutut"] + Vector((0, 0.5, 0.1)), "badan",
               deform=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    pb = arm.pose.bones
    for s in ("L", "R"):
        ik = pb[f"betis.{s}"].constraints.new("IK")
        ik.target, ik.subtarget = arm, f"ik.{s}"
        ik.pole_target, ik.pole_subtarget = arm, f"lutut.{s}"
        ik.pole_angle = math.radians(90)  # lutut menekuk ke depan (ke arah tiang), sama dengan mesh
        ik.chain_count = 2
    return arm


def _bobot(obj, arm, kaki):
    """Badan, lengan, kepala ikut tulang badan; celana ikut paha dan betis
    (berbaur di lutut); sandal ikut telapak."""
    n = len(obj.data.vertices)
    grup = {nm: obj.vertex_groups.new(name=nm) for nm in
            ["badan"] + [f"{t}.{s}" for s in ("L", "R") for t in ("paha", "betis", "telapak")]}
    di_kaki = set()
    for s, (celana, sandal) in kaki.items():
        for i in celana:
            z = obj.data.vertices[i].co.z
            w = min(max((0.36 - z) / 0.14, 0.0), 1.0)  # 0 di atas lutut, 1 di bawahnya
            if w < 1:
                grup[f"paha.{s}"].add([i], 1 - w, "REPLACE")
            if w > 0:
                grup[f"betis.{s}"].add([i], w, "REPLACE")
            di_kaki.add(i)
        grup[f"telapak.{s}"].add(list(sandal), 1.0, "REPLACE")
        di_kaki.update(sandal)
    grup["badan"].add([i for i in range(n) if i not in di_kaki], 1.0, "REPLACE")
    mod = obj.modifiers.new("Rangka", "ARMATURE")
    mod.object = arm


def _ke_badan(obj, arm):
    """Tempelkan objek pada tulang badan tanpa mengubah letaknya (kue tetap di tangan)."""
    from mathutils import Matrix
    b = arm.data.bones["badan"]
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = "badan"
    obj.matrix_parent_inverse = (b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()


def _mulus(t):
    return t * t * (3 - 2 * t)


def rencana_langkah(f0, f1, y0, y1, jumlah=4, ganda=0.25):
    """Jadwal langkah kecil: kaki kiri dan kanan bergantian, kedua kaki rapat di
    awal dan akhir. Setiap langkah: (sisi, frame angkat, frame tapak, y dari, y ke).

    Langkah pertama dan terakhir setengah panjang, jadi jarak antar kaki saat
    keduanya menapak = (y1 - y0) / (jumlah - 1); untuk 0,85 m dan 4 langkah 28 cm,
    langkah kecil anak umur enam tahun yang membawa kue. `ganda` = lama kedua
    kaki menapak di antara dua langkah, sebagai bagian dari lama satu ayunan.
    """
    satuan = (f1 - f0) / (jumlah + ganda * (jumlah + 1))
    jarak = (y1 - y0) / (jumlah - 1)
    tapak = {"L": y0, "R": y0}
    hasil = []
    for k in range(jumlah):
        sisi = "L" if k % 2 == 0 else "R"
        ke = y1 if k >= jumlah - 2 else y0 + jarak * (k + 1)
        a = f0 + ganda * satuan * (k + 1) + satuan * k
        hasil.append((sisi, a, a + satuan, tapak[sisi], ke))
        tapak[sisi] = ke
    return hasil


ANGKAT = 0.04   # tinggi ayunan sandal
NAIK = 0.012    # badan naik di tengah langkah (satu kaki menapak)
TURUN = 0.025   # pinggul turun sedikit (lutut menekuk) selama berjalan
GOYANG = 0.016  # pinggul bergeser ke kaki yang menapak
MIRING = 1.5    # derajat badan miring ke kaki yang menapak (kue tetap hampir datar)


def keadaan_jalan(t, rencana, y0, y1):
    """Pose pada waktu t (boleh pecahan): y tiap sandal, angkat, dan pinggul."""
    kaki = {"L": [y0, 0.0], "R": [y0, 0.0]}
    goyang = naik = 0.0
    for sisi, a, b, dari, ke in rencana:
        arah = -1.0 if sisi == "L" else 1.0  # badan condong ke kaki yang menapak (lawan)
        if t >= b:
            kaki[sisi] = [ke, 0.0]
        elif t > a:
            p = (t - a) / (b - a)
            kaki[sisi] = [dari + (ke - dari) * _mulus(p), ANGKAT * math.sin(math.pi * p)]
            naik += NAIK * math.sin(math.pi * p)
        # pinggul pindah ke kaki yang menapak sedikit sebelum kaki lain terangkat
        lebar = (b - a) * 0.35
        if a - lebar < t < b + lebar:
            p = (t - (a - lebar)) / (b - a + 2 * lebar)
            goyang += -arah * GOYANG * math.sin(math.pi * p)
    awal, akhir = rencana[0][1], rencana[-1][2]
    satuan = rencana[0][2] - rencana[0][1]
    # pinggul turun selama berjalan, naik lagi saat berhenti
    jalan = min(max((t - (awal - satuan)) / satuan, 0), 1) * min(max(((akhir + satuan) - t) / satuan, 0), 1)
    return kaki, goyang, naik - TURUN * _mulus(jalan)


def jalan(arm, f0, f1, y0, y1, langkah=4):
    """Anak berjalan dari y0 ke y1 (koordinat lokal, +y = ke depan) antara f0 dan f1.

    Kunci per frame: sasaran IK tiap sandal (diam saat menapak), dan tulang badan
    (maju, naik turun, bergeser dan sedikit miring ke kaki yang menapak).
    Pinggul maju mengikuti rata-rata kedua sandal yang dihaluskan.
    Mengembalikan rencana langkah.
    """
    from mathutils import Matrix
    rencana = rencana_langkah(f0, f1, y0, y1, langkah)
    pb = arm.pose.bones

    def y_pinggul(t):
        # rata-rata kedua sandal, dihaluskan selebar setengah langkah supaya pinggul
        # maju mulus tetapi tidak tertinggal (kaki depan tetap terjangkau)
        n, jum = 9, 0.0
        lebar = (rencana[0][2] - rencana[0][1]) * 0.5
        for i in range(n):
            u = t + lebar * (i / (n - 1) - 0.5)
            k, _, _ = keadaan_jalan(u, rencana, y0, y1)
            jum += (k["L"][0] + k["R"][0]) / 2
        return jum / n

    satuan = rencana[0][2] - rencana[0][1]
    for f in range(math.floor(f0 - 2 * satuan), math.ceil(f1 + 2 * satuan) + 1):
        kaki, goyang, naik = keadaan_jalan(f, rencana, y0, y1)
        yp = y_pinggul(f)
        miring = math.radians(MIRING) * goyang / GOYANG
        b = arm.data.bones["badan"]
        pb["badan"].matrix = (Matrix.Translation((goyang, yp, naik)) @ Matrix.Translation(b.head_local)
                              @ Matrix.Rotation(miring, 4, "Y") @ Matrix.Translation(-b.head_local)
                              @ b.matrix_local)
        for s in ("L", "R"):
            t = arm.data.bones[f"ik.{s}"]
            pb[f"ik.{s}"].matrix = Matrix.Translation((0, kaki[s][0], kaki[s][1])) @ t.matrix_local
        for nm in ("badan", "ik.L", "ik.R"):
            pb[nm].keyframe_insert("location", frame=f)
            pb[nm].keyframe_insert("rotation_quaternion", frame=f)
    from bpy_extras import anim_utils
    ad = arm.animation_data
    for fc in anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot).fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return rencana


def berdiri(arm, f, y):
    """Kunci anak berdiri tegak dengan kedua kaki rapat di y pada frame f."""
    from mathutils import Matrix
    pb = arm.pose.bones
    pb["badan"].matrix = Matrix.Translation((0, y, 0)) @ arm.data.bones["badan"].matrix_local
    for s in ("L", "R"):
        pb[f"ik.{s}"].matrix = Matrix.Translation((0, y, 0)) @ arm.data.bones[f"ik.{s}"].matrix_local
    for nm in ("badan", "ik.L", "ik.R"):
        pb[nm].keyframe_insert("location", frame=f)
        pb[nm].keyframe_insert("rotation_quaternion", frame=f)


def goyang_api(api_list, lampu_list, frame_awal, frame_akhir, langkah=2):
    """Api bergoyang dengan pola tetap: tinggi, condong, dan terang berubah tiap `langkah` frame."""
    rng = random.Random(SEED)
    for api, lampu in zip(api_list, lampu_list):
        fase = rng.uniform(0, 6.28)
        for f in range(frame_awal, frame_akhir + 1, langkah):
            t = f * 0.35 + fase
            tinggi = 1.0 + 0.12 * math.sin(t) + rng.uniform(-0.08, 0.08)
            api.scale = (1.0, 1.0, tinggi)
            api.rotation_euler = (math.radians(rng.uniform(-6, 6)), math.radians(6 * math.sin(t * 0.7)), 0)
            api.keyframe_insert("scale", frame=f)
            api.keyframe_insert("rotation_euler", frame=f)
            lampu.data.energy = 0.6 * (0.85 + 0.15 * tinggi + rng.uniform(-0.05, 0.05))
            lampu.data.keyframe_insert("energy", frame=f)
