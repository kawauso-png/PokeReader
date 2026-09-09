/* Host pause control only. No guest memory or synthetic key writes. */
enum { MANUAL_WAIT, MANUAL_STEP, MANUAL_RUN, MANUAL_EXPORT };
typedef struct { unsigned pending; } Manual7121;
static unsigned manual7121_poll(Manual7121 *m,unsigned edge,unsigned held){
    if(m->pending){
        if(held)return MANUAL_WAIT;
        unsigned action=m->pending;m->pending=0;return action;
    }
    /* A pause chord (L+R) must never count as an L step. */
    if(held==KEY_L && (edge&KEY_L))m->pending=MANUAL_STEP;
    else if(held==KEY_START && (edge&KEY_START))m->pending=MANUAL_RUN;
    else if(held==KEY_SELECT && (edge&KEY_SELECT))m->pending=MANUAL_EXPORT;
    return MANUAL_WAIT;
}
