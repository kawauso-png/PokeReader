"""Input-only RTC timing scenarios, not a validated live shiny gate.

The physical-UP release delay and subsequent host frame cadence are unknown
at launch. Test explicit hypotheses without reading outcome rows. Agreement
across this finite grid does not establish a probability or cover every path.
"""
from pathlib import Path
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import platform
import re
import struct
import subprocess

from prepare_replay import export
from run_prediction import summarize

EPOCH = dt.datetime(1900, 1, 1)


def rtc_milliseconds(blob):
    if len(blob) != 4112:
        raise ValueError('wrong launch RTC input size')
    begin, end = struct.unpack_from('<QQ', blob)
    counter, = struct.unpack_from('<I', blob, 16)
    milliseconds, reference, hz, drift = struct.unpack_from(
        '<QQI4xq', blob, 16 + 32 + 32 * (counter & 1))
    if end < begin or not hz or end < reference:
        raise ValueError('invalid RTC tick reference')
    return milliseconds + drift + (end - reference) * 1000 / hz


def pack(milliseconds):
    t = EPOCH + dt.timedelta(milliseconds=milliseconds)
    return (t.year << 26 | t.month << 22 | t.day << 17 |
            t.hour << 12 | t.minute << 6 | t.second)


def make_schedule(milliseconds, fps, pause_ms):
    # Model the pause between completed frames 2 and 3. This is a hypothesis
    # about host time, not a synthetic input or a change to real guest memory.
    return ''.join(f'{f},{pack(milliseconds + f * 1000 / fps + (pause_ms if f >= 3 else 0)):X}\n'
                   for f in range(1100))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace', type=Path, required=True)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--fps', nargs='+', type=float, default=[30, 60])
    p.add_argument('--pause-ms', nargs='+', type=int, default=[0, 1000, 3000, 5000])
    p.add_argument('--jobs', type=int, default=2)
    a = p.parse_args()
    if any(x <= 0 or x > 1000 for x in a.fps) or any(x < 0 or x > 600000 for x in a.pause_ms) or not 1 <= a.jobs <= 4:
        p.error('invalid scenario bounds or job count')
    if len(set(a.fps)) != len(a.fps) or len(set(a.pause_ms)) != len(a.pause_ms):
        p.error('duplicate scenarios')
    a.out.mkdir(parents=True, exist_ok=True)
    if (a.out / 'sensitivity.json').exists():
        p.error('choose a new output directory; existing results are preserved')
    manifest = export(a.trace, a.rom, a.out / 'input')
    import unicorn
    lib = Path(unicorn.__file__).parent
    source = Path(__file__).with_name('native_replay.c')
    exe = (a.out / 'native_replay').resolve()
    cmd = ['cc', '-O2']
    if platform.system() == 'Darwin':
        cmd += ['-arch', platform.machine()]
    subprocess.run(cmd + ['-I' + str(lib / 'include'), str(source),
                   str(lib / 'lib/libunicorn.a'), '-lpthread', '-lm', '-o', str(exe)], check=True)
    env = {k: v for k, v in os.environ.items() if k not in
           ('RTC_DELTA', 'RTC_INPUT_FILE', 'RTC_SCHEDULE_FILE', 'HEADLESS')}
    env['RTC_INPUT_FILE'] = str((a.out / 'input/launch_rtc.bin').resolve())
    env['HEADLESS'] = '1'
    memory = (a.out / 'input/pre_memory.bin').resolve()
    # Cross-check Python reference conversion against the original VC getter.
    probe = subprocess.run([str(exe), str(memory), str((a.out / 'rtc_probe').resolve()), '0'],
                           env=env, check=True, capture_output=True, text=True)
    native = int(re.search(r'RTC_INPUT_RESOLVED ([0-9A-F]+)', probe.stderr).group(1), 16)
    milliseconds = rtc_milliseconds((a.out / 'input/launch_rtc.bin').read_bytes())
    if pack(milliseconds) != native:
        raise ValueError('RTC conversion boundary mismatch; do not use approximate schedule')
    scenarios = [(fps, pause) for fps in a.fps for pause in a.pause_ms]

    def run(scenario):
        fps, pause = scenario
        name = f'fps{fps:g}_pause{pause}'
        schedule = (a.out / (name + '_rtc.csv')).resolve()
        schedule.write_text(make_schedule(milliseconds, fps, pause))
        prefix = (a.out / name).resolve()
        with (a.out / (name + '.log')).open('w') as log:
            subprocess.run([str(exe), str(memory), str(prefix), '1100'],
                           env={**env, 'RTC_SCHEDULE_FILE': str(schedule)},
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        result = dict(fps=fps, release_pause_ms=pause,
                      schedule_sha256=hashlib.sha256(schedule.read_bytes()).hexdigest(),
                      **summarize(Path(str(prefix) + '_events.csv')))
        print(json.dumps(result), flush=True)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        results = list(pool.map(run, scenarios))
    dvs = sorted({r['predicted_dv'] for r in results})
    report = dict(scope='Input-only finite RTC sensitivity grid; not independently validated',
                  input_manifest=manifest, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  outcomes_already_known_for_this_dataset='not inferred by this tool',
                  scenarios=results, distinct_dvs=dvs, dv_sensitive=len(dvs) > 1,
                  any_tested_scenario_shiny=any(r['predicted_shiny'] for r in results),
                  all_tested_scenarios_shiny=all(r['predicted_shiny'] for r in results),
                  live_gate_ready=False, success_probability=None,
                  limitations=['Finite constant-fps hypotheses; real frame cadence varies.',
                               'UP release pause is a hypothesis, not known at launch.',
                               'Within-frame RTC calls use one timestamp per frame.',
                               'Native getter validates launch conversion; later sub-millisecond boundaries remain approximate.',
                               'Headless rendering validated on 0032 and retrospective 0033 only.',
                               'All tested scenarios agreeing does not prove all possible trajectories agree.'])
    (a.out / 'sensitivity.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ('scenarios', 'input_manifest', 'limitations')}, indent=2))


if __name__ == '__main__':
    main()
