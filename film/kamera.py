"""Gerakan kamera per shot, sesuai kolom "Gerakan kamera" di STORYBOARD.md.

Kamera dibuat oleh shot.py (satu per shot, berganti lewat marker). Modul ini
memberi keyframe posisi, arah, lensa, dan fokus (depth of field). Semua
gerakan memakai easing. Motion blur ringan diatur di bangun.py.

Wajah kurir tidak pernah terlihat: kamera selalu di belakang atau samping
belakang kurir, dan saat helm terpasang kaca helm gelap. Anak hanya siluet.
Periksa dengan periksa_wajah().
"""

import math

import bpy
from mathutils import Matrix, Vector

from . import adegan, dunia_kota as kota, waktu

ATAS = Vector((0, 0, 1))


def _hadap(lok, sasaran, atas=ATAS):
    """Rotasi kamera (Euler) dari lok menatap sasaran, dengan arah atas gambar."""
    maju = (Vector(sasaran) - Vector(lok)).normalized()
    kanan = maju.cross(atas).normalized()
    atas2 = kanan.cross(maju)
    m = Matrix((kanan, atas2, -maju)).transposed()  # kolom: X kamera, Y kamera, Z kamera (ke belakang)
    return m.to_euler()


def _ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _kunci(cam, f, lok, sasaran, lensa=None, atas=ATAS):
    cam.location = lok
    e = _hadap(lok, sasaran, atas)
    if cam.animation_data and cam.animation_data.action:
        e.make_compatible(cam.rotation_euler)  # hindari putaran 360 derajat antar kunci
    cam.rotation_euler = e
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_euler", frame=f)
    if lensa is not None:
        cam.data.lens = lensa
        cam.data.keyframe_insert("lens", frame=f)


def _fokus(cam, objek, fstop, tulang=""):
    dof = cam.data.dof
    dof.use_dof = True
    dof.focus_object = bpy.data.objects[objek]
    if tulang:
        dof.focus_subtarget = tulang
    dof.aperture_fstop = fstop
    dof.aperture_blades = 7


def _kamera(nomor):
    return bpy.data.objects[f"S{nomor:02d}_Kamera"]


def _shot1(s):
    """Lensa 24 mm, rendah dekat genangan; naik pelan (crane) saat motor lewat lalu menjauh."""
    cam = _kamera(1)
    dasar = kota.TITIK["motor_kenanga"] + Vector((2.2, -7.6, 0.0))  # di samping lajur motor
    for f in range(s.frame_mulai, s.frame_selesai + 1, 4):
        t = _ease((f - 14) / 130)
        lok = dasar + Vector((0, 0, 0.3 + 1.25 * t))
        sasaran = dasar + Vector((-1.6, 40, 0.8 + 1.6 * t))
        _kunci(cam, f, lok, sasaran, 24 if f == s.frame_mulai else None)
    _fokus(cam, "Motor", 2.8)


# Shot 2b: kamera diam dan rendah di tepi seberang kali, 11,6 m dari titik motor
# mengerem, 0,55 m di atas jalan (0,9 m di atas air); lensa 40 mm.
# Air kali mengisi sepertiga bawah gambar, bibir beton tanpa pagar melintang di
# bawah motor, dan lampu depan motor (arah -38 derajat, 26 derajat dari garis
# ke kamera) terpantul di air. Relatif terhadap (KALI_X, 28.3, 0).
SHOT2B_LOK = Vector((9.0, 4.7, 0.55))
SHOT2B_SASARAN = Vector((-1.6, 0.0, 0.7))
SHOT2B_LENSA = 40


def _shot2(s):
    """Shot 2 dalam dua kamera:
    a) 7-10 dtk: close-up layar HP (lensa 50 mm, f/2), mengikuti HP di setang;
       jalan di belakangnya kabur.
    b) 10-20 dtk: kamera diam dan rendah di seberang kali, lensa 40 mm."""
    cam = _kamera(2)
    layar = bpy.data.objects["HP_Layar"]
    scene = bpy.context.scene
    for f in range(s.frame_mulai, adegan.POTONG_KALI):
        scene.frame_set(f)
        mw = layar.matrix_world
        lok = mw @ Vector((0.0, -0.012, 0.28))
        _kunci(cam, f, lok, mw.translation, 50 if f == s.frame_mulai else None,
               atas=(mw.to_3x3() @ Vector((0, 1, 0))).normalized())
    _fokus(cam, "HP_Layar", 2.0)

    # Kamera kedua untuk potongan seberang kali, berganti lewat marker
    data = bpy.data.cameras.new("S02b_Kamera")
    data.sensor_fit = "AUTO"
    data.clip_start = 0.05
    data.clip_end = 500
    cam2 = bpy.data.objects.new("S02b_Kamera", data)
    cam.users_collection[0].objects.link(cam2)
    dasar = Vector((kota.KALI_X, 28.3, 0.0))
    _kunci(cam2, adegan.POTONG_KALI, dasar + SHOT2B_LOK, dasar + SHOT2B_SASARAN, SHOT2B_LENSA)
    _fokus(cam2, "Motor", 2.8)
    penanda = scene.timeline_markers.new("S02b", frame=adegan.POTONG_KALI)
    penanda.camera = cam2


