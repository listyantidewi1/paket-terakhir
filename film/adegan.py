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
from mathutils import Euler, Vector

from . import dunia_kota as kota
from . import anak, kucing, kurir, waktu

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


def shot2(m, arm):
    """Shot 2, tiga potongan (detik 7-20):
    7-10  close-up layar HP; motor melaju di jalan kecil (kurir tidak di gambar).
    10-17 kamera di seberang kali: motor berbelok kanan menuju kali dan mengerem
          tepat di bibir beton; helm menoleh ke kali, ke HP, lalu ke kali lagi.
    17-20 kamera yang sama: motor berbelok kiri ke jalan cabang dan hilang di
          balik tembok; kali tetap di gambar.
    """
    s2 = waktu.SHOTS[1]
    X = kota.KALI_X
    motor_jalan = __import__("film.motor", fromlist=["animasi_jalan"]).animasi_jalan
    motor_jalan(m, [
        (s2.frame_mulai, (X - 3.0, -2.0, 0.0), 0.0),
        (262, (X - 3.0, 24.0, 0.0), 0.0, "linear"),           # sekitar 25 km/jam
        (MOTOR_REM, (X - 1.6, 28.3, 0.0), -38.0, "keluar"),    # belok kanan, mengerem di bibir beton
        (BELOK_KIRI, (X - 1.6, 28.3, 0.0), -38.0, "linear"),   # diam: menoleh kali, HP, kali
        (452, (X - 12.0, 32.0, 0.0), 90.0, "masuk"),           # belok kiri ke jalan cabang
        (s2.frame_selesai, (X - 20.0, 32.0, 0.0), 90.0, "linear"),
    ], halus=False)
    tp = kurir.terapkan_pose
    for f, nama in ((s2.frame_mulai, "duduk_motor"), (MOTOR_REM, "duduk_motor"), (300, "lihat_kali"),
                    (325, "lihat_kali"), (333, "lihat_hp"), (350, "lihat_hp"), (358, "lihat_kali"),
                    (400, "lihat_kali"), (BELOK_KIRI, "duduk_motor")):
        tp(arm, nama, frame=f)
    # Potongan close-up HP: kurir tidak tampil (kamera berada di tempat dadanya)
    for nama in ("Kurir_Tubuh", "Kurir_Helm", "Kurir_Rambut", "Kurir_Ponco"):
        obj = bpy.data.objects[nama]
        for f, sembunyi in ((s2.frame_mulai - 1, False), (s2.frame_mulai, True),
                            (POTONG_KALI - 1, True), (POTONG_KALI, False)):
            obj.hide_render = sembunyi
            obj.keyframe_insert("hide_render", frame=f)


POTONG_KALI = 241  # detik 10: dari close-up HP ke kamera di seberang kali
BELOK_KIRI = 409  # detik 17: motor mulai berbelok kiri
MOTOR_REM = 292  # frame motor berhenti di bibir beton


def shot45(m, arm, kol_kurir):
    """Shot 4-5: motor menyusuri Gang Melati lalu berhenti di depan rumah tujuan;
    di shot 5 tutup boks terbuka (label paket di dalam). Kurir duduk di motor
    dengan ponco tanpa simulasi; di shot 2 juga.
    """
    s2, s4, s5 = waktu.SHOTS[1], waktu.SHOTS[3], waktu.SHOTS[4]
    teras = kota.TITIK["teras_tujuan"]
    berhenti = Vector((kota.GANG_X - 0.7, teras.y, 0.05))
    motor_jalan = __import__("film.motor", fromlist=["animasi_jalan"]).animasi_jalan
    motor_jalan(m, [
        (s4.frame_mulai, (kota.GANG_X - 0.2, -16.0, 0.05), 0.0),
        (955, tuple(berhenti), 0.0, "keluar"),  # melambat sampai berhenti di depan pagar hijau
        (waktu.SHOTS[-1].frame_selesai, tuple(berhenti), 0.0, "linear"),
    ], halus=False)
    kurir.kunci_tempat(arm, s4.frame_mulai - 1, (-0.9, -0.9, 0), -409)
    kurir.kunci_tempat(arm, s4.frame_mulai, (0, 0, 0), 0)
    kurir.terapkan_pose(arm, "duduk_motor", frame=s4.frame_mulai)
    # Tutup boks terbuka selama shot 5 (engsel di belakang, berputar pada sumbu X)
    tutup = bpy.data.objects["Motor_Boks_Tutup"]
    for f, sudut in ((s5.frame_mulai - 1, 0.0), (s5.frame_mulai, 105.0), (s5.frame_selesai, 105.0),
                     (s5.frame_selesai + 1, 0.0)):
        tutup.rotation_euler = (math.radians(sudut), 0, 0)
        tutup.keyframe_insert("rotation_euler", index=0, frame=f)
    _konstan_jalur(tutup)


