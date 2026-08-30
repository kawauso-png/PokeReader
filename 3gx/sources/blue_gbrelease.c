#include <3ds.h>
#include <stdio.h>
#include <string.h>

/*
 * Blue Mewtwo v7.3.1 SAFE marker.
 *
 * This deliberately does NOT create threads, install hooks, scan memory, or
 * perform file I/O while the Mewtwo transition is running. Rust calls mark()
 * on the already-validated GB-side hJoyHeld.A 1->0 transition. We only copy
 * values that blue_dvtrace.c has already sampled. After battle/CSV finalize,
 * append_csv() writes the marker as a tiny second CSV section.
 */

extern u32 host_blue_dvtrace_seq(void);
extern u32 host_blue_dvtrace_rng(void);
extern u32 host_blue_dvtrace_div(void);
extern u32 host_blue_dvtrace_battle_seq(void);

static bool gbrel_valid = false;
static u32 gbrel_seq = 0;
static u32 gbrel_rng = 0;
static u32 gbrel_div = 0;

void host_blue_gbrelease_reset(void)
{
    gbrel_valid = false;
    gbrel_seq = 0;
    gbrel_rng = 0;
    gbrel_div = 0;
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
    gbrel_valid = true;
}

static void write_bytes(Handle file, u64 *offset, const char *s, u32 len)
{
    u32 written = 0;
    if (R_SUCCEEDED(FSFILE_Write(file, &written, *offset, s, len, 0)))
        *offset += written;
}

u32 host_blue_gbrelease_append_csv(u32 slot)
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

    char line[256];
    int n = snprintf(
        line, sizeof(line),
        "\ngb_release_meta,seq,battle_seq,release_to_battle,rng_add,rng_sub,frame,div\n"
        "GBREL,%lu,%lu,%lu,%02X,%02X,%02X,%02X\n",
        (unsigned long)gbrel_seq,
        (unsigned long)battle_seq,
        (unsigned long)delta,
        add, sub, frame, div);
    if (n > 0)
        write_bytes(file, &off, line, (u32)n);

    FSFILE_Flush(file);
    FSFILE_Close(file);
    fsExit();
    return 1;
}

u32 host_blue_gbrelease_seq(void) { return gbrel_valid ? gbrel_seq : 0; }
u32 host_blue_gbrelease_valid(void) { return gbrel_valid ? 1u : 0u; }
