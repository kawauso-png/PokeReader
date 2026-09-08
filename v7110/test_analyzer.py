from pathlib import Path
import csv,tempfile,copy
from analyze_clock import analyze,HEX

header='record,index,kind,advance,frame,pc,state,div,elapsed,remaining,tima,tma,tac,ie,iflag,ly,lyc,stat,lcdc,hvblank,ime,timer_phase,budget,lcd_count,lcd_long,timer_count,timer_flag,stable'.split(',')
# Manually specified transcript: FE01 -> FD00 normal update, then three
# final calls produce 4DAF, A25A, F903, hence raw DV 5A03.
given=[(0x2b6,0xfe01,16382,100),(0x2be,0xfd01,9,101),
       (0x2f60,0xfd00,0x5008,101),(0x2f68,0x4d00,0x5013,101),
       (0x2f60,0x4daf,0x5508,101),(0x2f68,0xa2af,0x5513,101),
       (0x2f60,0xa25a,0x5708,101),(0x2f68,0xf95a,0x5713,101)]
# The timer phase coordinate is 14 bits; DIV 50 is phase 1400, not 5000.
given=[(pc,state,(phase>>8)*64+(phase&255) if phase in (0x5008,0x5013,0x5508,0x5513,0x5708,0x5713) else phase,adv) for pc,state,phase,adv in given]
records=[]
for i,(pc,state,phase,adv) in enumerate(given):
    d={k:0 for k in header};d.update(record='R7110_CLOCK',index=i,kind='DIV',advance=adv,pc=pc,state=state,
        div=phase>>6,remaining=64-(phase%64),stable=1,ie=15,tac=4)
    records.append([f'{d[k]:X}' if k in HEX else str(d[k]) for k in header])
end=bytearray(127);end[0x61:0x63]=bytes.fromhex('F903')
base=[['target','target_state','raw_dv'],['SUICUNE','100','FE01','5A03']]
# Main record headers include their record-name column.
base=[['record','target','target_state','raw_dv'],['SUICUNE','100','FE01','5A03'],
      ['record','target','pre_ok','end_valid','end_advance'],['R7102_META','100','1','1','101'],
      ['R7102_BLOB','END_HRAM','FF80','0',end.hex()],
      ['R7110_CLOCKMETA','100','1','8','0','0','0','0','DIAGNOSTIC_NO_SHINY_GATE'],header]
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'trace.csv'
    def check(rows):
        with p.open('w',newline='') as f:csv.writer(f).writerows(rows)
        return analyze(p)
    good=check(base+records);assert good['valid'],good
    assert good['normal_updates']==1 and good['final_calls']==3 and good['replayed_dv']=='5A03'
    bad=copy.deepcopy(base+records);bad[5][4]='1';assert not check(bad)['valid']
    bad=copy.deepcopy(base+records);bad[7][header.index('remaining')]='0';assert not check(bad)['valid']
    bad=copy.deepcopy(base+records);bad[8][header.index('state')]='FD02';assert not check(bad)['valid']
    bad=copy.deepcopy(base+records);bad[7][header.index('stable')]='0';assert not check(bad)['valid']
    assert not check(base+records[1:])['valid']
print('PASS: complete measured-clock RNG/DV replay, missing reads, overflow, unstable snapshots and state mismatches')
