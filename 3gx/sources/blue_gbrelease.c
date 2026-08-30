#include <3ds.h>
#include <stdio.h>
#include <string.h>

/*
 * Blue Mewtwo v7.3.3 SAFE IO marker.
 *
 * Critical-path rule: no threads, hooks, scans, sleeps or file I/O between
 * GB-side A release and DV generation. mark() copies the already-sampled
 * seq/RNG/DIV and performs only five direct byte reads from the already-known
 * flat GB IO block. All SD writes and phase classification stay post-battle.
 */

extern u32 host_blue_dvtrace_seq(void);
extern u32 host_blue_dvtrace_rng(void);
extern u32 host_blue_dvtrace_div(void);
extern u32 host_blue_dvtrace_div_ptr(void);
extern u32 host_blue_dvtrace_battle_seq(void);

static bool gbrel_valid = false;
static bool gbrel_io_valid = false;
static u32 gbrel_seq = 0;
static u32 gbrel_rng = 0;
static u32 gbrel_div = 0;
static u8 gbrel_tima = 0; /* FF05, div_ptr + 01 */
static u8 gbrel_tac = 0;  /* FF07, div_ptr + 03 */
static u8 gbrel_if = 0;   /* FF0F, div_ptr + 0B */
static u8 gbrel_stat = 0; /* FF41, div_ptr + 3D */
static u8 gbrel_ly = 0;   /* FF44, div_ptr + 40 */

void host_blue_gbrelease_reset(void)
{
    gbrel_valid = false;
    gbrel_io_valid = false;
    gbrel_seq = 0;
    gbrel_rng = 0;
    gbrel_div = 0;
    gbrel_tima = 0;
    gbrel_tac = 0;
    gbrel_if = 0;
    gbrel_stat = 0;
    gbrel_ly = 0;
}

void host_blue_gbrelease_mark(void)
{
    if (gbrel_valid)
        return;

    u32 seq = host_blue_dvtrace_seq();
    if (seq == 0)
        return;

    gbrel_seq = seq;
    gbrel_rng = host_blue_dvtrace_rng();
    gbrel_div = host_blue_dvtrace_div();

    /*
     * host_blue_dvtrace_sample() has already validated div_ptr immediately
     * before this call. FF04..FF44 live in the same flat mirrored IO block.
     * Deliberately avoid svcQueryMemory here: only five volatile byte reads.
     */
    u32 divp = host_blue_dvtrace_div_ptr();
    if (divp != 0)
    {
        gbrel_tima = *(vu8 *)(divp + 0x01u);
        gbrel_tac = *(vu8 *)(divp + 0x03u);
        gbrel_if = *(vu8 *)(divp + 0x0Bu);
        gbrel_stat = *(vu8 *)(divp + 0x3Du);
        gbrel_ly = *(vu8 *)(divp + 0x40u);
        gbrel_io_valid = true;
    }

    gbrel_valid = true;
}

static void write_bytes(Handle file, u64 *offset, const char *s, u32 len)
{
    u32 written = 0;
    if (R_SUCCEEDED(FSFILE_Write(file, &written, *offset, s, len, 0)))
        *offset += written;
}

u32 host_blue_gbrelease_append_csv(u32 slot, u32 pre_seq, u32 pre_rng,
                                   u32 pre_div, u32 phase_offset,
                                   u32 dvhigh_first_div)
{
    if (slot == 0 || !gbrel_valid)
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
    snprintf(path, sizeof(path),
             "/luma/plugins/pokereader/traces/mewtwo_trace_%04lu.csv",
             (unsigned long)slot);

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

    u32 battle_seq = host_blue_dvtrace_battle_seq();
    u32 delta = (battle_seq >= gbrel_seq) ? (battle_seq - gbrel_seq) : 0;
    u8 add = (u8)((gbrel_rng >> 16) & 0xFFu);
    u8 sub = (u8)((gbrel_rng >> 8) & 0xFFu);
    u8 frame = (u8)(gbrel_rng & 0xFFu);
    u8 div = (u8)gbrel_div;

    u8 pre_add = (u8)((pre_rng >> 16) & 0xFFu);
    u8 pre_sub = (u8)((pre_rng >> 8) & 0xFFu);
    u8 pre_frame = (u8)(pre_rng & 0xFFu);
    bool known_phase = phase_offset == 90u || phase_offset == 91u || phase_offset == 94u;

    char line[640];
    int n = snprintf(
        line, sizeof(line),
        "\ngb_release_meta,seq,battle_seq,release_to_battle,rng_add,rng_sub,frame,div,"
        "release_io_valid,release_tima,release_tac,release_if,release_stat,release_ly,"
        "pre_seq,pre_rng_add,pre_rng_sub,pre_frame,pre_div,dvhigh_first_div,phase_offset,phase_known\n"
        "GBREL,%lu,%lu,%lu,%02X,%02X,%02X,%02X,%u,%02X,%02X,%02X,%02X,%02X,"
        "%lu,%02X,%02X,%02X,%02X,%02X,%lu,%u\n",
        (unsigned long)gbrel_seq,
        (unsigned long)battle_seq,
        (unsigned long)delta,
        add, sub, frame, div,
        gbrel_io_valid ? 1u : 0u,
        gbrel_tima, gbrel_tac, gbrel_if, gbrel_stat, gbrel_ly,
        (unsigned long)pre_seq,
        pre_add, pre_sub, pre_frame, (u8)pre_div,
        (u8)dvhigh_first_div,
        (unsigned long)phase_offset,
        known_phase ? 1u : 0u);
    if (n > 0)
        write_bytes(file, &off, line, (u32)n);

    FSFILE_Flush(file);
    FSFILE_Close(file);
    fsExit();
    return 1;
}

u32 host_blue_gbrelease_seq(void) { return gbrel_valid ? gbrel_seq : 0; }
u32 host_blue_gbrelease_valid(void) { return gbrel_valid ? 1u : 0u; }