TEMPAT_S5 = Vector((0.0, -1.5, 0.0))  # kurir di belakang boks motor, menghadap ke depan (+Y)
# Paket dimiringkan ke kanan-atas (ke arah lampu teras dan kamera) supaya label terbaca;
# arah muka label dalam koordinat motor
ARAH_LABEL = Vector((0.9, 0.25, 0.9)).normalized()


def shot5(m, arm):
    """Shot 5: kurir memegang paket dengan dua tangan, label basah sedikit miring,
    diterangi lampu teras rumah tujuan yang hangat."""
    s5 = waktu.SHOTS[4]
    scene = bpy.context.scene
    kurir.kunci_tempat(arm, s5.frame_mulai - 1, (0, 0, 0), 0)
    kurir.terapkan_pose(arm, "duduk_motor", frame=s5.frame_mulai - 1)  # tahan duduk sepanjang shot 4
    for f in (s5.frame_mulai, s5.frame_selesai):
        kurir.kunci_tempat(arm, f, TEMPAT_S5, 0)
        kurir.terapkan_pose(arm, "baca_label", frame=f)
    # Paket mengikuti kedua tangan, miring ke arah kurir
    pk = bpy.data.objects["Paket"]
    asal_lok, asal_rot = pk.location.copy(), pk.rotation_euler.copy()
    pk.keyframe_insert("location", frame=s5.frame_mulai - 1)
    pk.keyframe_insert("rotation_euler", frame=s5.frame_mulai - 1)
    pb = arm.pose.bones
    inv = None
    rot = Vector((0, 0, 1)).rotation_difference(ARAH_LABEL).to_matrix()
    for f in sorted(set(range(s5.frame_mulai, s5.frame_selesai + 1, 2)) | {s5.frame_selesai}):
        scene.frame_set(f)
        inv = m.matrix_world.inverted()
        tangan = [arm.matrix_world @ ((pb[f"tangan.{s}"].head + pb[f"tangan.{s}"].tail) / 2) for s in "LR"]
        pusat = (tangan[0] + tangan[1]) / 2 + Vector((0, 0, 0.02))
        pk.location = inv @ pusat - rot @ Vector((0, 0, 0.08))
        pk.rotation_euler = rot.to_euler()
        pk.keyframe_insert("location", frame=f)
        pk.keyframe_insert("rotation_euler", frame=f)
    pk.location, pk.rotation_euler = asal_lok, asal_rot
    for f in (s5.frame_selesai + 1,):
        pk.keyframe_insert("location", frame=f)
        pk.keyframe_insert("rotation_euler", frame=f)
    # Lampu teras rumah tujuan: sorot hangat ke paket, hanya di shot 5 dan hanya
    # menerangi paket dan kurir (shot lain tidak berubah)
    teras = bpy.data.objects[f"Teras_No{kota.RUMAH_TUJUAN:02d}"]
    data = bpy.data.lights.new("Lampu_Teras_Label", type="SPOT")
    data.color = (1.0, 0.68, 0.38)
    data.spot_size = math.radians(35)
    data.spot_blend = 0.5
    data.shadow_soft_size = 0.08
    sorot = bpy.data.objects.new("Lampu_Teras_Label", data)
    teras.users_collection[0].objects.link(sorot)
    sorot.location = teras.matrix_world.translation
    scene.frame_set(1056)
    sasaran = m.matrix_world @ (TEMPAT_S5 + Vector((0, 0.36, 1.12)))
    sorot.rotation_euler = (sasaran - sorot.location).to_track_quat("-Z", "Y").to_euler()
    for f, daya in ((s5.frame_mulai - 1, 0.0), (s5.frame_mulai, 1400.0), (s5.frame_selesai, 1400.0),
                    (s5.frame_selesai + 1, 0.0)):
        data.energy = daya
        data.keyframe_insert("energy", frame=f)
    terima = bpy.data.collections.new("Diterangi_Lampu_Label")
    for o in [pk] + list(pk.children_recursive) + [bpy.data.objects["Kurir_Tubuh"]]:
        if o.type in ("MESH", "FONT"):
            terima.objects.link(o)
    sorot.light_linking.receiver_collection = terima
    scene.frame_set(1)


