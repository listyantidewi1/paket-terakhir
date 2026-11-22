"""Koreografi per shot: siapa di mana, kapan, dengan pose apa.

Shot 3 (frame 481-792), sesuai STORYBOARD.md:
    lampu merah, motor berhenti di garis henti; kucing oren melompat ke boks
    dan duduk. Lampu berubah hijau; kucing tidak bergerak. JEDA 1 detik penuh:
    kurir dan kucing sama-sama diam. Kurir turun, mengangkat kucing dengan dua
    tangan, menaruhnya di bangku warung; kucing langsung duduk rapi. Kurir
    kembali ke motor.
"""

import math

import bpy
from mathutils import Vector

from . import dunia_kota as kota
from . import kucing, kurir, waktu

# Jadwal shot 3 (frame film). JEDA: lampu hijau di HIJAU, lalu 24 frame
# (1 detik pada 24 fps) tanpa gerakan apa pun dari kurir maupun kucing.
HIJAU = 560
JEDA = 24
GERAK_LAGI = HIJAU + JEDA  # 584: frame pertama yang boleh bergerak lagi
TENANG = 556  # sejak frame ini kucing sudah benar-benar diam (ekor berhenti)

BOKS_ATAS = Vector((0, -0.745, 1.335))  # tengah tutup boks, koordinat motor
BANGKU = kota.TITIK["bangku_warung"] + Vector((0, 0, 0.47))  # dudukan bangku, koordinat dunia


def _kunci_motor_diam(m, frame, lokasi, jarak):
    m.location = lokasi
    m.rotation_euler = (0, 0, 0)
    m["jarak_tempuh"] = jarak
    m["kecepatan"] = 0.0
    for jalur in ("location", "rotation_euler", '["jarak_tempuh"]', '["kecepatan"]'):
        m.keyframe_insert(jalur, frame=frame)


def _lampu_hijau(frame):
    """Lampu lalu lintas berganti merah -> hijau tepat di `frame`."""
    for nama, sebelum, sesudah in (("ll_merah_nyala", 2.5, 0.08), ("ll_hijau_mati", 0.08, 2.5)):
        sok = bpy.data.materials[nama].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for f, v in ((frame - 1, sebelum), (frame, sesudah)):
            sok.default_value = v
            sok.keyframe_insert("default_value", frame=f)
    cahaya = bpy.data.objects["LL_Cahaya"].data
    for f, w in ((frame - 1, (1.0, 0.05, 0.03)), (frame, (0.1, 1.0, 0.5))):
        cahaya.color = w
        cahaya.keyframe_insert("color", frame=f)


def _konstan(id_data):
    """Semua keyframe sebuah ID menjadi CONSTANT (tidak ada gerak di antara kunci)."""
    from bpy_extras import anim_utils
    ad = id_data.animation_data
    if not ad or not ad.action:
        return
    for fc in anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot).fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def _kunci_kucing(kc, frame, lokasi, arah, pose=None, ayun=None):
    kc.location = lokasi
    kc.rotation_euler = (0, 0, math.radians(arah))
    kc.keyframe_insert("location", frame=frame)
    kc.keyframe_insert("rotation_euler", index=2, frame=frame)
    if pose:
        kucing.terapkan_pose(kc, pose, frame=frame, ayun=ayun)
    elif ayun is not None:
        kc["ayun_ekor"] = ayun
        kc.keyframe_insert('["ayun_ekor"]', frame=frame)


def _ke_dunia(m, p):
    return m.matrix_world @ Vector(p)


