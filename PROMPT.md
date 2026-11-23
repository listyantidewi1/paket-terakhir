# Prompt di video "Paket Terakhir Malam Ini"

Semua prompt yang diketik di video tutorial ada di sini, bernomor sesuai bab.
Di video, label di layar menyebut nomornya, misalnya **Prompt 4.3**.
Salin prompt dengan tombol salin di pojok kotak, lalu tempel di Claude Code.

Hasil Claude Code bisa berbeda sedikit darimu karena AI tidak selalu menjawab
sama. Itu wajar. Bandingkan hasilmu dengan kode di repo ini, dan perbaiki
dengan prompt lanjutan seperti yang dilakukan di video.

Isi `CLAUDE.md` diketik sendiri (bab 2). Salinannya ada di berkas
[CLAUDE.md](CLAUDE.md).

## Bab 2

### Prompt 2.1 · Storyboard pertama

```text
Saya ingin membuat film animasi pendek 75 detik di Blender berjudul
"Paket Terakhir Malam Ini", tanpa narasi.
Cerita: pada malam hujan di Kota Senja, Mas Adit, kurir motor ber-helm putih
dan ber-jas hujan ponco kuning, mengantar paket terakhirnya. GPS menyuruhnya
belok ke arah kali, seekor kucing oren duduk di atas paketnya saat lampu merah,
dan semua rumah di Gang Melati berpagar hijau. Saat tiba, label paket berbunyi
"Penerima: Ayah". Pintu terbuka, anaknya membawa kue ulang tahun untuk dia.
Gaya: realistis, malam yang basah. Wajah kurir tidak pernah terlihat.

Tulis STORYBOARD.md berisi tabel 8 shot: nomor, detik mulai-selesai, gambar,
gerakan kamera, dan suara. Jangan menulis kode dulu.
```

### Prompt 2.2 · Memperbaiki storyboard: lelucon harus dijelaskan

```text
Ada tiga hal yang perlu diubah.
1. GPS adalah lelucon. GPS menyuruh "Belok kanan", padahal di kanan ada kali.
   Motor berhenti mendadak tepat di tepi kali, GPS mengulang "Belok kanan.",
   lalu kurir berbelok ke kiri. Suara GPS tetap dipakai.
2. Kucing tidak mau turun saat lampu hijau. Beri jeda 1 detik hening, baru
   kurir mengangkat kucing dengan hati-hati dan menaruhnya di bangku warung.
3. Wajah anak juga tidak boleh terlihat. Anak berdiri membelakangi cahaya
   rumah, jadi hanya siluetnya yang tampak. Kalimatnya hanya satu:
   "Selamat ulang tahun, Ayah!"
Atur ulang detiknya. Tetap 8 shot dan total tetap 75 detik.
```

## Bab 3

### Prompt 3.1 · Kerangka film dan alat cek

```text
Baca STORYBOARD.md dan CLAUDE.md. Buat kerangka film:
- bangun.py: membangun film.blend dari nol, memanggil modul di folder film/.
- film/waktu.py: daftar shot dari storyboard (frame mulai dan selesai, 24 fps).
- film/shot.py: satu kamera per shot, berganti otomatis lewat marker di timeline.
- cek.py: render beberapa frame 480p dengan sedikit sampel, lalu gabungkan
  menjadi satu lembar kontak cek/lembar.png berisi nomor shot dan frame.
Untuk sekarang setiap shot cukup berisi lantai, satu kubus, dan tulisan nomor shot.
Jangan membuat isi adegan dulu.
```

## Bab 4

### Prompt 4.1 · Mengunduh aset dari Poly Haven

```text
Buat aset.py yang mengunduh dari Poly Haven (lewat api.polyhaven.com) ke folder aset/:
- satu langit malam (HDRI) untuk pencahayaan kota,
- tekstur aspal, dinding plester, bata, genteng, dan logam berkarat (resolusi 2k).
Lewati aset yang sudah ada. Catat setiap aset di ASET.md: nama, alamat halaman,
lisensi. Tunjukkan daftar pilihannya ke saya sebelum mengunduh.
```

### Prompt 4.2 · Memilih ulang langit malam

