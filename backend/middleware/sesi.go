package middleware

import (
	"context"
	"errors"
	"log"
	"net/http"
	"strings"

	"chatbot/backend/model"
	"chatbot/backend/service"
)

type kunciKonteks string

const kunciPengguna kunciKonteks = "pengguna"

// WajibSesi hanya meneruskan request yang membawa token sesi yang masih berlaku
func WajibSesi(sesi *service.SesiService, berikutnya http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		pengguna, err := sesi.Periksa(AmbilToken(r))
		if errors.Is(err, service.ErrSesiTidakValid) {
			tolak(w, http.StatusUnauthorized, "sesi tidak valid, silakan masuk lagi")
			return
		}
		if err != nil {
			log.Println("error periksa sesi:", err)
			tolak(w, http.StatusInternalServerError, "server sedang bermasalah")
			return
		}
		ctx := context.WithValue(r.Context(), kunciPengguna, pengguna)
		berikutnya.ServeHTTP(w, r.WithContext(ctx))
	})
}

// AmbilToken membaca token dari header "Authorization: Bearer <token>"
func AmbilToken(r *http.Request) string {
	token, ada := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
	if !ada {
		return ""
	}
	return strings.TrimSpace(token)
}

// PenggunaDari mengambil pengguna yang dititipkan WajibSesi ke dalam context
func PenggunaDari(ctx context.Context) model.Pengguna {
	pengguna, _ := ctx.Value(kunciPengguna).(model.Pengguna)
	return pengguna
}

func tolak(w http.ResponseWriter, status int, pesan string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	w.Write([]byte(`{"status":"gagal","message":"` + pesan + `"}`))
}
