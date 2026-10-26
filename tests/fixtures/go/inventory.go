package inventory

import "errors"

// Reserve is synthetic inventory behavior for the public test fixtures.
func Reserve(stock, quantity int) (int, error) {
	if quantity <= 0 || quantity > stock {
		return stock, errors.New("invalid quantity")
	}
	return stock - quantity, nil
}
