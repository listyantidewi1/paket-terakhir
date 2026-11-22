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
    """Shot 2: motor di jalan kecil tepi kali (diam untuk sementara).

    Motor ada di tepi kali sampai frame sebelum pra-gulir kain shot 3. Menurut
    storyboard motor sudah keluar frame di akhir shot 2, jadi 3 detik terakhir
    shot 2 bisa dipakai pra-gulir shot 3 di lampu merah.
    Kurir disembunyikan dari render di shot 2: kamera ada di atas setang
    menatap ke depan, dan ponconya belum disimulasikan untuk shot ini.
    """
    s1, s2, s3 = waktu.SHOTS[0], waktu.SHOTS[1], waktu.SHOTS[2]
    scene = bpy.context.scene
    scene.frame_set(s1.frame_selesai)
    jarak1 = m["jarak_tempuh"]
    pra3 = s3.frame_mulai - kurir.MULAI_KAIN
    kali = kota.TITIK["motor_kali"]
    _kunci_motor_diam(m, s2.frame_mulai, kali, jarak1)
    _kunci_motor_diam(m, pra3 - 1, kali, jarak1)
    for nama in ("Kurir_Tubuh", "Kurir_Helm"):
        obj = bpy.data.objects[nama]
        for f, sembunyi in ((s2.frame_mulai - 1, False), (s2.frame_mulai, True),
                            (s2.frame_selesai, True), (s2.frame_selesai + 1, False)):
            obj.hide_render = sembunyi
            obj.keyframe_insert("hide_render", frame=f)
    scene.frame_set(1)


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
    # (Frame shot 1 berikutnya sampai pra - 1 diatur oleh shot2(): motor di tepi kali.)
    _kunci_motor_diam(m, pra, M, jarak1)
    _kunci_motor_diam(m, s3.frame_selesai, M, jarak1)

    # --- Ponco: ponco shot 1 hanya tampil di shot 1; ponco shot 3 punya cache sendiri
    kurir.tampil_di(bpy.data.objects["Kurir_Ponco"], -10000, s1.frame_selesai)
    # Ponco ditenangkan: di shot ini kurir turun dan berjalan, kain tidak boleh terbang
    p3 = kurir.ponco_shot(kol_kurir, arm, "Kurir_Ponco_S3", pra, s3.frame_selesai, tenang=True)
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


def shot67(m, arm, kol_kurir, kol_anak):
    """Shot 6-7 di teras rumah tujuan.

    Shot 6: kurir (dari belakang) berdiri di teras dengan paket di tangan kiri,
    melepas helm dengan tangan kanan, lalu mengetuk pintu tiga kali.
    Shot 7: pintu kayu terbuka perlahan; siluet anak membawa kue dengan tiga
    lilin di ambang pintu; cahaya hangat dari dalam rumah.
    """
    s6, s7 = waktu.SHOTS[5], waktu.SHOTS[6]
    scene = bpy.context.scene
    pra = s6.frame_mulai - kurir.MULAI_KAIN
    luar = kota.TITIK["pintu_keluar"]

    # Kurir: koordinat motor (kurir anak dari motor; motor diam di lampu merah)
    scene.frame_set(pra - 1)
    lama_lok, lama_rot = arm.location.copy(), math.degrees(arm.rotation_euler.z)
    inv = m.matrix_world.inverted()
    teras = inv @ kota.TITIK["teras_tujuan"]
    arah = math.degrees(math.atan2(luar.x, -luar.y))  # menghadap ke dalam rumah
    kurir.kunci_tempat(arm, pra - 1, lama_lok, lama_rot)
    kurir.kunci_tempat(arm, pra, teras, arah)
    kurir.kunci_tempat(arm, s7.frame_selesai, teras, arah)

    # Berdiri saja: tanpa angin dan teredam, tetapi tanpa tarikan ke bentuk lonceng awal
    p67 = kurir.ponco_shot(kol_kurir, arm, "Kurir_Ponco_S67", pra, s7.frame_selesai, tenang=True, goal=0.0)
    kurir.tampil_di(p67, s6.frame_mulai, s7.frame_selesai)

    tp = kurir.terapkan_pose
    jadwal = [
        (pra, "berdiri_paket"), (1153, "berdiri_paket"),
        (1165, "pegang_helm"), (1176, "pegang_helm"), (1184, "angkat_helm"), (1198, "helm_di_tangan_paket"),
        (1212, "ketuk_tarik"), (1218, "ketuk"), (1224, "ketuk_tarik"), (1230, "ketuk"), (1236, "ketuk_tarik"),
        (1242, "ketuk"), (1252, "ketuk_tarik"), (1268, "helm_di_tangan_paket"),
        (s7.frame_selesai, "helm_di_tangan_paket"),
    ]
    for f, nama in jadwal:
        tp(arm, nama, frame=f)

    # Paket mengikuti tangan kiri kurir (koordinat motor), frame demi frame
    pk = bpy.data.objects["Paket"]
    asal_lok, asal_rot = pk.location.copy(), pk.rotation_euler.copy()
    pk.keyframe_insert("location", frame=s6.frame_mulai - 1)
    pk.keyframe_insert("rotation_euler", frame=s6.frame_mulai - 1)
    pb = arm.pose.bones["tangan.L"]
    for f in range(s6.frame_mulai, s7.frame_selesai + 1):
        scene.frame_set(f)
        tangan = arm.matrix_world @ ((pb.head + pb.tail) / 2)
        hadap = arm.matrix_world.to_3x3() @ Vector((1, 0, 0))  # ke arah tengah badan
        pusat = tangan + hadap.normalized() * 0.12 - Vector((0, 0, 0.03))
        pk.location = inv @ (pusat - Vector((0, 0, 0.08)))
        pk.rotation_euler = (0, 0, arm.matrix_world.to_euler().z - m.matrix_world.to_euler().z)
        pk.keyframe_insert("location", frame=f)
        pk.keyframe_insert("rotation_euler", frame=f)
    pk.location, pk.rotation_euler = asal_lok, asal_rot
    pk.keyframe_insert("location", frame=s7.frame_selesai + 1)
    pk.keyframe_insert("rotation_euler", frame=s7.frame_selesai + 1)

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
    scene.frame_set(1)
