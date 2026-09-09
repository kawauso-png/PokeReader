/* Explicitly invoked only after SELECT stopped hunting and all keys released.
 * This exports a private copy. It never resumes the guest or selects a DV. */
extern int snapshot7118_save(const Snapshot7116Meta*,const uint8_t*,const uint8_t*,const uint8_t*,uint32_t*,uint32_t);
uint32_t gate7118_export(uint32_t *pid_out) {
 uint32_t adv=0,st=suicune_native_pre_state(&adv),pid=0,heap=0,hashes[4];
 if(!(st&0x80000000U)||get_current_keys()!=0)return 1;
 if(svcGetProcessId(&pid,CUR_PROCESS_HANDLE)!=0)return 2;
 *pid_out=pid;
 for(uint32_t a=0x100000;a<0x1b1000;a+=4096)if(!is_memory_mapped(a))return 3;
 if(!clock_capture())return 4;
 uint64_t generation=svcGetSystemTick();
 uint8_t *data=suicune_shadow7113_capture(adv,&heap);if(!data)return 5;
 uint32_t rom=word(0x22f6c4);
 if(rom<0x08000000U||rom>0x13e00000U)return 6;
 for(uint32_t off=0;off<0x200000;off+=4096)if(!is_memory_mapped(rom+off))return 6;
 if(!is_memory_mapped(rom+0x1fffff))return 6;
 uint32_t after_adv=0,after=suicune_native_pre_state(&after_adv);
 if(after!=st||after_adv!=adv||get_current_keys()!=0)return 7;
 /* Reference schedule for offline analysis only; no plan is armed. */
 uint64_t reference_launch=generation+600ULL*clock_hz;
 uint64_t cycle=(reference_launch+5ULL*clock_hz)/4481233ULL+1;
 while((cycle&15U)!=14U)cycle++;
 Snapshot7116Meta m={.search_id=generation,.clock_ms=clock_ms,.clock_tick=clock_tick,
 .launch=reference_launch,.resume=cycle*4481233ULL,.check=0,.advance=adv,
 .seed=st&65535U,.rom_base=rom,.rom_size=0x200000,.heap_base=heap,.hz=clock_hz};
 if(!snapshot7118_save(&m,(const uint8_t*)0x100000,data,(const uint8_t*)(uintptr_t)rom,hashes,pid))return 8;
 return 0;
}