def _konstan_jalur(obj):
    _konstan(obj)


def shot8(arm):
    """Shot 8: kurir sudah masuk rumah; pintu menutup perlahan, gang kembali gelap."""
    s8 = waktu.SHOTS[7]
    for nama in ("Kurir_Tubuh", "Kurir_Helm", "Kurir_Rambut", "Kurir_Ponco"):
        obj = bpy.data.objects[nama]
        for f, sembunyi in ((s8.frame_mulai - 1, False), (s8.frame_mulai, True)):
            obj.hide_render = sembunyi
            obj.keyframe_insert("hide_render", frame=f)
    pintu = bpy.data.objects["Pintu_Tujuan"]
    buka = math.radians(pintu["buka_derajat"])
    for f, sudut in ((1640, buka), (1700, 0.0)):
        pintu.rotation_euler = (0, 0, sudut)
        pintu.keyframe_insert("rotation_euler", index=2, frame=f)


def shot3(m, arm, kc, kol_kurir):
    s3 = waktu.SHOTS[2]
    pra = s3.frame_mulai  # tanpa simulasi kain: motor dan kurir pindah tepat di awal shot 3
    scene = bpy.context.scene
    M = kota.TITIK["motor_lampu_merah"]

    # --- Motor: setelah shot 1 berhenti (kecepatan 0), lalu dipindah ke garis
    # henti sebelum pra-gulir kain shot 3; diam sepanjang shot 3.
    s1 = waktu.SHOTS[0]
    scene.frame_set(s1.frame_selesai)
    akhir1, jarak1 = m.location.copy(), m["jarak_tempuh"]
    # (Frame shot 1 berikutnya sampai pra - 1 diatur oleh shot2(): motor di tepi kali.)
    _kunci_motor_diam(m, pra, M, jarak1)
    _kunci_motor_diam(m, s3.frame_selesai, M, jarak1)


    # --- Kurir duduk lagi (pra-gulir kain seperti shot 1), lalu adegan
    tp = kurir.terapkan_pose
    tp(arm, "duduk_motor", frame=s1.frame_selesai)
    tp(arm, "duduk_motor", frame=pra - 1)
    kurir.kunci_tempat(arm, pra - 1, (0, 0, 0), 0)
    tp(arm, "duduk_motor", frame=pra)
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

    # Saat kurir turun, ponco jangan tersangkut di jok atau boks (gesekannya
    # tinggi agar ponco tidak merosot ketika duduk): tumbukan motor dimatikan.
    for o in m.children_recursive:
        if o.type == "MESH" and any(md.type == "COLLISION" for md in o.modifiers):
            for f, aktif in ((GERAK_LAGI + 5, True), (GERAK_LAGI + 6, False), (s3.frame_selesai, False),
                             (s3.frame_selesai + 1, True)):
                o.collision.use = aktif
                o.keyframe_insert("collision.use", frame=f)

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


def _anak_siluet(kol_anak):
    """Anak hanya disinari dari dalam rumah (dari belakang): siluet gelap.

    Semua lampu lain (lampu teras, lampu jalan, cahaya bulan, dan lainnya)
    memakai light linking yang mengecualikan tubuh anak. Lampu lilin sudah
    hanya menerangi kue. Ruangan dibuat lebih terang dan hangat.
    """
    tubuh = [o for o in bpy.data.collections["Anak_Siluet"].objects]
    kecuali = bpy.data.collections.new("Anak_Tanpa_Cahaya_Luar")
    for o in tubuh:
        kecuali.objects.link(o)
    for item in kecuali.collection_objects:
        item.light_linking.link_state = "EXCLUDE"
    dalam = ("Rumah_Tujuan_Belakang", "Rumah_Tujuan_Lampu")
    for L in bpy.data.objects:
        if L.type != "LIGHT" or L.name in dalam or L.name.startswith("Lampu_Lilin"):
            continue
        if L.light_linking.receiver_collection is None:
            L.light_linking.receiver_collection = kecuali
    bpy.data.objects["Rumah_Tujuan_Belakang"].data.energy = 260
    bpy.data.objects["Rumah_Tujuan_Lampu"].data.energy = 220