```text
Ganti langit malamnya. cobblestone_street_night berisi gedung-gedung Eropa
yang nanti ikut terpantul di genangan, padahal kota kita ada di Indonesia.
Pakai moonless_golf, langit malam gelap dengan cahaya kota di cakrawala.
Tambahkan juga satu tekstur beton untuk tepi kali. Sisanya sudah oke,
silakan unduh.
```

### Prompt 4.3 · Kota malam yang basah

```text
Buat film/dunia_kota.py untuk kota malam yang basah oleh hujan, sesuai STORYBOARD.md:
- Jl. Kenanga (lajur kiri) dengan lampu jalan natrium oranye, ruko berkanopi,
  kabel listrik melintang, polisi tidur kuning-hitam, perempatan dengan lampu
  lalu lintas, dan warung yang sudah tutup dengan bangku kayu (shot 1 dan 3).
- Jalan kecil dengan kali di sisi kanan, tepinya beton tanpa pagar (shot 2).
- Gang Melati: sepuluh rumah berderet, semuanya berpagar hijau, nomor rumah
  sebagian tertutup tanaman. Bentuk rumah bervariasi dengan seed tetap.
- Aspal basah dengan genangan yang memantulkan cahaya, hujan, dan kabut tipis.
- Pakai langit malam dan tekstur dari aset/.
Setelah selesai, jalankan cek.py untuk shot 1, 2, 3, dan 4.
```

### Prompt 4.4 · Genangan yang lebih wajar

```text
Genangan di shot 1 seperti cermin besar yang menutupi seluruh jalan.
Buat genangan lebih kecil dan tidak beraturan, tepinya lembut, dan permukaannya
bergetar sedikit terkena hujan. Aspal di sekitarnya tetap basah tetapi kasar.
Jangan ubah posisi benda apa pun. Jalankan cek.py untuk shot 1 dan 2.
```

### Prompt 4.5 · Warna cahaya malam

```text
Gambarnya terlalu gelap dan hampir semuanya cokelat. Buat bayangan dan langit
sedikit kebiruan, lampu natrium menjadi kolam cahaya oranye yang jelas di aspal,
dan jendela rumah berwarna hangat. Lampu lalu lintas harus terlihat sebagai
tiang dengan tiga lampu, bukan hanya titik merah.
Jangan ubah posisi benda apa pun. Jalankan cek.py untuk shot 1, 2, 3, dan 4.
```

### Prompt 4.6 · Detail ruko

```text
Ruko masih berupa kotak polos. Tambahkan detail ruko di Indonesia: rolling door
besi bergaris, kanopi seng bergelombang, papan nama toko tanpa merek sungguhan,
jendela lantai dua dengan teralis, talang air, dan AC luar. Semak dibuat lebih
rimbun dan tidak bersegi. Jangan ubah posisi benda apa pun.
Jalankan cek.py untuk shot 1 dan 3.
```

### Prompt 4.7 · Merapikan sisa masalah

```text
Sudah jauh lebih baik. Masih ada tiga hal.
1. Di ujung jalan pada shot 1, 2, dan 4 ada gumpalan hijau-kuning yang menyala.
   Cari benda apa itu, lalu perbaiki supaya tidak menyala.
2. Di shot 3 tiang lampu lalu lintas tidak terlihat dan lampu merahnya berbentuk
   aneh. Buat tiang besi abu-abu, kotak lampu hitam, dan tiga lampu bulat bertudung.
3. Di shot 2 kolam cahaya lampu natrium di aspal belum terlihat.
Jangan ubah posisi benda apa pun. Jalankan cek.py untuk shot 1, 2, 3, dan 4.
```

## Bab 5

### Prompt 5.1 · Motor bebek dan boks paket

```text
Buat film/motor.py: motor bebek biru dengan setang, spion, lampu depan yang
menyorot ke depan, lampu belakang merah, dan plat nomor tanpa nomor sungguhan.
Di jok belakang ada boks paket oranye dengan strip pemantul, berisi satu paket
berlabel kertas. Ukuran dalam meter dan titik pusat motor di tanah, supaya nanti
bisa dipakai di game Kurir Senja.
Putaran roda harus sesuai jarak tempuh (jarak dibagi keliling roda), supaya
roda tidak terlihat tergelincir.
Untuk sekarang taruh motor diam di jalan pada shot 1. Jalankan cek.py untuk
shot 1, lalu render juga motor dari dekat ke cek/motor.png.
```

### Prompt 5.2 · Motor bebek yang membulat

