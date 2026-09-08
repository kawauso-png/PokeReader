static inline __attribute__((always_inline)) void arm7113_const(Arm7113*a,ArmRead read,ArmWrite write,uint32_t pc,uint32_t op){
 uint32_t next=pc+4;a->steps++;
 if((op&0xff70f000)==0xf550f000){a->r[15]=next;return;}
 if(!cond(a->flags,op>>28)){if((op>>28)==15){a->error=1;goto bad;}a->r[15]=next;return;}
 unsigned rn=(op>>16)&15,rd=(op>>12)&15,rm=op&15;uint32_t x=rr(a,rn,pc),v=0;
 switch((op>>25)&7){case 2:goto single_transfer;case 3:if(!(op&16))goto single_transfer;break;case 4:goto multiple_transfer;case 5:goto branch_transfer;}
 if((op&0x0ffffff0)==0x012fff10||(op&0x0ffffff0)==0x012fff30){v=rr(a,rm,pc);if(op&0x20)a->r[14]=pc+4;if(v&1){a->error=2;goto bad;}next=v;}
 else if((op&0x0ff000f0)==0x01600010){v=rr(a,rm,pc);a->r[rd]=v?__builtin_clz(v):32;}
 else if((op&0x0fbf0fff)==0x010f0000){a->r[rd]=a->flags|0x10;}
 else if((op&0x0fb0fff0)==0x0120f000||(op&0x0fb0f000)==0x0320f000){v=(op&(1<<25))?rot(op&255,((op>>8)&15)*2):rr(a,rm,pc);if(op&(1<<19))a->flags=(a->flags&0x0fffffff)|(v&0xf0000000);}
 else if((op&0x0f8000f0)==0x00800090){unsigned hi=rn,lo=rd;uint64_t t;if(op&(1<<22))t=(int64_t)(int32_t)rr(a,rm,pc)*(int32_t)rr(a,(op>>8)&15,pc);else t=(uint64_t)rr(a,rm,pc)*rr(a,(op>>8)&15,pc);if(op&(1<<21))t+=((uint64_t)a->r[hi]<<32)|a->r[lo];a->r[lo]=t;a->r[hi]=t>>32;if(op&(1<<20)){a->flags=(a->flags&~(N|Z))|((t>>32)&N)|(t?0:Z);}}
 else if((op&0x0fc000f0)==0x00000090){v=rr(a,rm,pc)*rr(a,(op>>8)&15,pc);if(op&(1<<21))v+=rr(a,rd,pc);a->r[rn]=v;if(op&(1<<20))nz(a,v);}
 else if((op&0x0fb00ff0)==0x01000090){unsigned n=(op&(1<<22))?1:4;v=read(x,n);write(x,rr(a,rm,pc),n);a->r[rd]=v;}
 else if((op&0x0e000090)==0x00000090 && (op&0x60)){
  uint32_t off=(op&(1<<22))?((op>>4)&0xf0)|(op&15):rr(a,rm,pc);uint32_t dest=(op&(1<<23))?x+off:x-off;uint32_t addr=(op&(1<<24))?dest:x;
  unsigned type=(op>>5)&3;if(op&(1<<20)){if(type==1)v=read(addr,2);else if(type==2)v=(uint32_t)(int32_t)(int8_t)read(addr,1);else v=(uint32_t)(int32_t)(int16_t)read(addr,2);a->r[rd]=v;}
  else{if(type==1)write(addr,rr(a,rd,pc),2);else if(type==2){a->r[rd]=read(addr,4);a->r[rd+1]=read(addr+4,4);}else{write(addr,rr(a,rd,pc),4);write(addr+4,rr(a,rd+1,pc),4);}}if(!(op&(1<<24))||(op&(1<<21)))a->r[rn]=dest;
 }
 else if((op&0x0fff0ff0)==0x06bf0fb0){v=rr(a,rm,pc);a->r[rd]=((v&0x00ff00ff)<<8)|((v&0xff00ff00)>>8);}
 else if((op&0x0fff0ff0)==0x06bf0f30){a->r[rd]=__builtin_bswap32(rr(a,rm,pc));}
 else if((op&0x0fff0ff0)==0x06ff0fb0){v=rr(a,rm,pc);a->r[rd]=(uint32_t)(int32_t)(int16_t)(((v&255)<<8)|((v>>8)&255));}
 else if((op&0x0f8000f0)==0x06800070){unsigned k=(op>>20)&7;v=rot(rr(a,rm,pc),((op>>10)&3)*8);if(k==7)v&=65535;else if(k==6)v&=255;else if(k==3)v=(uint32_t)(int32_t)(int16_t)v;else if(k==2)v=(uint32_t)(int32_t)(int8_t)v;else{a->error=8;goto bad;}a->r[rd]=v+(rn==15?0:x);}
 else if((op&0x0c000000)==0x04000000){single_transfer:;
  uint32_t off=op&4095;if(op&(1<<25)){if(op&16){a->error=4;goto bad;}unsigned carry=!!(a->flags&C);off=shift(rr(a,rm,pc),(op>>5)&3,(op>>7)&31,0,&carry);}
  uint32_t dest=(op&(1<<23))?x+off:x-off,addr=(op&(1<<24))?dest:x;unsigned n=(op&(1<<22))?1:4;
  if(op&(1<<20)){v=read(addr,n);if(rd==15){if(v&1){a->error=2;goto bad;}next=v;}else a->r[rd]=v;}else write(addr,rd==15?pc+12:a->r[rd],n);
  if(!(op&(1<<24))||(op&(1<<21)))a->r[rn]=dest;
 }
 else if((op&0x0e000000)==0x08000000){multiple_transfer:;
  if(op&(1<<22)){a->error=5;goto bad;}unsigned list=op&65535,count=__builtin_popcount(list);uint32_t addr=(op&(1<<23))?x:x-4*count;if(!!(op&(1<<24))==!!(op&(1<<23)))addr+=4;
  for(unsigned i=0;i<16;i++)if(list&(1<<i)){if(op&(1<<20)){v=read(addr,4);if(i==15){if(v&1){a->error=2;goto bad;}next=v;}else a->r[i]=v;}else write(addr,i==15?pc+12:a->r[i],4);addr+=4;}
  if(op&(1<<21))a->r[rn]=(op&(1<<23))?x+count*4:x-count*4;
 }
 else if((op&0x0e000000)==0x0a000000){branch_transfer:;int32_t off=(int32_t)(op<<8)>>6;if(op&(1<<24))a->r[14]=pc+4;next=pc+8+off;}
 else if((op&0x0c000000)==0){
  unsigned k=(op>>21)&15,s=!!(op&(1<<20)),carry=!!(a->flags&C);uint32_t y;
  if(op&(1<<25)){unsigned n=((op>>8)&15)*2;y=rot(op&255,n);if(n)carry=y>>31;}
  else{unsigned byreg=!!(op&16),n=byreg?(rr(a,(op>>8)&15,pc)&255):(op>>7)&31;y=shift(rm==15&&byreg?pc+12:rr(a,rm,pc),(op>>5)&3,n,byreg,&carry);}
  if(k==0||k==8)v=x&y;else if(k==1||k==9)v=x^y;else if(k==2||k==10)v=add(a,x,~y,1,s);else if(k==3)v=add(a,y,~x,1,s);else if(k==4||k==11)v=add(a,x,y,0,s);else if(k==5)v=add(a,x,y,!!(a->flags&C),s);else if(k==6)v=add(a,x,~y,!!(a->flags&C),s);else if(k==7)v=add(a,y,~x,!!(a->flags&C),s);else if(k==12)v=x|y;else if(k==13)v=y;else if(k==14)v=x&~y;else v=~y;
  if(s&&(k==0||k==1||k==8||k==9||k>=12)){nz(a,v);a->flags=(a->flags&~C)|(carry?C:0);}
  if(k<8||k>=12){if(rd==15){if(s){a->error=6;goto bad;}next=v;}else a->r[rd]=v;}
 }
 else {a->error=7;goto bad;}
 a->r[15]=next;return;
 bad:a->error_pc=pc;a->error_op=op;
}
