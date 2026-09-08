/* Exact C port of scene_duration empirical ranking. Scores are not probabilities. */
#include "rank_core.h"
#include "rank_model.h"
#include <string.h>
#include <stdlib.h>
static double scores[65536];
static uint16_t order[65536];
static const uint16_t shiny[8]={0x2aaa,0x3aaa,0x6aaa,0x7aaa,0xaaaa,0xbaaa,0xeaaa,0xfaaa};
static unsigned support[8],count,best_index,best_rank;
typedef struct {uint16_t dv;double w;} Hypothesis;
static unsigned div_at(int phase){return ((unsigned)phase&16383U)>>6;}
static int forward(uint16_t seed,int sa,int ss,const RankPath *p,int shift) {
    unsigned total=(seed>>8)+sa,a=total&255,s=((seed&255)-ss-(total>>8))&255;
    unsigned vals[4];
    for(int i=0;i<p->f;i++) {
        total=a+div_at(p->final[i][0]+shift);
        a=total&255;s=(s-div_at(p->final[i][1]+shift)-(total>>8))&255;vals[i]=s;
    }
    if((vals[0]>=192)!=(p->f==4))return -1;
    return (vals[p->f-2]<<8)|vals[p->f-1];
}
static int compare(const void *x,const void *y) {
    unsigned a=*(const uint16_t*)x,b=*(const uint16_t*)y;
    if(scores[a]>scores[b])return -1;if(scores[a]<scores[b])return 1;
    return (a>b)-(a<b);
}
uint32_t rank7108_rank(uint16_t dv) {
    double threshold=scores[dv];if(threshold<=0)return 0;
    double eps=threshold*1e-12;if(eps<1e-15)eps=1e-15;
    unsigned r=0;for(unsigned i=0;i<65536;i++)if(scores[i]>=threshold-eps)r++;
    return r; /* worst rank within a floating-point tie, matching Python */
}
uint32_t rank7108_score(uint16_t seed,int cost,int exclude) {
    memset(scores,0,sizeof(scores));memset(support,0,sizeof(support));
    double kernel=shared_weight[0];for(int i=1;i<=8;i++)kernel+=2*shared_weight[i];kernel*=1.5;
    for(int pi=0;pi<(int)(sizeof(paths)/sizeof(paths[0]));pi++) {
        if(pi==exclude)continue;
        const RankPath *p=&paths[pi];Hypothesis hyp[195];unsigned nh=0;double norm=0;
        for(int error=-32;error<=32;error++) {
            int shift=cost-p->cost+error,sa=p->sa,ss=p->ss;
            for(int i=0;i<p->n;i++){sa+=div_at(p->normal[i][0]+shift);ss+=div_at(p->normal[i][1]+shift);}
            for(int nv=-1;nv<=1;nv++) {
                int a=sa,s=ss;
                if(nv==-1){a-=div_at(p->normal[p->n-1][0]+shift);s-=div_at(p->normal[p->n-1][1]+shift);}
                if(nv==1){a+=div_at(p->normal[p->n-1][0]+shift+1172);s+=div_at(p->normal[p->n-1][1]+shift+1172);}
                int dv=forward(seed,a,s,p,shift+nv*2344);
                if(dv>=0){double w=time_weight[abs(error)]*(nv==0?4:1);hyp[nh++]=(Hypothesis){(uint16_t)dv,w};norm+=w*kernel;}
            }
        }
        if(!nh)continue;
        double path_weight=1.0/(1.0+abs(cost-p->cost)/128.0);unsigned touched=0;
        for(unsigned i=0;i<nh;i++) {
            unsigned dv=hyp[i].dv;
            for(int d=-8;d<=8;d++)for(int h=-1;h<=1;h++) {
                uint16_t out=((((dv>>8)+d+h)&255)<<8)|(((dv&255)+d)&255);
                double w=hyp[i].w*shared_weight[abs(d)]*(h==0?1:.25)/norm*path_weight;
                scores[out]+=w;
                for(unsigned j=0;j<8;j++)if(out==shiny[j])touched|=1U<<j;
            }
        }
        for(unsigned j=0;j<8;j++)support[j]+=(touched>>j)&1;
    }
    count=0;for(unsigned i=0;i<65536;i++)if(scores[i]>0)order[count++]=i;
    qsort(order,count,sizeof(order[0]),compare);
    best_rank=0;best_index=0;
    for(unsigned j=0;j<8;j++) {
        unsigned r=rank7108_rank(shiny[j]);
        if(r && (!best_rank||r<best_rank)){best_rank=r;best_index=j;}
    }
    return count;
}
uint32_t rank7108_best_rank(void){return best_rank;}
uint16_t rank7108_best_shiny(void){return best_rank?shiny[best_index]:0;}
uint32_t rank7108_support(void){return best_rank?support[best_index]:0;}
uint16_t rank7108_top(unsigned i){return i<count?order[i]:0;}
double rank7108_weight(uint16_t dv){return scores[dv];}
const char *rank7108_model_id(void){return RANK7108_MODEL;}