```text
Motornya masih kotak-kotak, belum seperti motor bebek. Motor bebek punya:
- bodi yang membulat, dengan pelindung kaki melengkung di depan lutut,
- sayap depan yang melengkung menutupi bagian atas roda depan,
- jok panjang yang empuk dengan tepi membulat,
- knalpot di kanan bawah, pijakan kaki, dan ban yang lebih ramping.
Pakai subdivision dan bevel supaya tepinya halus. Ukuran, titik pusat, dan
posisi motor jangan diubah. Render lagi cek/motor.png.
```

### Prompt 5.3 · Kurir Mas Adit

```text
Buat film/kurir.py untuk Mas Adit:
- Tubuh dari bentuk dasar dengan armature (tulang): pinggul, punggung, leher,
  kepala, lengan, tangan, dan kaki. Tubuh ini nanti tertutup jas hujan.
- Helm full face putih dengan kaca gelap yang memantulkan lampu, sarung tangan
  gelap, dan sepatu bot.
- Jas hujan ponco kuning dengan simulasi kain (cloth): ujungnya berkibar saat
  motor melaju, permukaannya tampak basah, dan kainnya tidak menembus badan
  atau jok motor.
- Pose yang nanti dibutuhkan storyboard: duduk di motor, menoleh, turun dari
  motor, berjalan, mengangkat dengan dua tangan, melepas helm, dan mengetuk pintu.
Tampilkan kurir duduk di motor yang diam di shot 1. Jalankan cek.py untuk
shot 1, lalu render kurir dari samping ke cek/kurir.png.
```

### Prompt 5.3b · Memberi batas: sudah cukup

```text
Cukup, jangan kejar angka paha 100%. Ponco kurir di atas motor memang tersingkap
di paha, itu wajar. Yang penting ponco menutupi badan dan lengan atas, tidak
menembus badan, dan tidak bergetar saat diam. Pakai hasil terbaik yang sudah
ada, jalankan cek.py untuk shot 1, render cek/kurir.png, lalu berhenti.
```

### Prompt 5.4 · Motor melaju di shot 1

```text
Gerakkan motor dan kurir di shot 1 sepanjang Jl. Kenanga dengan kecepatan tetap
di lajur kiri, menjauhi kamera. Tambahkan cipratan air setiap kali roda melewati
genangan. Jalankan cek.py untuk 4 frame di shot 1, lalu tunjukkan angka putaran
roda dibanding jarak tempuhnya.
```

### Prompt 5.5 · Kucing oren

```text
Buat film/kucing.py: kucing oren yang basah dengan bulu dari hair curves, ekor
yang bisa bergerak, dan gerakan untuk shot 3: melompat ke atas boks paket, duduk
diam, diangkat dengan dua tangan, lalu duduk rapi di bangku warung.
Ingat jedanya: setelah lampu hijau, kurir dan kucing diam selama 1 detik penuh.
Bulunya harus ringan supaya muat di kartu grafis 4 GB.
Jalankan cek.py untuk 6 frame di shot 3.
```

### Prompt 5.6 · Ponco saat berjalan

```text
Di shot 3, saat kurir turun dan berjalan ke bangku warung (sekitar frame 690
sampai 770), ponco terbang ke samping seperti tertiup badai. Ponco harus tetap
menggantung di badan dan hanya bergoyang sedikit saat berjalan. Kalau simulasi
kain sulit distabilkan, kurangi kekuatan angin dan kecepatan gerak kain di shot
ini saja. Jangan habiskan waktu mengejar angka sempurna.
Jalankan cek.py untuk frame 690, 730, dan 770.
```

### Prompt 5.7 · Ponco mengikuti tulang

```text
Ponco masih menggembung dan lepas dari badan saat kurir berjalan. Kita ganti
caranya. Jangan pakai simulasi kain untuk seluruh ponco. Buat ponco sebagai
mesh yang mengikuti tulang (armature) dengan bobot yang halus, panjangnya sampai
lutut, dan menutupi bahu serta lengan atas. Hanya tepi bawah selebar kira-kira
15 cm yang boleh bergoyang dengan simulasi kain; bagian lain terkunci ke badan.
Periksa juga helm: di shot 3 kepala kurir tampak seperti bola polos, padahal
helm putih dengan kaca gelap harus selalu terpasang.
Jalankan cek.py untuk frame 84, 690, 730, dan 770, lalu berhenti.
```

