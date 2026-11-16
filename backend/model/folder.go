package model

// Folder mengelompokkan percakapan milik satu akun; Jumlah adalah banyaknya percakapan aktif di dalamnya
type Folder struct {
	ID     string `json:"id"`
	Nama   string `json:"nama"`
	Jumlah int    `json:"jumlah"`
}
