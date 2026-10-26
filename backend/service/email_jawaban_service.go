package service

import (
	"errors"
	"strings"
	"sync"
	"time"

	"chatbot/backend/agen"
	"chatbot/backend/model"
)

const batasIsiEmailJawaban = 20000

var (
	ErrJatahEmailHabis = errors.New("jatah kirim email hari ini sudah habis")
	zonaWIB            = time.FixedZone("WIB", 7*3600)
)

// EmailJawabanService mengirim jawaban chatbot ke email akun pengguna sendiri, bila pengguna memintanya
type EmailJawabanService struct {
	pengirim PengirimEmail
	maksHari int

	mu      sync.Mutex
	jatah   map[string]int
	tanggal string
}

// BaruEmailJawabanService mengembalikan nil bila pengirim email belum diatur atau maksHari 0, artinya fitur mati
func BaruEmailJawabanService(pengirim PengirimEmail, maksHari int) *EmailJawabanService {
	if pengirim == nil || maksHari <= 0 {
		return nil
	}
	return &EmailJawabanService{pengirim: pengirim, maksHari: maksHari, jatah: map[string]int{}}
}

// Bisa menandai apakah pengguna ini boleh meminta jawaban dikirim ke email; tamu tidak punya email
func (s *EmailJawabanService) Bisa(pengguna model.Pengguna) bool {
	return s != nil && pengguna.Jenis != "tamu" && pengguna.Email != ""
}

// Kirim mengirim email ke alamat akun pengguna, bukan alamat dari isi percakapan, agar fitur ini tidak bisa dipakai mengirim spam
func (s *EmailJawabanService) Kirim(pengguna model.Pengguna, email *agen.Email) error {
	if !s.Bisa(pengguna) || email == nil {
		return errors.New("kirim email tidak aktif untuk akun ini")
	}
	if !s.pakaiJatah(pengguna.ID) {
		return ErrJatahEmailHabis
	}
	subjek := potong(strings.Join(strings.Fields(email.Subjek), " "), 120)
	if subjek == "" {
		subjek = "Jawaban dari Vokapas"
	}
	isi := potong(strings.TrimSpace(email.Isi), batasIsiEmailJawaban) + "\n\n---\nDikirim oleh Vokapas atas permintaanmu di percakapan."
	return s.pengirim.Kirim(pengguna.Email, subjek, isi)
}

// pakaiJatah menghitung email per pengguna per hari (WIB); hitungan diulang setiap ganti hari
func (s *EmailJawabanService) pakaiJatah(penggunaID string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	hariIni := time.Now().In(zonaWIB).Format("2006-01-02")
	if s.tanggal != hariIni {
		s.tanggal = hariIni
		s.jatah = map[string]int{}
	}
	if s.jatah[penggunaID] >= s.maksHari {
		return false
	}
	s.jatah[penggunaID]++
	return true
}
