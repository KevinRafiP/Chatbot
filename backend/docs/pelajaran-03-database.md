# Dokumentasi Pelajaran 3 — Koneksi PostgreSQL (Chatbot Tahap A)

## Persiapan database
```powershell
psql -U postgres -f database/buat_database.sql
psql -U postgres -d latihan_chatbot -f database/migrasi.sql
```

## Konfigurasi (.env / .env.example)
| Variabel | Contoh | Fungsi |
|---|---|---|
| APP_PORT | 8080 | Port server |
| DB_HOST | localhost | Alamat PostgreSQL |
| DB_PORT | 5432 | Port PostgreSQL |
| DB_USER | postgres | User database |
| DB_PASSWORD | (rahasia) | Password database, hanya di `.env` |
| DB_NAME | latihan_chatbot | Nama database |
| DB_SSLMODE | disable | SSL untuk lokal dimatikan |

`.env` tidak di-upload ke git (`.gitignore`).

## Struktur
| Folder/File | Tugas |
|---|---|
| `config/config.go` | Membaca `.env` → struct `Config`, method `DSN()` |
| `database/postgres.go` | `Hubungkan(dsn)`: buka pool koneksi + `Ping` |
| `database/*.sql` | Pembuatan database, tabel, data contoh |
| `model/pengetahuan.go` | Struct `Pengetahuan` (cermin tabel) |
| `repository/pengetahuan_repository.go` | Query SQL: `Semua()` |
| `main.go` | Merangkai config → DB → repository → route |

## Alur
```
go run . → config.Muat() → database.Hubungkan() → repository → mux → ListenAndServe
GET /pengetahuan → daftarPengetahuan → repo.Semua() → SELECT → JSON
```

## Endpoint baru
| Method | Path | Keterangan |
|---|---|---|
| GET | `/pengetahuan` | Semua isi tabel pengetahuan |

## Dependensi
- `github.com/jackc/pgx/v5` (driver PostgreSQL, didaftarkan lewat blank import `_ ".../stdlib"`)
- `github.com/joho/godotenv` (membaca `.env`)

## Kesalahan yang pernah terjadi
| Gejala | Penyebab |
|---|---|
| `undefined: time` | lupa `import "time"` |
| `undefined: Config` | `type config` huruf kecil |
| `non-declaration statement outside function body` | kurang `{` setelah deklarasi fungsi |
| `404 page not found` | route `/Pengetahuan` (huruf besar) — path case-sensitive |
| `body JSON tidak valid` di Postman | Body bukan raw → JSON / kosong / format JSON salah |