### Prompt 5.8 · Layar HP

```text
Buat film/hp.py: HP di dudukan setang motor dengan layar menyala. Isinya
aplikasi kurir generik tanpa logo atau merek, dibuat dari objek teks:
- shot 2: panah besar ke kanan dan tulisan "Belok kanan", jarak "20 m".
- shot 4 dan 5: "1 paket tersisa", "Gang Melati, pagar hijau", jam 21.47.
Tetes hujan menempel di layar. Jalankan cek.py untuk shot 2, lalu render layar
HP dari dekat ke cek/hp.png.
```

### Prompt 5.9 · Pintu dan siluet anak

```text
Buat adegan shot 6 dan 7 di rumah tujuan Gang Melati:
- Pintu kayu yang terbuka perlahan, cahaya hangat dari dalam rumah.
- Anak kecil hanya sebagai siluet gelap di ambang pintu, tanpa detail wajah,
  membawa kue ulang tahun dengan tiga lilin. Api lilin bergoyang dengan pola
  tetap (pakai seed) dan hanya menerangi kue, tidak wajah anak.
- Kurir dilihat dari belakang: berdiri di teras, melepas helm, mengetuk pintu.
Jalankan cek.py untuk shot 6 dan 7.
```

### Prompt 5.10 · Bingkai shot 6 dan 7

```text
Periksa ulang shot 6 dan 7 dengan ponco yang baru.
- Shot 6: kurir terlihat seluruh badan dari belakang di teras. Helm sudah dilepas
  dan dipegang di tangan kiri. Kepalanya punya rambut hitam pendek yang basah,
  bukan bola polos.
- Shot 7: kamera dari belakang bahu kanan kurir. Bahu dan kepala kurir hanya
  mengisi kira-kira sepertiga kiri gambar. Siluet anak dan kue dengan tiga
  lilin harus terlihat jelas di ambang pintu, di tengah gambar.
Jalankan cek.py untuk shot 6 dan 7, lalu berhenti.
```

### Prompt 5.11 · Siluet anak dan bentuk ponco

```text
Shot 7 belum seperti storyboard. Perbaiki tiga hal:
1. Anak harus berupa siluet gelap. Ruangan di belakangnya terang dan hangat,
   sedangkan dari arah kamera hampir tidak ada cahaya yang mengenai anak.
   Hanya kue dan api lilin yang terang.
2. Bentuk anak masih seperti balok kayu. Buat anak kecil setinggi kira-kira
   110 cm dengan kepala bulat berambut, badan dan lengan yang membulat, dan
   kedua tangan memegang piring kue di depan dada.
3. Ponco kurir tampak seperti papan rata. Beri bahu yang membulat mengikuti
   badan, lipatan kain yang jatuh ke bawah, dan tudung yang terlipat di punggung.
Jalankan cek.py untuk shot 6 dan 7, lalu berhenti.
```

## Bab 6

### Prompt 6.1 · Kamera sinematik

```text
Buat film/kamera.py sesuai kolom "Gerakan kamera" di STORYBOARD.md:
- Shot 1: lensa 24 mm, kamera rendah dekat genangan, naik pelan saat motor lewat.
- Shot 2: lensa 35 mm dari belakang-atas bahu kurir, layar HP tajam di depan.
  Kamera tersentak saat motor mengerem, lalu diam selama jeda.
- Shot 3: kamera diam, lensa 35 mm. Motor, lampu lalu lintas, dan bangku warung
  terlihat dalam satu bingkai. Ini adegan lelucon, jadi kamera tidak bergerak.
- Shot 4: kamera mengikuti dari belakang motor menyusuri Gang Melati.
- Shot 5: lensa 85 mm, maju pelan ke label paket sampai tulisannya memenuhi layar.
- Shot 6: kamera diam dari belakang kurir, sedikit dari bawah.
- Shot 7: dari belakang bahu kurir, maju sangat pelan ke kue.
- Shot 8: lebar dan diam, lalu mundur sangat pelan ke ujung gang.
Wajah kurir dan wajah anak tidak boleh terlihat di frame mana pun.
Semua gerakan memakai easing, fokus kabur (depth of field) pada benda penting,
dan motion blur ringan. Jalankan cek.py untuk frame awal, tengah, dan akhir
setiap shot.
```

