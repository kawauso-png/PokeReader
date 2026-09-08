from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parent
subprocess.run(['python3',str(root/'v7108/test_rom_diag.py')],check=True)
c=(root/'3gx/sources/main.c').read_text()
t=(root/'reader_core/src/crystal/trace.rs').read_text()
with tempfile.TemporaryDirectory() as td:
    tmp=Path(td)
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        str(root/'v7108/test_native.c'),str(root/'v7108/audio_sim.c'),str(root/'v7108/rank_core.c'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True)
    # Execute the actual generated pause-loop branch with mocked host actions.
    start=c.index('            if (suicune_neutral_probe_pending)')
    stop=c.index('            // Neutral delay is complete.',start)
    block=c[start:stop]
    harness=r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
typedef uint32_t u32;typedef uint64_t u64;
enum {KEY_A=1,KEY_B=2,KEY_X=4,KEY_Y=8,KEY_DUP=16,KEY_DDOWN=32,KEY_DLEFT=64,KEY_DRIGHT=128,KEY_L=256,KEY_R=512,KEY_START=1024,KEY_SELECT=2048};
static bool suicune_neutral_probe_pending,suicune_wait_up_after_b,rank7108_hunting=true;
static bool suicune_root_lock_ready,suicune_root_lock_active,suicune_root_lock_failed,suicune_live_pass_ready;
static bool fixed_armed,fixed_run_pending,suicune_auto_resume_pending,suicune_phase_lock_active,suicune_start_phase_lock_active,v7102_release_shown;
static u32 held,suicune_neutral_probe_remaining,suicune_neutral_probe_executed,fixed_a_frames,fixed_frames_remaining;
static u64 suicune_obs_arm_tick;
static int decision,commit_ok,arm_count,commit_count,evaluate_count,arm_ok=1;
int rank7108_evaluate(void){evaluate_count++;return decision;}
int rank7108_log_scan(int d){return 1;}
int rank7108_commit(void){commit_count++;return commit_ok;}
u32 rank7108_error(void){return 9;}u32 rank7108_cycles(void){return 9012;}u32 rank7108_checks(void){return 1;}
unsigned rank7108_best_shiny(void){return 0x2aaa;}unsigned rank7108_best_rank(void){return 40;}
void svcSleepThread(int x){}u64 svcGetSystemTick(void){return 1;}
void v7102_panel(const char*a,const char*b,const char*d){}
void arm_suicune_probe(void){assert(commit_count==1 && commit_ok);arm_count++;}
int suicune_research_arm_ok(void){return arm_ok;}int arm_suicune_live_pass(void){return 1;}
void suicune_observe_reset(void){}void suicune_early_lab_reset(void){}
void tick(void){for(int n=0;n<1;n++){BLOCK}}
void init(void){rank7108_hunting=true;suicune_neutral_probe_pending=true;suicune_wait_up_after_b=true;suicune_neutral_probe_remaining=0;
held=0;suicune_root_lock_ready=true;suicune_root_lock_active=suicune_root_lock_failed=suicune_live_pass_ready=false;
arm_count=commit_count=evaluate_count=0;fixed_armed=false;commit_ok=1;decision=1;}
int main(void){
init();suicune_neutral_probe_remaining=3;tick();assert(suicune_neutral_probe_remaining==2 && !evaluate_count && !arm_count);
init();held=KEY_DUP;tick();assert(!evaluate_count && !arm_count && suicune_neutral_probe_pending);
init();decision=0;tick();assert(evaluate_count==1 && !commit_count && !arm_count && suicune_root_lock_active && !suicune_wait_up_after_b);
init();decision=-1;tick();assert(!arm_count && !rank7108_hunting && suicune_root_lock_failed);
init();commit_ok=0;tick();assert(commit_count==1 && !arm_count && !rank7108_hunting);
init();tick();assert(commit_count==1 && arm_count==1 && suicune_live_pass_ready && fixed_armed && fixed_a_frames==2);
puts("PASS: real pause branch rejects early UP, weak candidate and failed PRE logging; Exact2 arms only after durable prediction");}
'''.replace('BLOCK',block)
    (tmp/'flow.c').write_text(harness)
    subprocess.run(['cc','-std=c99','-O2',str(tmp/'flow.c'),'-o',str(tmp/'flow')],check=True)
    subprocess.run([str(tmp/'flow')],check=True)
assert c.index('rank7108_commit()',c.index('int decision=rank7108_evaluate()'))<c.index('arm_suicune_probe();',c.index('int decision=rank7108_evaluate()'))
assert 'const u32 wanted = 14U;' in c and 'suicune_neutral_probe_remaining=3U;' in c
assert 'suicune_rank_pre_state' in (root/'reader_core/src/lib.rs').read_text()
assert 'cur.wrapping_sub(self.practical_live_found_advance)!=3' in t
assert 'ap!=0x2a35 || sp!=0x2a40' in t
for name in ('audio_sim.c','rank_core.c','rank_runtime.c'):
    assert (root/'v7108'/name).read_bytes()==(root/'3gx/sources'/('v7108_'+name)).read_bytes()
    text=(root/'v7108'/name).read_text()
    for forbidden in ('write_volatile','host_write_mem','synthetic','LegalAdvance'):
        assert forbidden not in text,(name,forbidden)
assert 'FSFILE_Flush(w.file)' in (root/'v7108/rank_runtime.c').read_text()
print('PASS: generated source identity, neutral3 PRE guard, M14 and read-only runtime')
