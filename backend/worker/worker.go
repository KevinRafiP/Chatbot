package worker

import "context"

// Interface/syarat: siapa pun yang punya fungsi Mulai(ctx) dianggap sebagai Worker.
type Worker interface {
	Mulai(ctx context.Context)
}

// JalankanSemua menyalakan setiap worker di jalurnya sendiri (goroutine)
func JalankanSemua(ctx context.Context, daftar ...Worker) {
	for _, w := range daftar {
		go w.Mulai(ctx)
	}
}
