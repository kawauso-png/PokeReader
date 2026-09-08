"""Predict DV from frozen input and launch RTC, without reading trial outcomes."""
from pathlib import Path
import argparse,csv,json,subprocess,sys,os,platform,hashlib
from prepare_replay import export

def summarize(path):
 rows=list(csv.DictReader(path.open()));pairs=[]
 if len(rows)%2:raise ValueError('unpaired native DIV reads')
 previous=None
 for a,s in zip(rows[::2],rows[1::2]):
  if (a['pc'],s['pc']) not in [('02B6','02BE'),('2F60','2F68')]:raise ValueError('unexpected DIV read sequence')
  before=int(a['state'],16);mid=int(s['state'],16);total=(before>>8)+int(a['div'])
  if previous is not None and previous!=before:raise ValueError('native RNG continuity failed')
  if mid!=(((total&255)<<8)|(before&255)):raise ValueError('native A update mismatch')
  previous=(mid&0xff00)|(((mid&255)-int(s['div'])-(total>>8))&255)
  pairs.append(dict(pc=a['pc'],after=previous))
 final=[p for p in pairs if p['pc']=='2F60']
 if len(final) not in (3,4) or any(p['pc']!='2F60' for p in pairs[-len(final):]):raise ValueError('final DV generation not reached')
 if ((final[0]['after']&255)>=192)!=(len(final)==4):raise ValueError('held item branch mismatch')
 dv=((final[-2]['after']&255)<<8)|(final[-1]['after']&255)
 return dict(predicted_dv=f'{dv:04X}',predicted_shiny=dv in (0x2aaa,0x3aaa,0x6aaa,0x7aaa,0xaaaa,0xbaaa,0xeaaa,0xfaaa),normal_updates=len(pairs)-len(final),final_calls=len(final),div_reads=len(rows))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trace',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--retrospective-rtc-delta',type=int);p.add_argument('--headless',action='store_true');a=p.parse_args()
 inp=a.out/'input';manifest=export(a.trace,a.rom,inp,a.retrospective_rtc_delta is not None)
 import unicorn
 lib=Path(unicorn.__file__).parent;source=Path(__file__).with_name('native_replay.c');exe=a.out/'native_replay'
 cmd=['cc','-O2']
 if platform.system()=='Darwin':cmd+=['-arch',platform.machine()]
 cmd+=['-I'+str(lib/'include'),str(source),str(lib/'lib/libunicorn.a'),'-lpthread','-lm','-o',str(exe)]
 subprocess.run(cmd,check=True)
 env={k:v for k,v in os.environ.items() if k not in ('RTC_DELTA','RTC_INPUT_FILE','RTC_SCHEDULE_FILE','HEADLESS')}
 if a.retrospective_rtc_delta is not None:env['RTC_DELTA']=str(a.retrospective_rtc_delta)
 else:env['RTC_INPUT_FILE']=str((inp/'launch_rtc.bin').resolve())
 if a.headless:env['HEADLESS']='1'
 prefix=a.out/'predicted'
 with (a.out/'replay.log').open('w') as log:subprocess.run([str(exe.resolve()),str((inp/'pre_memory.bin').resolve()),str(prefix.resolve()),'1100'],stdout=log,stderr=subprocess.STDOUT,env=env,check=True)
 result=summarize(Path(str(prefix)+'_events.csv'))
 result.update(scope='Conditional native simulation; actual device gate and prospective success rate not established',input_manifest=manifest,retrospective_rtc_delta=a.retrospective_rtc_delta,headless=a.headless,rtc_model='RTC held at launch time throughout event; sensitivity must be verified for new conditions',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
 (a.out/'prediction.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
