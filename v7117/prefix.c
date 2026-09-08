#include "prefix.h"
#include "prefix_data.h"
unsigned prefix7117_model_count(void){return PREFIX7117_MODELS;}
unsigned prefix7117_offers(uint16_t seed,uint16_t phase){
 unsigned offers=0;
 for(unsigned j=0;j<PREFIX7117_MODELS;j++){
  const Prefix7117Path*p=&prefix7117_paths[j];unsigned a=seed>>8,s=seed&255,first=0,hi=0,lo=0;
  for(unsigned k=0;k<(unsigned)p->normal+p->final;k++){
   unsigned at=p->offset+2*k,v=(((unsigned)prefix7117_phases[at]+phase)&16383)>>6,w=(((unsigned)prefix7117_phases[at+1]+phase)&16383)>>6;
   unsigned sum=a+v;a=sum&255;s=(s-w-(sum>>8))&255;
   if(k==p->normal)first=s;hi=lo;lo=s;
  }
  for(int d=-8;d<=8;d++){
   unsigned f=(first+d)&255,h=(hi+d)&255,l=(lo+d)&255,dv=h*256+l;
   if((f>=192)==(p->final==4)&&(dv&4095)==0xaaa&&((dv>>12)&2)){offers++;break;}
  }
 }
 return offers;
}
