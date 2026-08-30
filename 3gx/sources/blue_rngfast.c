#include <3ds.h>
#include <stdio.h>
#include <string.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL
#define HRAM_SLOT 0x0021B6DCu
#define DIV_SLOT  0x0021B7B4u
#define PC_A_ADDR 0x0021B8F8u
#define PC_S_ADDR 0x0021B890u

#define HRAM_ADD_OFF   0x53u
#define HRAM_SUB_OFF   0x54u
#define HRAM_FRAME_OFF 0x55u

#define FAST_MAX 256u
#define FAST_STACK_SIZE 0x3000u

typedef struct
{
    u32 index;
    u32 coarse_seq;
    u16 pc_a;
    u16 pc_s;
    u8 add;
    u8 sub;
    u8 frame;
    u8 div;
    u8 kind; /* 0=start, 1=change, 2=stop */
} FastEvent;

extern u32 host_blue_dvtrace_seq(void);

static FastEvent fast_events[FAST_MAX];
static volatile u32 fast_count = 0;
static volatile u32 fast_dropped = 0;
static volatile bool fast_active = false;
static volatile bool fast_thread_ok = false;
static Handle fast_thread = 0;
static u8 fast_stack[FAST_STACK_SIZE] __attribute__((aligned(8)));
static u32 fast_hram = 0;
static u32 fast_divp = 0;
static u8 last_add = 0;
static u8 last_sub = 0;

static bool query_span_mapped(u32 start, u32 end)
{
    MemInfo info;
    PageInfo page;
    if (end < start)
        return false;
    if (svcQueryMemory(&info, &page, start) != 0)
        return false;
    if (info.state == MEMSTATE_FREE || info.state == MEMSTATE_RESERVED)
        return false;
    if (start < info.base_addr)
        return false;
    if ((start - info.base_addr) >= info.size)
        return false;
    return (end - info.base_addr) < info.size;
}

static void capture_event(u8 kind, bool force)
{
    if (fast_hram == 0 || fast_divp == 0)
        return;

    u8 add = *(vu8 *)(fast_hram + HRAM_ADD_OFF);
    u8 sub = *(vu8 *)(fast_hram + HRAM_SUB_OFF);
    if (!force && add == last_add && sub == last_sub)
        return;

    last_add = add;
    last_sub = sub;

    u32 slot = fast_count;
    if (slot >= FAST_MAX)
    {
        fast_dropped++;
        return;
    }

    FastEvent e;
    e.index = slot;
    e.coarse_seq = host_blue_dvtrace_seq();
    e.add = add;
    e.sub = sub;
    e.frame = *(vu8 *)(fast_hram + HRAM_FRAME_OFF);
    e.div = *(vu8 *)fast_divp;
    e.pc_a = query_span_mapped(PC_A_ADDR, PC_A_ADDR + 1u) ? *(vu16 *)PC_A_ADDR : 0;
    e.pc_s = query_span_mapped(PC_S_ADDR, PC_S_ADDR + 1u) ? *(vu16 *)PC_S_ADDR : 0;
    e.kind = kind;
    fast_events[slot] = e;
    fast_count = slot + 1u;
}

static void fast_sampler_main(void *arg)
{
    (void)arg;
    for (;;)
    {
        if (!fast_active)
        {
            svcSleepThread(1000000LL);
            continue;
        }

        /*
         * 3GX cannot use libctru threadCreate() without pulling APT runtime
         * globals that do not exist in this plugin environment. This raw SVC
         * thread runs only during the ~9 GB-frame release->DV window. A very
         * short sleep gives the emulator time to execute between observations.
         */
        capture_event(1u, false);
        svcSleepThread(1000LL);
    }
}

void host_blue_rngfast_init(void)
{
    if (fast_thread_ok)
        return;
    if (get_title_id() != BLUE_JP_TITLE_ID)
        return;

    u32 *stack_top = (u32 *)(fast_stack + FAST_STACK_SIZE);
    Result r = svcCreateThread(&fast_thread, fast_sampler_main, 0, stack_top, 0x2F, -2);
    fast_thread_ok = R_SUCCEEDED(r);
}

