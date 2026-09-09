#ifndef EVENTS7123_H
#define EVENTS7123_H
#include <stdint.h>
#include <string.h>
#include <stdio.h>
/* RAM only on timing-sensitive paths. Persist only after abort or DV result. */
#define EV7123_CAP 16
struct Event7123 {uint64_t tick;uint32_t kind,keys,detail;};
struct Events7123 {uint64_t nonce,source,launch,resume;uint32_t advance,dv,count,finished;struct Event7123 rows[EV7123_CAP];};
static void events7123_add(struct Events7123 *s,uint32_t kind,uint64_t tick,uint32_t keys,uint32_t detail){
 if(!s->nonce||s->finished)return;
 if(s->count&&s->rows[s->count-1].kind==kind)return;
 unsigned n=s->count<EV7123_CAP?s->count++:EV7123_CAP-1;
 s->rows[n]=(struct Event7123){tick,kind,keys,detail};
}
static void events7123_begin(struct Events7123*s,uint64_t nonce,uint64_t source,uint32_t advance,uint32_t dv,uint64_t launch,uint64_t resume,uint64_t now){
 memset(s,0,sizeof(*s));s->nonce=nonce;s->source=source;s->advance=advance;s->dv=dv;s->launch=launch;s->resume=resume;events7123_add(s,1,now,0,0);
}
static int events7123_render(const struct Events7123*s,char*out,unsigned cap){
 int n=snprintf(out,cap,"EVENT7123,nonce,%016llX,source,%016llX,advance,%u,predicted_dv,%04X,launch,%llu,resume,%llu\nkind,tick,held_keys,detail\n",(unsigned long long)s->nonce,(unsigned long long)s->source,s->advance,s->dv,(unsigned long long)s->launch,(unsigned long long)s->resume);
 if(n<0||(unsigned)n>=cap)return 0;
 for(unsigned i=0;i<s->count;i++){const struct Event7123*e=&s->rows[i];int k=snprintf(out+n,cap-n,"%u,%llu,%u,%u\n",e->kind,(unsigned long long)e->tick,e->keys,e->detail);if(k<0||(unsigned)k>=cap-(unsigned)n)return 0;n+=k;}
 return n;
}
#endif
