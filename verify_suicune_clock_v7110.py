from pathlib import Path
import ast,json,subprocess,tempfile,os
root=Path(__file__).resolve().parent
subprocess.run(['python3','-B',str(root/'v7110/test_analyzer.py')],check=True)
c=(root/'3gx/sources/main.c').read_text()
h=(root/'reader_core/src/crystal/hook.rs').read_text()
r=(root/'reader_core/src/crystal/research.rs').read_text()
assert (root/'reader_core/src/crystal/clock7110.rs').read_bytes()==(root/'v7110/clock.rs').read_bytes()
assert 'static const bool clock7110_collection=true;' in c
assert 'if(rank7108_hunting && !clock7110_collection)' in c
assert h.index('super::research::clock_observe(')<h.index('if requested != 0xff04')
assert 'clock7110::arm(target,IO_HOST,PRE_OK && IO_OK && EMU_OK && MODE==3)' in r
clock=(root/'v7110/clock.rs').read_text()
hot=clock[clock.index('pub fn observe('):clock.index('pub fn save(')]
for token in ['trace_file_write','format!','write!','String','Vec','request_resume','pause','write_volatile']:
    assert token not in hot,token
with tempfile.TemporaryDirectory() as td:
    p=Path(td)
    test=(root/'v7110/test_clock.rs.in').read_text().replace('CLOCK_PATH',json.dumps(str(root/'v7110/clock.rs')))
    (p/'test.rs').write_text(test)
    subprocess.run(['rustc','--edition=2021','--test','-O',str(p/'test.rs'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test'),'--test-threads=1'],env={**os.environ,'CLOCK_TEST_OUT':str(p/'clock.csv')},check=True)
    # Exercise real generated research integration with the existing collector fixtures.
    test=(root/'v7102/test_collector.rs.in').read_text().replace('RESEARCH_PATH',json.dumps(str(root/'reader_core/src/crystal/research.rs')))
    (p/'research.rs').write_text(test)
    subprocess.run(['rustc','--edition=2021','--test','-O',str(p/'research.rs'),'-o',str(p/'research')],check=True)
    subprocess.run([str(p/'research'),'--test-threads=1'],check=True)
    # Reuse the original host-flow harness; include the deployed collection branch.
    tree=ast.parse((root/'verify_suicune_v7108.py').read_text())
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='harness' for t in n.targets))
    harness=node.value.func.value.value
    harness=harness.replace('static bool suicune_neutral_probe_pending,','static bool clock7110_collection=false;\nstatic bool suicune_neutral_probe_pending,')
    harness=harness.replace('assert(commit_count==1 && commit_ok);','if(!clock7110_collection)assert(commit_count==1 && commit_ok);')
    harness=harness.replace('void init(void){','void init(void){clock7110_collection=false;')
    harness=harness.replace('puts("PASS: real pause', '''init();clock7110_collection=true;decision=-1;tick();assert(!evaluate_count && !commit_count && arm_count==1 && suicune_live_pass_ready && fixed_a_frames==2);
init();clock7110_collection=true;held=KEY_DUP;tick();assert(!arm_count && suicune_neutral_probe_pending);
init();clock7110_collection=true;arm_ok=0;tick();assert(arm_count==1 && !suicune_live_pass_ready);
puts("PASS: collection starts without a shiny gate, waits for release and respects failed arming");
puts("PASS: real pause''')
    start=c.index('            if (suicune_neutral_probe_pending)');end=c.index('            // Neutral delay is complete.',start)
    (p/'flow.c').write_text(harness.replace('BLOCK',c[start:end]))
    subprocess.run(['cc','-std=c99','-O2',str(p/'flow.c'),'-o',str(p/'flow')],check=True)
    subprocess.run([str(p/'flow')],check=True)
print('PASS: compact clock rows, bounded memory, stable-read flag, generated integration and collection-only UI flow')