u32 host_blue_rngfast_start(void)
{
    fast_active = false;
    fast_count = 0;
    fast_dropped = 0;
    memset(fast_events, 0, sizeof(fast_events));

    if (get_title_id() != BLUE_JP_TITLE_ID)
        return 0;
    host_blue_rngfast_init();
    if (!fast_thread_ok)
        return 0;

    if (!query_span_mapped(HRAM_SLOT, HRAM_SLOT + 3u) ||
        !query_span_mapped(DIV_SLOT, DIV_SLOT + 3u))
        return 0;

    fast_hram = *(vu32 *)HRAM_SLOT;
    fast_divp = *(vu32 *)DIV_SLOT;
    if (!query_span_mapped(fast_hram + HRAM_ADD_OFF, fast_hram + HRAM_FRAME_OFF) ||
        !query_span_mapped(fast_divp, fast_divp))
        return 0;

    last_add = *(vu8 *)(fast_hram + HRAM_ADD_OFF);
    last_sub = *(vu8 *)(fast_hram + HRAM_SUB_OFF);
    capture_event(0u, true);
    fast_active = true;
    return 1;
}

void host_blue_rngfast_stop(void)
{
    if (!fast_active)
        return;
    fast_active = false;
    /* Let an in-flight sampler iteration retire, then capture final state. */
    svcSleepThread(1000000LL);
    capture_event(2u, true);
}

static void write_bytes(Handle file, u64 *offset, const char *s, u32 len)
{
    u32 written = 0;
    if (R_SUCCEEDED(FSFILE_Write(file, &written, *offset, s, len, 0)))
        *offset += written;
}

u32 host_blue_rngfast_append_csv(u32 slot)
{
    if (slot == 0)
        return 0;

    Result r = fsInit();
    if (R_FAILED(r))
        return 0;

    FS_Archive sdmc;
    r = FSUSER_OpenArchive(&sdmc, ARCHIVE_SDMC, fsMakePath(PATH_EMPTY, ""));
    if (R_FAILED(r))
    {
        fsExit();
        return 0;
    }

    char path[128];
    snprintf(path, sizeof(path), "/luma/plugins/pokereader/traces/mewtwo_trace_%04lu.csv", (unsigned long)slot);
    Handle file = 0;
    r = FSUSER_OpenFile(&file, sdmc, fsMakePath(PATH_ASCII, path), FS_OPEN_WRITE, 0);
    FSUSER_CloseArchive(sdmc);
    if (R_FAILED(r) || file == 0)
    {
        fsExit();
        return 0;
    }

    u64 off = 0;
    if (R_FAILED(FSFILE_GetSize(file, &off)))
    {
        FSFILE_Close(file);
        fsExit();
        return 0;
    }

    char line[256];
    int n = snprintf(line, sizeof(line),
        "\nfast_meta,count,dropped,thread_ok\nFAST,%lu,%lu,%u\n"
        "fast_index,coarse_seq,rng_add,rng_sub,frame,div,pc_a,pc_s,kind\n",
        (unsigned long)fast_count, (unsigned long)fast_dropped, fast_thread_ok ? 1u : 0u);
    if (n > 0)
        write_bytes(file, &off, line, (u32)n);

    u32 count = fast_count;
    if (count > FAST_MAX)
        count = FAST_MAX;
    for (u32 i = 0; i < count; i++)
    {
        FastEvent e = fast_events[i];
        n = snprintf(line, sizeof(line), "%lu,%lu,%02X,%02X,%02X,%02X,%04X,%04X,%u\n",
            (unsigned long)e.index, (unsigned long)e.coarse_seq,
            e.add, e.sub, e.frame, e.div, e.pc_a, e.pc_s, e.kind);
        if (n > 0)
            write_bytes(file, &off, line, (u32)n);
    }

    FSFILE_Flush(file);
    FSFILE_Close(file);
    fsExit();
    return 1;
}

u32 host_blue_rngfast_count(void) { return fast_count; }
u32 host_blue_rngfast_dropped(void) { return fast_dropped; }
u32 host_blue_rngfast_thread_ok(void) { return fast_thread_ok ? 1u : 0u; }