def _arah_kamera(cam):
    """Arah pandang kamera saat ini (kamera tidak punya induk)."""
    return cam.rotation_euler.to_matrix() @ Vector((0, 0, -1))


# Shot 3: posisi diam hasil pencarian (motor, lampu lalu lintas, bangku dalam satu bingkai)
SHOT3 = {"geser": Vector((4.5, -8.0, 1.2)), "lensa": 35}


def _shot3(s):
    """Diam, lensa 35 mm: motor, lampu lalu lintas, dan bangku warung dalam satu bingkai."""
    cam = _kamera(3)
    M = kota.TITIK["motor_lampu_merah"]
    tengah = (M + Vector((0, -0.4, 0.9)) + kota.TITIK["lampu_lalu_lintas"] + Vector((0, 0, 2.2))
              + kota.TITIK["bangku_warung"] + Vector((0, 0, 0.5))) / 3
    _kunci(cam, s.frame_mulai, M + SHOT3["geser"], tengah, SHOT3["lensa"])
    _fokus(cam, "Kucing", 5.6)


def _shot4(s):
    """Mengikuti dari belakang motor menyusuri Gang Melati (sedikit tertinggal, halus)."""
    cam = _kamera(4)
    m = bpy.data.objects["Motor"]
    scene = bpy.context.scene
    riwayat = []
    for f in range(s.frame_mulai - 6, s.frame_selesai + 1):
        scene.frame_set(max(f, s.frame_mulai))
        riwayat.append(m.matrix_world.translation.copy())
        if f < s.frame_mulai:
            continue
        lambat = sum(riwayat[-7:], Vector()) / len(riwayat[-7:])  # rata-rata 7 frame: tertinggal halus
        lok = lambat + Vector((0.15, -3.0, 1.65))
        sasaran = m.matrix_world.translation + Vector((0, 3.5, 0.95))
        if (f - s.frame_mulai) % 2 == 0 or f == s.frame_selesai:
            _kunci(cam, f, lok, sasaran, 28 if f == s.frame_mulai else None)
    _fokus(cam, "Motor", 2.8)


def _shot5(s):
    """Lensa 85 mm, maju pelan ke label paket di tangan kurir sampai tulisannya
    memenuhi layar. Dari atas bahu kanan kurir (arah tegak lurus label melewati
    kepalanya); atas gambar mengikuti label supaya tulisan mendatar."""
    cam = _kamera(5)
    scene = bpy.context.scene
    m = bpy.data.objects["Motor"]
    pk = bpy.data.objects["Paket"]
    label = bpy.data.objects["Paket_Label_0"]
    for f in sorted(set(range(s.frame_mulai, s.frame_selesai + 1, 6)) | {s.frame_selesai}):
        scene.frame_set(f)
        r = pk.matrix_world.to_3x3()
        pusat = label.matrix_world @ Vector((0, -0.012, 0))  # tengah dua baris tulisan
        normal = (r @ Vector((0, 0, 1))).normalized()
        atas_label = (r @ Vector((0, 1, 0))).normalized()
        kanan = m.matrix_world.to_3x3() @ Vector((1, 0, 0))
        arah = normal  # tegak lurus label (paket sudah dihadapkan ke kamera)
        t = _ease((f - s.frame_mulai) / (s.frame_selesai - 40 - s.frame_mulai))
        jarak = 1.05 + (0.34 - 1.05) * t
        _kunci(cam, f, pusat + arah * jarak, pusat, 85 if f == s.frame_mulai else None, atas=atas_label)
    _fokus(cam, "Paket_Label_0", 4.0)


def _shot6(s):
    """Diam dari belakang kurir, sedikit dari bawah (posisi dari shot.py)."""
    cam = _kamera(6)
    _kunci(cam, s.frame_mulai, cam.location.copy(), cam.location + _arah_kamera(cam), 20)
    _fokus(cam, "Kurir", 4.0, "dada")


def _shot7(s):
    """Dari belakang bahu kanan kurir, maju sangat pelan ke kue."""
    cam = _kamera(7)
    awal = cam.location.copy()
    kue = kota.TITIK["lantai_dalam"] + kota.TITIK["pintu_keluar"] * 0.11 + Vector((0, 0, 0.86))
    for f in range(s.frame_mulai, s.frame_selesai + 1, 12):
        t = _ease((f - s.frame_mulai) / (s.frame_selesai - s.frame_mulai))
        _kunci(cam, f, awal.lerp(kue, 0.12 * t), kue, 35 if f == s.frame_mulai else None)
    _fokus(cam, "Anak_Kue_kue_krim", 2.2)