def shot3(m, arm, kc, kol_kurir):
    s3 = waktu.SHOTS[2]
    pra = s3.frame_mulai - kurir.MULAI_KAIN
    scene = bpy.context.scene
    M = kota.TITIK["motor_lampu_merah"]

    # --- Motor: setelah shot 1 berhenti (kecepatan 0), lalu dipindah ke garis
    # henti sebelum pra-gulir kain shot 3; diam sepanjang shot 3.
    s1 = waktu.SHOTS[0]
    scene.frame_set(s1.frame_selesai)
    akhir1, jarak1 = m.location.copy(), m["jarak_tempuh"]
    _kunci_motor_diam(m, s1.frame_selesai + 1, akhir1, jarak1)
    _kunci_motor_diam(m, pra - 1, akhir1, jarak1)
    _kunci_motor_diam(m, pra, M, jarak1)
    _kunci_motor_diam(m, s3.frame_selesai, M, jarak1)

    # --- Ponco: ponco shot 1 hanya tampil di shot 1; ponco shot 3 punya cache sendiri
    kurir.tampil_di(bpy.data.objects["Kurir_Ponco"], -10000, s1.frame_selesai)
    p3 = kurir.ponco_shot(kol_kurir, arm, "Kurir_Ponco_S3", pra, s3.frame_selesai)
    kurir.tampil_di(p3, s3.frame_mulai, s3.frame_selesai)

    # --- Kurir duduk lagi (pra-gulir kain seperti shot 1), lalu adegan
    tp = kurir.terapkan_pose
    tp(arm, "duduk_motor", frame=s1.frame_selesai)
    tp(arm, "duduk_motor", frame=pra - 1)
    kurir.kunci_tempat(arm, pra - 1, (0, 0, 0), 0)
    tp(arm, "duduk_tangan_turun", frame=pra)
    tp(arm, "duduk_motor", frame=pra + 30)
    tp(arm, "duduk_motor", frame=524)
    tp(arm, "menoleh", frame=538)  # menoleh ke belakang, melihat kucing di boks
    tp(arm, "menoleh", frame=GERAK_LAGI - 1)  # tahan sepanjang jeda
    kurir.kunci_tempat(arm, GERAK_LAGI - 1, (0, 0, 0), 0)
    # Turun dari motor ke sisi kiri
    tp(arm, "turun", frame=604)
    kurir.kunci_tempat(arm, 604, (0, 0, 0), 0)
    tp(arm, "berdiri", frame=618)
    kurir.kunci_tempat(arm, 618, (-0.5, -0.25, 0), 0)
    # Melangkah ke samping boks, menghadap boks (+X motor)
    tp(arm, "jalan_kiri", frame=626)
    tp(arm, "jalan_kanan", frame=634)
    tp(arm, "berdiri", frame=640)
    kurir.kunci_tempat(arm, 640, (-0.45, -0.75, 0), -90)
    tp(arm, "ambil_kucing", frame=650)  # tangan memegang kucing
    tp(arm, "bawa_kucing", frame=664)  # diangkat ke depan dada
    kurir.kunci_tempat(arm, 664, (-0.45, -0.75, 0), -90)
    # Berjalan ke bangku sambil menggendong, berbalik menghadap bangku (-X)
    bangku_motor = BANGKU - M
    tujuan = (bangku_motor.x + 0.55, bangku_motor.y, 0)
    jalur = [(676, (-0.9, -1.3, 0), -180), (716, tujuan, -270)]
    for f, (lok, arah) in zip((676, 716), [(j[1], j[2]) for j in jalur]):
        kurir.kunci_tempat(arm, f, lok, arah)
    for i, f in enumerate(range(670, 712, 10)):
        tp(arm, "jalan_bawa_kiri" if i % 2 == 0 else "jalan_bawa_kanan", frame=f)
    tp(arm, "bawa_kucing", frame=716)
    tp(arm, "taruh_kucing", frame=730)  # membungkuk, kucing di dudukan bangku
    tp(arm, "taruh_kucing", frame=734)
    tp(arm, "berdiri", frame=748)
    kurir.kunci_tempat(arm, 748, tujuan, -270)
    # Kembali ke motor
    kurir.kunci_tempat(arm, s3.frame_selesai, (-0.9, -0.9, 0), -409)
    for i, f in enumerate(range(756, s3.frame_selesai + 1, 11)):
        tp(arm, "jalan_kiri" if i % 2 == 0 else "jalan_kanan", frame=f)

    # --- Lampu lalu lintas
    _lampu_hijau(HIJAU)

    # --- Kucing (koordinat dunia; tidak menjadi anak motor)
    mw = m.matrix_world.copy()
    scene.frame_set(s3.frame_mulai)
    mw = m.matrix_world.copy()
    boks = mw @ BOKS_ATAS
    mulai = Vector((boks.x - 1.2, boks.y - 1.3, 0.0))
    dekat = Vector((boks.x - 0.85, boks.y - 0.95, 0.0))
    arah_boks = math.degrees(math.atan2(-(boks.x - dekat.x), boks.y - dekat.y))
    _kunci_kucing(kc, s3.frame_mulai - 1, mulai, arah_boks, "berdiri", ayun=6)
    _kunci_kucing(kc, 481, mulai, arah_boks, "berdiri", ayun=6)
    _kunci_kucing(kc, 492, dekat, arah_boks, "berdiri", ayun=5)
    _kunci_kucing(kc, 498, dekat, arah_boks, "jongkok", ayun=2)
    # Lompatan: lintasan parabola per frame dari tanah ke tutup boks
    f0, f1 = 500, 512
    for f in range(f0, f1 + 1):
        t = (f - f0) / (f1 - f0)
        p = dekat.lerp(boks, t) + Vector((0, 0, 0.35 * 4 * t * (1 - t)))
        kc.location = p
        kc.keyframe_insert("location", frame=f)
    kucing.terapkan_pose(kc, "lompat", frame=505, ayun=0)
    _kunci_kucing(kc, f1, boks, arah_boks, "berdiri", ayun=3)
    _kunci_kucing(kc, 522, boks, -150, "duduk", ayun=4)  # berbalik dan duduk di atas boks
    _kunci_kucing(kc, 548, boks, -150, "duduk", ayun=4)
    _kunci_kucing(kc, TENANG, boks, -150, "duduk", ayun=0)  # ekor berhenti; diam sampai jeda usai
    _kunci_kucing(kc, GERAK_LAGI - 1, boks, -150, "duduk", ayun=0)
    _kunci_kucing(kc, 648, boks, -150, "duduk", ayun=0)  # belum disentuh

    # Digendong: kucing mengikuti titik tengah kedua tangan kurir, frame demi frame
    # Di awal (650-658) kucing berpindah halus dari boks ke tangan dan berputar
    # mengikuti arah kurir; di akhir (722-731) menyatu halus ke dudukan bangku.
    lepas = 732
    pb = arm.pose.bones
    for f in range(650, lepas):
        scene.frame_set(f)
        tangan = [arm.matrix_world @ ((pb[f"tangan.{s}"].head + pb[f"tangan.{s}"].tail) / 2) for s in "LR"]
        tengah = (tangan[0] + tangan[1]) / 2 - Vector((0, 0, 0.2))  # badan kucing 0,2 m di atas titik pusatnya
        arah_kurir = math.degrees(arm.matrix_world.to_euler().z)
        masuk = min(1.0, (f - 650) / 8)
        keluar = max(0.0, (f - 722) / 10)
        lok = boks.lerp(tengah, masuk).lerp(BANGKU, keluar)
        arah = -150 + (((arah_kurir + 150 + 180) % 360) - 180) * masuk
        kc.location = lok
        kc.rotation_euler = (0, 0, math.radians(arah))
        kc.keyframe_insert("location", frame=f)
        kc.keyframe_insert("rotation_euler", index=2, frame=f)
    kucing.terapkan_pose(kc, "digendong", frame=658, ayun=2)
    # Ditaruh di bangku, langsung duduk rapi menghadap jalan
    _kunci_kucing(kc, lepas, BANGKU, -90, "duduk_rapi", ayun=0)
    _kunci_kucing(kc, 760, BANGKU, -90, "duduk_rapi", ayun=3)
    _kunci_kucing(kc, s3.frame_selesai, BANGKU, -90, "duduk_rapi", ayun=3)
    scene.frame_set(1)


def periksa_jeda(arm, kc, frame_awal=HIJAU, panjang=JEDA):
    """Kembalikan perubahan terbesar (meter) pada tulang kurir dan kucing selama jeda."""
    scene = bpy.context.scene

    def keadaan():
        titik = []
        for obj in (arm, kc):
            mw = obj.matrix_world
            for b in obj.pose.bones:
                titik += [mw @ b.head, mw @ b.tail]
        return titik

    scene.frame_set(frame_awal)
    awal = keadaan()
    terbesar = 0.0
    for f in range(frame_awal + 1, frame_awal + panjang):
        scene.frame_set(f)
        terbesar = max(terbesar, max((a - b).length for a, b in zip(awal, keadaan())))
    scene.frame_set(frame_awal + panjang)
    sesudah = max((a - b).length for a, b in zip(awal, keadaan()))
    return terbesar, sesudah
