# Suicune Post-Adaptive v6.5

v6.5 keeps the v6.4 practical target search and exact execution path, but changes the rel40 mismatch behavior.

A rel40 mismatch no longer aborts the encounter. It is recorded as `S65 LEARN 1`; the practical prediction is disabled, while the normal Suicune probe continues through stop2/PURETAIL/DV and autosaves the full trace. This converts an unexpected PRE->POST transition into a complete donor instead of wasting the attempt.

Known-path matches still use the existing v6.4 rel716/rel717 closed-loop checks.
