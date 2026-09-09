/* Independent terminal record: mac_step.json remains an acceptance receipt. */
#include "events7123.h"
static struct Events7123 events7123;
static void gate7123_begin(void){events7123_begin(&events7123,mac7119_nonce,mac7119_requested_id,advance,selected,launch,resume,svcGetSystemTick());}
void gate7123_note(uint32_t kind,uint64_t tick,uint32_t keys,uint32_t detail){events7123_add(&events7123,kind,tick,keys,detail);}
int gate7123_finish(uint32_t kind,uint64_t tick,uint32_t keys,uint32_t detail){
 if(!events7123.nonce||events7123.finished)return 1;
 events7123_add(&events7123,kind,tick,keys,detail);events7123.finished=1;
 char path[128],line[1536];int n=events7123_render(&events7123,line,sizeof(line));
 snprintf(path,sizeof(path),"/luma/plugins/pokereader/traces/mac7123_%016llX.csv",(unsigned long long)events7123.nonce);
 return n&&append_file(path,line,1);
}
