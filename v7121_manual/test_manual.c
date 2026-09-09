#include <assert.h>
#include <stdio.h>
enum {KEY_L=1,KEY_R=2,KEY_START=4,KEY_SELECT=8,KEY_A=16};
#include "manual.h"
int main(void){
    Manual7121 m={0};
    assert(manual7121_poll(&m,KEY_L,KEY_L|KEY_R)==MANUAL_WAIT && !m.pending);
    for(unsigned action=MANUAL_STEP;action<=MANUAL_EXPORT;action++){
        unsigned key=action==MANUAL_STEP?KEY_L:action==MANUAL_RUN?KEY_START:KEY_SELECT;
        assert(manual7121_poll(&m,key,key)==MANUAL_WAIT);
        for(unsigned i=0;i<100;i++)assert(manual7121_poll(&m,0,key)==MANUAL_WAIT);
        assert(manual7121_poll(&m,KEY_A,KEY_A)==MANUAL_WAIT);
        assert(manual7121_poll(&m,0,0)==action);
        for(unsigned i=0;i<100;i++)assert(manual7121_poll(&m,0,0)==MANUAL_WAIT);
    }
    assert(manual7121_poll(&m,KEY_START,KEY_START|KEY_L)==MANUAL_WAIT && !m.pending);
    puts("PASS: LR never steps; L/START/SELECT act once after all keys release");
}
