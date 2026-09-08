#include "rank_core.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
int main(void) {
    /* Reference results are from Python leave-one-out, not self replay. */
    const unsigned seed[]={53301,373,25594,62830,27423,9416,30508,36861,44752};
    const unsigned cost[]={8746,11350,9012,8750,8758,9761,8570,10125,8569};
    const unsigned dv[]={0x20c9,0xd956,0xc568,0x5a03,0xe58d,0xae1f,0xfd83,0x0396,0xa82e};
    const unsigned rank[]={46,2768,2605,4,23,0,166,759,194};
    const unsigned count[]={4038,3892,3973,4083,3979,3630,3898,3927,3884};
    for(int i=0;i<9;i++) {
        assert(rank7108_score(seed[i],cost[i],i)==count[i]);
        assert(rank7108_rank(dv[i])==rank[i]);
    }
    rank7108_score(0x034e,9012,-1);
    assert(rank7108_best_shiny()==0x2aaa && rank7108_best_rank()==40 && rank7108_support()>=2);
    rank7108_score(0,8569,-1);assert(rank7108_best_rank()==0);
    /* Synthetic ROM, no copyrighted ROM fixture. Check reset, bounds and
       rejection of unsupported/uninitialized interpreter paths. */
    uint8_t *rom=calloc(2097152,1),ram[8192]={0},io[256]={0},out[448];uint32_t cycles=0;
    assert(rom);unsigned entry=0x3a*0x4000+0x5c;rom[entry]=0xc9;rom[0x3bb0]=0xc9;
    memset(ram+0x100,0x5a,448);
    assert(rank7108_audio(rom,2097152,ram,io,&cycles,out)==0 && cycles==24);
    assert(memcmp(out,ram+0x100,448)==0);
    assert(io[0x9d]==0 && ram[0x100]==0x5a); /* caller's state stays intact */
    rom[entry]=0x76;assert(rank7108_audio(rom,2097152,ram,io,&cycles,out)==2);
    rom[entry]=0xfa;rom[entry+1]=0;rom[entry+2]=0x80;rom[entry+3]=0xc9;
    assert(rank7108_audio(rom,2097152,ram,io,&cycles,out)==1);
    rom[entry]=0xc3;rom[entry+1]=0x5c;rom[entry+2]=0x40;
    assert(rank7108_audio(rom,2097152,ram,io,&cycles,out)==3);
    assert(rank7108_audio(rom,64,ram,io,&cycles,out)==4);
    free(rom);puts("PASS: 9 Python-reference ranks; shiny inverse case; audio bounds, reset, read-only inputs");
}
