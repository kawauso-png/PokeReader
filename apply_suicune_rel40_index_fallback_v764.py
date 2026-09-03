from pathlib import Path
T=Path('reader_core/src/crystal/trace.rs')
t=T.read_text()
old="""                let(Some(ai),Some(si))=(add_div_tracker().index(),sub_div_tracker().index())else{self.practical_fail(11);return};
                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,(ai as u32)&0x3fff,(si as u32)&0x3fff);
"""
new="""                // v7.6.4: live DivTracker indices can temporarily be unavailable after Exact2F.
                // The PRE-HINT root indices were authoritative and stored before arming.  rel40 is
                // exactly target+41 RNG advances in this trace convention, so reconstruct the
                // missing indices from that saved root instead of declaring UNKNOWN.
                let ai=add_div_tracker().index().map(|x|(x as u32)&0x3fff)
                    .unwrap_or(self.practical_live_found_ai.wrapping_add(41)&0x3fff);
                let si=sub_div_tracker().index().map(|x|(x as u32)&0x3fff)
                    .unwrap_or(self.practical_live_found_si.wrapping_add(41)&0x3fff);
                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
"""
if old not in t: raise SystemExit('v764 rel40 index anchor missing')
t=t.replace(old,new,1)
# Make generic reset UI identify the fixed gate epoch instead of the inherited S719 label.
t=t.replace('pnp::println!("S719 RESET RECOMMENDED");','pnp::println!("S764 RESET RECOMMENDED");',1)
T.write_text(t)
print('Applied v7.6.4 rel40 tracker-index fallback')