### Prompt 6.2 · Gambar cek yang cepat

```text
Berhenti dulu, gambar cek sekarang terlalu lambat (satu frame lebih dari 10
menit). Untuk cek.py, matikan motion blur dan depth of field, dan jangan
hitung ulang simulasi dari frame 1 untuk setiap gambar. Motion blur dan fokus
kabur hanya dipakai di render akhir. Lalu jalankan cek.py untuk satu frame
tengah setiap shot saja, dan laporkan berapa lama satu frame.
```

### Prompt 6.3 · Ponco tanpa simulasi kain

```text
Berhenti mengukur. Kita sederhanakan: hapus simulasi kain dari ponco sama
sekali. Tepi bawah ponco cukup bergoyang dengan cara murah, misalnya gelombang
kecil (wave atau noise pada tulang tepi) yang kekuatannya mengikuti kecepatan
kurir. Dengan begitu tidak ada simulasi yang harus dihitung dari frame 1.
Cipratan tetap partikel, tetapi hanya hidup di frame yang perlu.
cek.py tetap tanpa motion blur dan depth of field.
Lalu jalankan cek.py untuk satu frame tengah setiap shot, laporkan lama satu
frame, dan berhenti.
```

### Prompt 6.4 · Memperbaiki kamera shot 2 dan 5

```text
Dua shot masih salah. Jangan ubah shot lain.
- Shot 2: kamera berada di dalam bahu kurir, jadi gambar tertutup ponco dan helm.
  Mundurkan dan naikkan kamera supaya bahu dan helm hanya di tepi kiri bawah,
  layar HP di setang terlihat tajam di tengah bawah, dan jalan serta kali
  terlihat di depan.
- Shot 5: label terlalu gelap dan datar. Paket dipegang dua tangan bersarung,
  label kertas basah miring sedikit, diterangi lampu teras yang hangat, dan
  tulisan "Penerima: Ayah" terbaca jelas.
Jalankan cek.py untuk frame awal, tengah, dan akhir shot 2 dan shot 5.
```

### Prompt 6.5 · Kamera shot 2 dari belakang bahu

```text
Shot 5 sudah bagus. Shot 2 masih salah: kamera melihat kurir dari depan dan
layar HP tidak terlihat sama sekali. Yang benar:
- Kamera berada di BELAKANG kurir, kira-kira 0,6 m di belakang dan 0,3 m di
  atas bahu kanannya, dan menghadap ke arah motor melaju.
- Yang terlihat: sedikit bahu dan sisi helm di tepi kiri, setang, layar HP
  dengan panah "Belok kanan" yang terbaca di bagian bawah tengah, lalu jalan
  dan kali di depan.
- Fokus pada layar HP.
Periksa dengan angka dulu (posisi kamera relatif terhadap kurir dan arah
hadapnya), baru jalankan cek.py untuk frame awal, tengah, dan akhir shot 2.
```

### Prompt 6.6 · Shot 2 dipotong menjadi tiga sudut

```text
Dari belakang bahu, badan kurir menutupi layar HP dan jalan. Sudut itu tidak
bisa dipakai. Kita ubah shot 2 menjadi tiga potongan, waktunya tetap 7-20 detik:
- 7-10 detik: close-up layar HP di setang, seperti cek/hp.png. Panah dan
  tulisan "Belok kanan" terbaca, tetes hujan di layar, jalan kabur di belakang.
- 10-17 detik: kamera diam dan rendah di seberang kali, lensa 35 mm. Motor
  datang berbelok ke kanan menuju kamera dan mengerem tepat di bibir beton.
  Lampu depan menyorot air. Helm menoleh ke kali, ke HP, lalu ke kali lagi.
  Kaca helm gelap, wajah tidak terlihat.
- 17-20 detik: kamera yang sama tetap diam. Motor berbelok ke kiri dan keluar
  dari gambar, kali tetap terlihat.
Perbarui juga kolom kamera shot 2 di STORYBOARD.md.
Jalankan cek.py untuk detik 8, 12, 15, dan 19.
```

### Prompt 6.7 · Versi tegak untuk Short

