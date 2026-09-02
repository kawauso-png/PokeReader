#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs').read_text()
t=Path('reader_core/src/crystal/trace.rs').read_text()
m=Path('3gx/sources/main.c').read_text()

def need(c,msg):
    if not c: raise SystemExit('v735 audit FAIL: '+msg)

need('pub struct BucketPrediction' in p,'BucketPrediction missing')
need('pub fn evaluate_adaptive_bucket' in p,'adaptive evaluator missing')
for source,anchor,post in [(132,39,"post_proto:b'A',post_rot:2"),(128,76,"post_proto:b'C',post_rot:8"),(130,94,"post_proto:b'D',post_rot:15"),(129,112,"post_proto:b'A',post_rot:5"),(131,207,"post_proto:b'D',post_rot:2")]:
    need(f'source:{source},anchor:{anchor}' in p,f'donor {source}/bucket{anchor} missing')
    need(post in p,f'donor post {source} missing')
need('if steps < 4096 { 4 }' in p,'radius4 stage missing')
need('else if steps < 12288 { 8 }' in p,'radius8 stage missing')
need('else if steps < 24576 { 16 }' in p,'radius16 stage missing')
need('else { 128 }' in p,'full nearest stage missing')
need('evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),self.bucket_scan_steps)' in t,'frozen-root evaluator missing')
span=t[t.find('fn live_root_monitor'):t.find('fn practical_fail')]
need('evaluate_adaptive_bucket' not in span,'live scanner still predicts before request_pause transport')
need('out|=1u32<<27' in t,'shiny-ready bit missing')
need('bucket_model_active' in t,'bucket model state missing')
need('BUCKET735,V735' in t,'adaptive CSV missing')
need('S735 PAUSE SHINY SCAN' in t,'pause search UI missing')
need('S735 SHINY LOCK' in t,'shiny lock UI missing')
need('#define SUICUNE_ROOT_LOCK_MAX_STEPS 200000U' in m,'pause horizon missing')
need('bool shiny_ready = (cell & 0x08000000U) != 0;' in m,'shiny-ready decode missing')
need("if (shiny_ready && valid && bucket_valid && proto == (u32)'A' && rot == 10U)" in m,'dynamic ready gate missing')
need('bucket == 76U' not in m,'static bucket76 lock remains')
need('suicune_phase_slot = 1;' in m,'SLOT1 fixed path missing')
need('suicune_wait_up_after_b = true;' in m and 'if (suicune_wait_up_after_b)' in m,'TwoStageArm lost')
print('v7.3.5 audit PASS: frozen-root shiny evaluation; 5 bucket anchors; adaptive nearest widening; SLOT1 TwoStageArm retained')
