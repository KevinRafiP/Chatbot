# Dokumentasi Pelajaran 4–5 — Chatbot, Struktur Folder, Migrasi, Worker

## Endpoint
| Method | Path | Body | Keterangan |
|---|---|---|---|
| POST | `/chat` | `{"pertanyaan": "..."}` | Jawaban dari data pengetahuan paling cocok |
| GET | `/pengetahuan` | – | Semua data pengetahuan |

Contoh hasil `/chat`:
```json
{"status":"sukses","message":"jawaban chatbot","data":{"jawaban":"Kantor buka ...","sumber":["Jam operasional"]}}
```

## Alur chatbot
```
POST /chat → handler.Chat → service.Jawab → PecahKata (buang kata umum & <3 huruf)
          → repository.Cari (skor = jumlah kata yang cocok persis di kata_kunci) → isi data teratas
```

## Struktur folder
| Folder | Tugas |
|---|---|
| `handler/` | Terima request & kirim balasan (respon.go = Response + writeJSON) |
| `router/` | Daftar semua route API |
| `service/` | Logika (chatbot) |
| `repository/` | Semua SQL |
| `worker/` | Proses terjadwal di belakang layar |
| `database/migrasi/` | File migrasi bernomor `0001_xxx.sql` |

## Migrasi
- Dijalankan otomatis saat server menyala (`database.JalankanMigrasi`).
- Dicatat di tabel `riwayat_migrasi`; yang sudah tercatat dilewati.
- Aturan: hanya file bernomor 4 digit; jangan ubah file lama, buat nomor baru; jangan taruh `CREATE DATABASE` di folder ini (`database/buat_database.sql` dijalankan manual).

## Worker pengindeks kata kunci
- Jalan sekali saat start, lalu setiap `WORKER_INTERVAL_MENIT` menit.
- Mengisi `kata_kunci` = kata penting dari judul + isi + kata kunci lama (tanpa dobel, urut abjad).

## Konfigurasi baru
| Variabel | Contoh | Fungsi |
|---|---|---|
| WORKER_INTERVAL_MENIT | 10 | Jarak antar putaran worker (menit) |

## Kesalahan yang pernah terjadi
| Gejala | Penyebab |
|---|---|
| go vet: struct field tag ... bad syntax | Tag json kurang tanda kutip penutup |
| migrasi buat_database.sql gagal: sintaks error dekat NOT | File buat_database.sql masuk folder migrasi + `IF NOT EXISTS` tidak ada untuk CREATE DATABASE di PostgreSQL |
