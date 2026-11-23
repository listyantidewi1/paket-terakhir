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


# Shot 2b: kamera diam dan rendah di seberang kali (bibir beton timur), menatap
# titik motor mengerem; lensa 35 mm
# Di garis hadap motor saat mengerem (arah -38 derajat): motor datang menuju kamera,
# lampu depan menyorot air ke arah kamera; saat belok kiri motor hilang di balik
# tembok utara simpang. Relatif terhadap (KALI_X, 28.3, 0).
SHOT2B_LOK = Vector((9.9, 14.6, 0.85))
SHOT2B_SASARAN = Vector((-1.6, 0.0, 0.75))


def _shot2(s):
    """Shot 2 dalam dua kamera:
    a) 7-10 dtk: close-up layar HP (lensa 50 mm, f/2), mengikuti HP di setang;
       jalan di belakangnya kabur.
    b) 10-20 dtk: kamera diam dan rendah di seberang kali, lensa 35 mm."""
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
    _kunci(cam2, adegan.POTONG_KALI, dasar + SHOT2B_LOK, dasar + SHOT2B_SASARAN, 35)
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
