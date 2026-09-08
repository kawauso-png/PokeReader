/* Bounded offline LR35902 audio interpreter. All writes target private scratch
 * memory. No guest CPU, timer, APU, RNG or cartridge state is written. */
#include <stdint.h>
#include <string.h>
#include <stddef.h>
typedef struct {
    const uint8_t *rom; uint32_t length,cycles,error,bank;
    uint8_t mem[65536],known[65536],r[8],f;
    uint16_t pc,sp;
} AudioCPU;
static AudioCPU g;
static uint8_t rb(uint16_t a) {
    if(a<0x8000) {
        uint32_t off=a<0x4000?a:g.bank*0x4000U+a-0x4000U;
        if(off>=g.length){g.error=4;return 0;} return g.rom[off];
    }
    if(a>=0xe000 && a<0xfe00)a-=0x2000;
    if(!g.known[a]){g.error=1;return 0;} return g.mem[a];
}
static void wb(uint16_t a,uint8_t v) {
    if(a<0x8000) {
        if(a>=0x2000 && a<0x3000)g.bank=(g.bank&0x100U)|v;
        else if(a>=0x3000 && a<0x4000)g.bank=(g.bank&255U)|((v&1U)<<8);
        else g.error=5;
        return;
    }
    if(a>=0xe000 && a<0xfe00)a-=0x2000;
    g.mem[a]=v;g.known[a]=1;
}
static uint8_t imm(void){uint8_t v=rb(g.pc);g.pc++;return v;}
static uint16_t word(void){uint16_t v=imm();return v|((uint16_t)imm()<<8);}
static uint16_t pair(int p){return p==3?g.sp:((uint16_t)g.r[p*2]<<8)|g.r[p*2+1];}
static void setpair(int p,uint16_t v){if(p==3)g.sp=v;else {g.r[p*2]=v>>8;g.r[p*2+1]=v;}}
static uint8_t get(int i){return i==6?rb(pair(2)):g.r[i];}
static void put(int i,uint8_t v){if(i==6)wb(pair(2),v);else g.r[i]=v;}
static void push(uint16_t v){wb(--g.sp,v>>8);wb(--g.sp,v);}
static uint16_t pop(void){uint16_t v=rb(g.sp);v|=(uint16_t)rb(g.sp+1)<<8;g.sp+=2;return v;}
static int cond(int i){return i==0?!(g.f&128):i==1?!!(g.f&128):i==2?!(g.f&16):!!(g.f&16);}
static void alu(int k,int v) {
    int a=g.r[7],c=(k==1||k==3)?!!(g.f&16):0,t;
    if(k<2){t=a+v+c;g.f=(!(t&255)?128:0)|(((a&15)+(v&15)+c>15)?32:0)|(t>255?16:0);}
    else if(k==2||k==3||k==7){t=a-v-c;g.f=64|(!(t&255)?128:0)|((a&15)<(v&15)+c?32:0)|(t<0?16:0);}
    else {t=k==4?(a&v):k==5?(a^v):(a|v);g.f=(!t?128:0)|(k==4?32:0);}
    if(k!=7)g.r[7]=t;
}
static void step(void) {
    uint8_t op=imm();uint32_t cost=0;
    if(op>=0x40 && op<=0x7f) {
        if(op==0x76){g.error=2;return;}
        int d=(op>>3)&7,s=op&7;put(d,get(s));cost=(d==6||s==6)?2:1;
    } else if(op>=0x80 && op<=0xbf){alu((op>>3)&7,get(op&7));cost=(op&7)==6?2:1;}
    else if(op<0x40 && ((op&7)==4||(op&7)==5)) {
        int i=(op>>3)&7,v=get(i),dec=op&1,t=(v+(dec?-1:1))&255;
        g.f=(g.f&16)|(!t?128:0)|(dec?64:0)|((dec?((v&15)==0):((v&15)==15))?32:0);
        put(i,t);cost=i==6?3:1;
    } else if(op<0x40 && (op&7)==6){put((op>>3)&7,imm());cost=((op>>3)&7)==6?3:2;}
    else if(op<0x40 && (op&15)==1){setpair(op>>4,word());cost=3;}
    else if(op<0x40 && ((op&15)==3||(op&15)==11)){int p=op>>4;setpair(p,pair(p)+((op&15)==3?1:-1));cost=2;}
    else if(op<0x40 && (op&15)==9) {
        uint32_t a=pair(2),v=pair(op>>4),t=a+v;setpair(2,t);
        g.f=(g.f&128)|((a&4095)+(v&4095)>4095?32:0)|(t>65535?16:0);cost=2;
    } else if(op==2||op==0x12||op==0x22||op==0x32||op==0x0a||op==0x1a||op==0x2a||op==0x3a) {
        int p=op>>4;uint16_t a=pair(p<2?p:2);
        if(op&8)g.r[7]=rb(a);else wb(a,g.r[7]);
        if(p>=2)setpair(2,a+(p==2?1:-1));cost=2;
    } else if(op==0xc6||op==0xce||op==0xd6||op==0xde||op==0xe6||op==0xee||op==0xf6||op==0xfe) {alu((op>>3)&7,imm());cost=2;}
    else if(op==0xcb) {
        int x=imm(),group=x>>6,k=(x>>3)&7,i=x&7,v=get(i),t=v,out=0,c=!!(g.f&16);
        if(group==1)g.f=(g.f&16)|32|(!(v&(1<<k))?128:0);
        else if(group==2)t=v&~(1<<k);
        else if(group==3)t=v|(1<<k);
        else {
            if(k==0){t=(v<<1)|(v>>7);out=v>>7;}
            else if(k==1){t=(v>>1)|(v<<7);out=v&1;}
            else if(k==2){t=(v<<1)|c;out=v>>7;}
            else if(k==3){t=(v>>1)|(c<<7);out=v&1;}
            else if(k==4){t=v<<1;out=v>>7;}
            else if(k==5){t=(v>>1)|(v&128);out=v&1;}
            else if(k==6)t=(v<<4)|(v>>4);
            else {t=v>>1;out=v&1;}
            g.f=(!(t&255)?128:0)|(out?16:0);
        }
        if(group!=1)put(i,t);cost=i==6?(group==1?3:4):2;
    } else if(op==0xc5||op==0xd5||op==0xe5||op==0xf5){int p=(op>>4)&3;push(p==3?((uint16_t)g.r[7]<<8)|g.f:pair(p));cost=4;}
    else if(op==0xc1||op==0xd1||op==0xe1||op==0xf1){int p=(op>>4)&3;uint16_t v=pop();if(p==3){g.r[7]=v>>8;g.f=v&0xf0;}else setpair(p,v);cost=3;}
    else if(op==0xc3||op==0xc2||op==0xca||op==0xd2||op==0xda||op==0xcd||op==0xc4||op==0xcc||op==0xd4||op==0xdc) {
        uint16_t dest=word();int call=!!(op&4),take=op==0xc3||op==0xcd||cond((op>>3)&3);cost=3;
        if(take){if(call)push(g.pc);g.pc=dest;cost=call?6:4;}
    } else if(op==0x18||op==0x20||op==0x28||op==0x30||op==0x38) {
        int8_t d=(int8_t)imm();int take=op==0x18||cond((op>>3)&3);cost=2;if(take){g.pc+=d;cost=3;}
    } else if(op==0xc9||op==0xc0||op==0xc8||op==0xd0||op==0xd8) {
        int take=op==0xc9||cond((op>>3)&3);cost=op==0xc9?4:take?5:2;if(take)g.pc=pop();
    } else if((op&0xc7)==0xc7){push(g.pc);g.pc=op&0x38;cost=4;}
    else if(op==0xe9){g.pc=pair(2);cost=1;}
    else if(op==0xfa||op==0xea){uint16_t a=word();if(op==0xfa)g.r[7]=rb(a);else wb(a,g.r[7]);cost=4;}
    else if(op==0xf0||op==0xe0||op==0xf2||op==0xe2){uint16_t a=0xff00+((op&2)?g.r[1]:imm());if(op&16)g.r[7]=rb(a);else wb(a,g.r[7]);cost=(op&2)?2:3;}
    else if(op==7||op==15||op==23||op==31) {
        int v=g.r[7],c=!!(g.f&16),t,out;
        if(op==7||op==23){out=v>>7;t=(v<<1)|(op==7?out:c);}else {out=v&1;t=(v>>1)|((op==15?out:c)<<7);}
        g.r[7]=t;g.f=out?16:0;cost=1;
    } else if(op==0x2f){g.r[7]^=255;g.f|=96;cost=1;}
    else if(op==0x37){g.f=(g.f&128)|16;cost=1;}
    else if(op==0x3f){g.f=(g.f&128)|((g.f&16)^16);cost=1;}
    else if(op==0||op==0xf3||op==0xfb)cost=1;
    else {g.error=2;return;}
    g.cycles+=cost;
}
static void run(uint16_t pc) {
    g.pc=pc;push(0xffff);
    for(unsigned n=0;n<100000;n++) {if(g.error||g.pc==0xffff)return;step();}
    g.error=3;
}
uint32_t rank7108_audio(const uint8_t *rom,uint32_t len,const uint8_t *ram,const uint8_t *io,uint32_t *cycles,uint8_t *audio) {
    memset(&g,0,sizeof(g));g.rom=rom;g.length=len;
    memcpy(g.mem+0xc000,ram,8192);memset(g.known+0xc000,1,8192);
    memcpy(g.mem+0xff00,io,256);memset(g.known+0xff00,1,256);
    for(unsigned frame=0;frame<40;frame++) {
        memset(g.r,0,sizeof(g.r));g.f=0;g.sp=0xfffc;g.pc=0;g.bank=0x3a;g.cycles=0;
        wb(0xff9d,0x3a);
        unsigned count=frame==39?6:(frame>=28&&frame<=38?0:1);
        for(unsigned i=0;i<count;i++)run(0x405c);
        *cycles=g.cycles;
        if(frame==18){setpair(1,0x1f);run(0x3bb0);}
        if(g.error)return g.error;
    }
    if(audio)memcpy(audio,g.mem+0xc100,448);
    return 0;
}