```text
Tambahkan versi tegak 1080x1920 untuk YouTube Short. Untuk setiap shot (shot 2 punya tiga potongan), buat kamera kedua yang geraknya sama dengan kamera lebar, tetapi bidikannya disesuaikan supaya motor, kucing, layar HP, label paket, dan kue selalu berada di tengah dan utuh. Kamera tegak boleh sedikit lebih jauh atau memakai lensa sedikit lebih lebar.

Aturan kontinuitas tetap berlaku: wajah kurir dan wajah anak tidak boleh terlihat di versi tegak.

Beri bangun.py dan cek.py pilihan --tegak. Tanpa pilihan itu, hasilnya harus tetap versi lebar yang sekarang, tidak berubah sama sekali. Lalu jalankan cek.py --tegak, satu frame per shot, dan laporkan shot mana yang benda pentingnya terpotong.
```

## Bab 7

### Prompt 7.1 · Efek suara dari kode

```text
Buat sfx.py yang membuat semua efek suara di kolom Suara STORYBOARD.md dengan kode (numpy), lalu menyimpannya sebagai WAV 48 kHz di folder suara/. Jangan memakai suara dari internet.

Yang dibutuhkan:
- hujan: desis lembut yang terus-menerus, versi deras (shot 1 sampai 4) dan versi rintik (shot 5 sampai 8), masing-masing bisa diulang tanpa terdengar sambungannya,
- kali: gemuruh air yang rendah untuk shot 2,
- motor bebek: mesin idle, mesin digas lalu menjauh, mesin melambat, dan mesin dimatikan,
- ban menyibak genangan, ban berdecit saat rem mendadak, kerikil jatuh ke air,
- klakson samar, detak dan bunyi "tit" lampu penyeberangan,
- kucing: meong pendek dan dengkuran sebentar,
- langkah sepatu basah, derit bangku kayu, derit rantai pagar, tetes talang,
- tiga ketukan pintu, langkah kaki kecil berlari, kunci diputar, pintu menutup,
- desis api lilin yang kena tetes air, riuh keluarga yang teredam tanpa kata.

Jalankan dengan Python bawaan Blender (blender --background --python sfx.py), lalu tampilkan tabel: nama file, durasi, dan puncak kekerasannya. Jangan menjalankan cek.py, karena gambar tidak berubah.
```

### Prompt 7.2 · Sinkronisasi suara dan subtitle

```text
Di folder suara/ sekarang ada gps.mp3 (suara GPS "Belok kanan.") dan anak.mp3 (suara anak "Selamat ulang tahun, Ayah!").

Buat sinkron.py yang:
- menaruh setiap efek suara di detik yang tepat. Waktu kejadian diambil dari kode animasi di film/ (misalnya frame motor berhenti di bibir kali, frame lampu berubah hijau, frame ketukan pintu), bukan dikira-kira,
- memakai gps.mp3 dua kali di shot 2 dari file yang sama, supaya intonasinya identik: sekali sebelum motor berbelok, sekali saat motor diam di tepi kali,
- memakai anak.mp3 di shot 7 setelah pintu terbuka,
- membuat 1 detik hening di shot 3 setelah bunyi "tit" lampu hijau,
- mengecilkan hujan saat ada kalimat, supaya kalimatnya jelas terdengar,
- membuat suara/film.wav sepanjang tepat 75 detik dengan kekerasan sekitar -14 LUFS,
- membuat suara/film.srt berisi ketiga kalimat dengan waktu yang tepat.

Tampilkan tabel: suara, shot, detik mulai, detik selesai. Kalau ada dua suara penting yang bertabrakan, beri peringatan di tabel dan jangan diam-diam menggesernya. Jangan mengubah durasi shot. Jangan menjalankan cek.py.
```

## Bab 8

### Prompt 8.1 · Skrip render akhir dan penggabung video