def _shot8(s):
    """Lebar dan diam, lalu mundur sangat pelan ke ujung gang."""
    cam = _kamera(8)
    pintu = kota.TITIK["pintu_tujuan"]
    awal = Vector((kota.GANG_X + 0.7, pintu.y + 6.5, 1.7))
    akhir = awal + Vector((0, 5.0, 0.25))
    sasaran = pintu + Vector((0.6, 0.6, 1.1))
    for f in range(s.frame_mulai, s.frame_selesai + 1, 8):
        t = _ease((f - 1640) / (s.frame_selesai - 1640))
        _kunci(cam, f, awal.lerp(akhir, t), sasaran, 24 if f == s.frame_mulai else None)
    _fokus(cam, "Pintu_Tujuan", 5.6)


def atur():
    S = waktu.SHOTS
    for fungsi, s in zip((_shot1, _shot2, _shot3, _shot4, _shot5, _shot6, _shot7, _shot8), S):
        fungsi(s)
    bpy.context.scene.frame_set(1)


def periksa_wajah(langkah=2):
    """Hitung frame di mana wajah kurir (tanpa helm) menghadap kamera aktif."""
    scene = bpy.context.scene
    arm = bpy.data.objects["Kurir"]
    tubuh = bpy.data.objects["Kurir_Tubuh"]
    masalah = []
    for f in range(waktu.FRAME_AWAL, waktu.FRAME_AKHIR + 1, langkah):
        scene.frame_set(f)
        cam = scene.camera
        if tubuh.hide_render or arm["helm_di_tangan"] < 0.5:
            continue  # kurir tidak tampil, atau helm (kaca gelap) terpasang
        kepala = arm.matrix_world @ arm.pose.bones["kepala"].head + Vector((0, 0, 0.1))
        muka = (arm.matrix_world.to_3x3() @ arm.pose.bones["kepala"].matrix.to_3x3() @ Vector((0, 0, -1)))
        ke_kamera = (cam.matrix_world.translation - kepala).normalized()
        if muka.normalized().dot(ke_kamera) > 0.2:
            masalah.append(f)
    return masalah


# --------------------------------------------------------------------------
# Versi tegak (1080x1920, YouTube Short)
#
# Tiap kamera lebar diduplikasi dengan aksi animasi yang sama (gerak sama),
# lalu diarahkan (Track To) ke benda penting shot itu, dan lensanya dibuat
# cukup lebar supaya benda itu utuh di bingkai tegak. Hanya dipakai bila
# bangun.py dijalankan dengan --tegak.

def _titik_motor(m):
    mw = m.matrix_world
    return [mw @ Vector((x, y, z)) for x in (-0.34, 0.34) for y in (-1.0, 0.91) for z in (0.0, 1.34)]


def _titik_objek(nama_awal):
    hasil = []
    for o in bpy.data.objects:
        if o.name.startswith(nama_awal) and o.type in ("MESH", "FONT", "CURVES"):
            hasil += [o.matrix_world @ Vector(c) for c in o.bound_box]
    return hasil


def _titik_tulang(arm, tulang=None, lebih=0.0):
    mw = arm.matrix_world
    hasil = []
    for b in arm.pose.bones:
        if tulang is None or b.name in tulang:
            for p in (b.head, b.tail):
                q = mw @ p
                hasil += [q + Vector((dx, dy, dz)) for dx in (-lebih, lebih) for dy in (-lebih, lebih)
                          for dz in (-lebih, lebih)] if lebih else [q]
    return hasil


def _subjek():
    """nomor kamera -> (fungsi titik benda penting, (objek induk sasaran, offset lokal))."""
    m = bpy.data.objects["Motor"]
    kc = bpy.data.objects["Kucing"]
    arm = bpy.data.objects["Kurir"]
    layar = bpy.data.objects["HP_Layar"]
    pk = bpy.data.objects["Paket"]
    anak = bpy.data.objects["Anak"]
    motor = (lambda: _titik_motor(m), (m, Vector((0, 0, 0.7))))
    return {
        "S01_Kamera": motor,
        "S02_Kamera": (lambda: [layar.matrix_world @ Vector((x, y, 0)) for x in (-0.037, 0.037) for y in (-0.079, 0.079)],
                       (layar, Vector((0, 0, 0)))),
        "S02b_Kamera": motor,
        "S03_Kamera": (lambda: _titik_tulang(kc, lebih=0.06), (kc, Vector((0, 0, 0.2)))),
        "S04_Kamera": motor,
        "S05_Kamera": (lambda: _titik_objek("Paket_Label"), (pk, Vector((-0.05, -0.07, 0.165)))),
        "S06_Kamera": (lambda: _titik_tulang(arm, lebih=0.12), (arm, Vector((0, 0, 0.95)))),
        "S07_Kamera": (lambda: _titik_objek("Anak_Kue") + _titik_objek("Api_Lilin"), (anak, Vector((0, 0.22, 0.8)))),
        "S08_Kamera": (lambda: _titik_motor(m) + _titik_objek("Pintu_Tujuan"), (None, None)),
    }


