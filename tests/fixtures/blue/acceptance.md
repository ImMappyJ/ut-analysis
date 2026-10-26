# Synthetic inventory acceptance criteria

This is an authored specification for the bundled demonstration only, not a real product requirement.

- REQ-RESERVE: With stock 8, reserving 3 units returns remaining stock 5.
- REQ-INVALID: With stock 8, requests of 0, -1, 9 and fractional 0.5 units must raise ValueError.
- REQ-ALL: With stock 8, reserving all 8 units returns 0.

Synthetic acceptance policy: every listed P0 requirement must have sufficient assertion evidence.
No mandatory code coverage percentage is specified. Passing existing tests alone is insufficient.