```text
Buat render.py untuk render akhir di laptop dengan kartu grafis:
- Cycles dengan denoiser, motion blur dan depth of field menyala (yang di cek.py dimatikan), jumlah sampel bisa diatur lewat --sampel (bawaan 128).
- Pakai kartu grafis kalau ada (OptiX atau CUDA), dan tulis di terminal perangkat mana yang dipakai. Kalau tidak ada, pakai CPU dan beri peringatan.
- Kartu grafis saya hanya punya memori 4 GB: batasi ukuran tekstur saat render dan nyalakan penyimpanan data yang hemat memori, supaya render tidak gagal karena kehabisan memori.
- Simpan PNG per frame di render/<versi>/shotN/, dan lewati frame yang sudah ada, supaya render bisa dilanjutkan kalau terhenti di tengah malam.
- Pilihan --versi lebar atau tegak, --shot untuk merender satu shot saja, dan --frame untuk satu frame saja.
- Setiap selesai satu frame, tulis satu baris: shot, frame, lama render, dan perkiraan sisa waktu.

Buat juga gabung.py yang memakai ffmpeg untuk menyatukan PNG, suara/film.wav, dan suara/film.srt menjadi film_lebar.mp4 atau film_tegak.mp4 (H.264, 24 fps, subtitle sebagai trek terpisah, bukan dibakar ke gambar).

Di komputer ini tidak ada kartu grafis, jadi cukup uji render.py dengan satu frame shot 1 memakai --sampel 16 untuk memastikan skripnya jalan. Jangan merender lebih dari itu.
```

### Prompt 8.2 · Poles sebelum render

```text
Sebelum render akhir, poles tiga hal ini. Kerjakan satu per satu, dan periksa setiap hal dengan satu atau dua frame cek saja.

1. Shot 2, potongan dari seberang kali (detik 10 sampai 20): motor terlalu kecil dan kalinya tidak terbaca. Dekatkan kamera menjadi sekitar 10 sampai 12 meter dari titik berhenti motor, dan turunkan sedikit, supaya air kali yang deras terlihat di sepertiga bawah gambar dan bibir beton tanpa pagar terlihat jelas. Lampu depan motor harus memantul di air. Toleh kepala kurir harus terbaca.

2. Ponco kurir di shot 6 dan 7: dari belakang masih seperti karung kaku. Buat bahunya turun mengikuti bahu, ada lipatan tegak yang lembut, tepi bawah tidak rata, dan permukaannya basah mengilap dengan tetes air. Kepala tanpa helm perlu leher dan rambut basah yang wajar.

3. Siluet anak di shot 7: kakinya seperti tongkat dan posenya kaku. Beri proporsi anak umur enam tahun (kepala lebih besar, badan pendek), baju tidur longgar, kaki sedikit menekuk, dan badan sedikit condong ke depan saat menyodorkan kue. Tetap siluet gelap, wajah tidak terlihat.

Jangan mengubah waktu shot, kamera lain, atau suara. Setelah selesai, jalankan cek.py satu frame per shot untuk versi lebar, dan laporkan apa yang masih kurang.
```

## Bab 9

### Prompt 9.1 · Memeriksa hasil render

```text
Buat periksa.py yang memeriksa hasil di render/lebar dan render/tegak:
- Lembar kontak: satu gambar kecil setiap 12 frame, per shot, dengan nomor frame, disimpan di cek/periksa/.
- Frame hilang: daftar frame yang belum ada atau berkasnya rusak.
- Deteksi lompatan: bandingkan setiap frame dengan frame sebelumnya, dan tandai frame yang perubahan terangnya jauh lebih besar dari rata-rata shot itu (kecuali di pergantian shot).
- Pemeriksaan data dari film.blend: untuk setiap frame, bandingkan jarak yang ditempuh motor dengan putaran roda, dan tandai yang tidak cocok. Periksa juga apakah kucing menembus boks dan apakah wajah kurir atau anak menghadap kamera.
- Versi tegak: gambar kotak area aman Short (bagian bawah dan kanan tertutup tombol YouTube) dan tandai kalau HP, label paket, atau kue masuk ke area itu.
Tulis semua temuan di cek/laporan.md, lengkap dengan shot dan nomor frame. Jangan memperbaiki apa pun dulu.
```

## Bab 10

### Prompt 10.1 · Ekspor motor dan helm untuk game

```text
Buat ekspor.py yang mengekspor motor bebek (dengan boks paket) dan helm ke ekspor/motor_bebek.glb dan ekspor/helm.glb: format glTF biner, satuan meter, titik pusat di tanah, menghadap ke depan (sumbu -Z di glTF), tekstur disertakan di dalam file. Roda depan, roda belakang, dan setang harus tetap menjadi objek terpisah dengan titik putar yang benar, supaya bisa diputar di game. Jangan mengekspor kamera, lampu, atau kurir. Setelah itu, baca kembali kedua file dan tampilkan tabel: nama objek, jumlah segitiga, dan ukuran file.
```