def _rentang_kamera(nama):
    """Frame-frame saat kamera ini aktif (dari marker)."""
    scene = bpy.context.scene
    tanda = sorted(scene.timeline_markers, key=lambda t: t.frame)
    for i, t in enumerate(tanda):
        if t.camera and t.camera.name == nama:
            akhir = tanda[i + 1].frame - 1 if i + 1 < len(tanda) else waktu.FRAME_AKHIR
            return t.frame, akhir
    return None


def _hitung_lensa(cam, titik_fn, rentang, tepi=0.05):
    """Lensa terbesar (paling sempit) yang membuat semua titik benda masuk bingkai."""
    from bpy_extras.object_utils import world_to_camera_view as proyeksi
    scene = bpy.context.scene
    faktor = 1.0
    for f in range(rentang[0], rentang[1] + 1, max(1, (rentang[1] - rentang[0]) // 12)):
        scene.frame_set(f)
        for p in titik_fn():
            q = proyeksi(scene, cam, p)
            if q.z <= 0:
                continue
            for c in (q.x, q.y):
                d = abs(c - 0.5)
                if d > 1e-6:
                    faktor = min(faktor, (0.5 - tepi) / d)
    return faktor


# Kamera lebar yang sudah menatap tepat ke benda penting dengan kemiringan khusus
# (atas gambar = atas layar HP / atas label): tanpa Track To, supaya tulisan tetap mendatar
TANPA_JEJAK = {"S02_Kamera", "S05_Kamera"}


def atur_tegak():
    """Buat kamera tegak untuk tiap kamera lebar dan arahkan marker ke kamera tegak."""
    scene = bpy.context.scene
    subjek = _subjek()
    for nama, (titik_fn, (induk, offset)) in subjek.items():
        lebar = bpy.data.objects[nama]
        rentang = _rentang_kamera(nama)
        cam = lebar.copy()  # aksi animasi objek dipakai bersama: gerak sama persis
        cam.data = lebar.data.copy()
        cam.name = cam.data.name = nama.replace("_Kamera", "_Tegak")
        lebar.users_collection[0].objects.link(cam)
        lensa = lebar.data.lens
        if cam.data.animation_data:
            cam.data.animation_data_clear()  # lensa tegak tetap (dihitung di bawah)
        # Sasaran: empty yang menempel pada benda penting
        sasaran = bpy.data.objects.new(f"{cam.name}_Sasaran", None)
        lebar.users_collection[0].objects.link(sasaran)
        if induk is not None:
            sasaran.parent = induk
            sasaran.location = offset
        else:  # shot 8: titik tengah pintu dan motor
            scene.frame_set(rentang[0])
            pts = titik_fn()
            sasaran.location = sum(pts, Vector()) / len(pts)
        if nama not in TANPA_JEJAK:
            jejak = cam.constraints.new("TRACK_TO")
            jejak.target = sasaran
            jejak.track_axis = "TRACK_NEGATIVE_Z"
            jejak.up_axis = "UP_Y"
        cam.data.lens = lensa
        faktor = _hitung_lensa(cam, titik_fn, rentang)
        cam.data.lens = lensa * min(1.0, faktor)
        cam["lensa_lebar"] = lensa
        for t in scene.timeline_markers:
            if t.camera == lebar:
                t.camera = cam
    scene.frame_set(1)


def periksa_tegak(frame):
    """(nama kamera, utuh?, rentang x, rentang y) benda penting pada frame tertentu."""
    from bpy_extras.object_utils import world_to_camera_view as proyeksi
    scene = bpy.context.scene
    scene.frame_set(frame)
    cam = scene.camera
    nama_lebar = cam.name.replace("_Tegak", "_Kamera")
    titik_fn = _subjek()[nama_lebar][0]
    qs = [proyeksi(scene, cam, p) for p in titik_fn()]
    qs = [q for q in qs if q.z > 0]
    xs, ys = [q.x for q in qs], [q.y for q in qs]
    utuh = bool(qs) and min(xs) >= 0 and max(xs) <= 1 and min(ys) >= 0 and max(ys) <= 1
    return cam.name, utuh, (min(xs), max(xs)), (min(ys), max(ys))
