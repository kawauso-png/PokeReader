#!/usr/bin/env python3
from pathlib import Path

TRACE = Path('reader_core/src/crystal/trace.rs')
PRACTICAL = Path('reader_core/src/crystal/practical.rs')
MAIN = Path('3gx/sources/main.c')


def span(text, signature):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'missing function: {signature}')
    brace = text.find('{', start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == '{': depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    raise SystemExit(f'unclosed function: {signature}')


t = TRACE.read_text()
p = PRACTICAL.read_text()
m = MAIN.read_text()

search = span(t, 'pub fn search_practical_targets(&mut self, _reader: &Gen2Reader)')
wait = span(t, 'fn practical_wait_monitor(&mut self, reader: &Gen2Reader)')

checks = {
    'live scan field': 'practical_live_scan: bool' in t,
    'live start tick': 'practical_live_start_tick: u64' in t,
    'live found tick': 'practical_live_found_tick: u64' in t,
    'search enables scanner': 'self.practical_live_scan = true;' in search,
    'search release gated': 'pnp::request_release_resume();' in search,
    'search has no future stepping': 'normal_step' not in search,
    'search has no horizon': 'SEARCH_HORIZON' not in search,
    'search does not set E2': 'practical_search_error = 2' not in search,
    'search does not set E3': 'practical_search_error = 3' not in search,
    'one-check-per-advance gate': 'current == self.practical_live_last_advance' in wait,
    'live lane observation': 'self.live_practical_lane()' in wait,
    'actual state observation': 'reader.rng_state()' in wait,
    'actual DIV observation': 'measured_div()' in wait,
    'direct evaluator': 'practical::evaluate(lane_id, state, div)' in wait,
    'no future stepping in monitor': 'normal_step' not in wait,
    'no EVAL transport diag': 'set_transport_diag(3' not in wait,
    'no target equality wait': 'current != self.practical_targets' not in wait,
    'bind existing prediction': 'self.bind_practical_prediction(p);' in wait,
    'pause on live root': 'pnp::request_pause();' in wait,
    'scanner dashboard': 'S680 SCAN' in t,
    'ready preserved': 'S680 READY UP+B' in t,
    'branch guard 40 preserved': 'S680 RETRY B40' in t,
    'branch guard 716 preserved': 'S680 RETRY B716' in t,
    'branch guard 717 preserved': 'S680 RETRY B717' in t,
    'live telemetry': 'LIVE_SCAN,V680' in t,
    'fast validate preserved': 'S658 TEST' in t,
    'release gate preserved': 'host_request_release_resume' in m,
    'full-index model preserved': 'normal_inc_full' in p and '0x22b6' in p,
}

bad = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('OK  ' if ok else 'FAIL') + name)
if bad:
    raise SystemExit('v6.8.0 audit failed: ' + ', '.join(bad))

# Version sanity: the operational practical UI must be v680. Older marker text
# can still exist in comments/legacy diagnostics, but no active S671 UI strings.
if '"S671 ' in t:
    raise SystemExit('active S671 UI string remains')

print('Suicune v6.8.0 Live Root Scan audit passed')