def shot67(m, arm, kol_kurir, kol_anak):
    """Shot 6-7 di teras rumah tujuan.

    Shot 6: kurir (dari belakang) berdiri di teras dengan paket di tangan kiri,
    melepas helm dengan tangan kanan, lalu mengetuk pintu tiga kali.
    Shot 7: pintu kayu terbuka perlahan; siluet anak membawa kue dengan tiga
    lilin di ambang pintu; cahaya hangat dari dalam rumah.
    """
    s6, s7 = waktu.SHOTS[5], waktu.SHOTS[6]
    scene = bpy.context.scene
    pra = s6.frame_mulai  # tanpa simulasi kain: kurir baru pindah ke teras di awal shot 6
    luar = kota.TITIK["pintu_keluar"]

    # Kurir: koordinat motor (kurir anak dari motor; motor diam di lampu merah)
    scene.frame_set(pra - 1)
    lama_lok, lama_rot = arm.location.copy(), math.degrees(arm.rotation_euler.z)
    inv = m.matrix_world.inverted()
    teras = inv @ kota.TITIK["teras_tujuan"]
    arah = math.degrees(math.atan2(luar.x, -luar.y))  # menghadap ke dalam rumah
    kurir.kunci_tempat(arm, pra - 1, lama_lok, lama_rot)
    kurir.kunci_tempat(arm, pra, teras, arah)
    kurir.kunci_tempat(arm, s6.frame_selesai, teras, arah)
    # Shot 7: kurir 20 cm ke kirinya (potongan shot), ambang pintu di kanannya lebih terbuka
    kiri = inv.to_3x3() @ (-luar).cross(Vector((0, 0, 1))).normalized() * -0.2
    kurir.kunci_tempat(arm, s7.frame_mulai, teras + kiri, arah)
    kurir.kunci_tempat(arm, s7.frame_selesai, teras + kiri, arah)


    tp = kurir.terapkan_pose
    # Helm sudah dilepas sejak awal shot 6, tergantung di pergelangan kiri;
    # paket di tangan kiri; tiga ketukan dengan tangan kanan.
    jadwal = [
        (pra, "teras_paket"), (1153, "teras_paket"), (1190, "teras_paket"),
        (1200, "ketuk_tarik"), (1206, "ketuk"), (1212, "ketuk_tarik"), (1218, "ketuk"), (1224, "ketuk_tarik"),
        (1230, "ketuk"), (1240, "ketuk_tarik"), (1256, "teras_paket"),
        (s7.frame_selesai, "teras_paket"),
    ]
    for f, nama in jadwal:
        tp(arm, nama, frame=f)

    # Paket: tangan kiri memegang helm dan tangan kanan mengetuk, jadi paket
    # disembunyikan dari render selama shot 6-7 (belum ada tangan yang memegangnya).
    pk = bpy.data.objects["Paket"]
    for o in [pk] + list(pk.children_recursive):
        for f, sembunyi in ((s6.frame_mulai - 1, False), (s6.frame_mulai, True),
                            (s7.frame_selesai, True), (s7.frame_selesai + 1, False)):
            o.hide_render = sembunyi
            o.keyframe_insert("hide_render", frame=f)

    # Pintu terbuka perlahan (3 detik) ke dalam rumah
    pintu = bpy.data.objects["Pintu_Tujuan"]
    buka = math.radians(pintu["buka_derajat"])
    for f, sudut in ((s7.frame_mulai + 3, 0.0), (s7.frame_mulai + 73, buka), (s7.frame_selesai, buka)):
        pintu.rotation_euler = (0, 0, sudut)
        pintu.keyframe_insert("rotation_euler", index=2, frame=f)

    # Anak di ambang pintu, menghadap teras, membawa kue; api lilin bergoyang
    arah_anak = math.degrees(math.atan2(-luar.x, luar.y))
    akar, api, lampu = anak.buat_anak(kol_anak, kota.TITIK["lantai_dalam"], arah_anak)
    anak.goyang_api(api, lampu, s6.frame_mulai, s7.frame_selesai)
    _anak_siluet(kol_anak)
    scene.frame_set(1)
