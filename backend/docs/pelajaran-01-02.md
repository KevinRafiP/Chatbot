# Dokumentasi Pelajaran 1–2

## Menjalankan
```
go run .
```
Server berjalan di `http://localhost:8080`.

## Endpoint

| Method | Path | Parameter | Keterangan |
|---|---|---|---|
| GET | `/halo` | – | Teks biasa `Halo dari server Go!` |
| GET | `/sapa/{nama}` | path `nama`, query opsional `umur` (angka) | Sapaan JSON. `umur` bukan angka → 400 |
| POST | `/pengguna` | body JSON `{"nama": string, "umur": int}` | `nama` wajib. Sukses → 201 |

## Format response JSON
```json
{ "status": "sukses | gagal", "message": "…", "data": … }
```
`data` hilang jika kosong (`omitempty`).

## Isi main.go
- `Response`, `Pengguna`: struct + struct tag json
- `writeJSON`: urutan wajib Header → WriteHeader → Encode
- `sapa`: `r.PathValue`, `r.URL.Query().Get`, `strconv.Atoi`
- `buatPengguna`: `json.NewDecoder(r.Body).Decode(&p)` + validasi

## Contoh tes (PowerShell)
```powershell
curl.exe "http://localhost:8080/sapa/Kevin?umur=20"
Invoke-RestMethod -Method Post -Uri http://localhost:8080/pengguna -ContentType "application/json" -Body '{"nama":"Kevin","umur":20}'
```
