# Suicune v7.6.2 Multi-PRE Inverse Shiny Selector

Scope:
- Keep natural RNG progression only. No Legal Advance / transport.
- Do not use the v7.6.1 open-loop future state/DIV projection in the production path.
- Expand actionable PRE cells only where a measured donor model already exists.
- Use inverse Gen2 shiny-DV matching instead of forward deep-call enumeration.

Supported measured PRE cells (distinct):
- A/r14, A/r3, A/r10, A/r6
- B/r10, B/r11, B/r5, B/r1
- D/r12

Inverse route-3 rule:
- For each measured deep profile and each shiny raw DV in {2AAA,3AAA,6AAA,7AAA,AAAA,BAAA,EAAA,FAAA}, compute the three high-byte carries from the current predeep high byte.
- Treat raw high/low bytes as L2/L3, invert L3 <- L2 and L2 <- L1 transitions, require L1 < C0, then recover the unique required predeep L0.
- Candidate iff actual predeep L0 equals the recovered value.

Inverse route-4 rule:
- Treat raw high/low bytes as L3/L4, invert to L2/L1/L0 with four carries, require L1 >= C0.

Safety:
- Actual current state/DIV/index only; no future state projection.
- Existing rel40 actual-POST rebind remains authoritative.
- Unknown PRE cells are observed but never armed.
