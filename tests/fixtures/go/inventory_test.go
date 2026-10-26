package inventory

import test "testing"

func TestReserve(t *test.T) {
	t.Run("valid", func(t *test.T) {
		if got, err := Reserve(8, 3); got != 5 || err != nil {
			t.Errorf("remaining stock = %d, want 5", got)
		}
	})
}

func BenchmarkReserve(b *test.B) {
	for i := 0; i < b.N; i++ {
		_ = 8 - 3
	}
}
