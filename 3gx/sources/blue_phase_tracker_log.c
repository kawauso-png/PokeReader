#include <3ds.h>
#include <stdio.h>
#include <string.h>

u32 host_blue_phase_tracker_append_csv(
    u32 slot,
    u32 transitions,
    u32 fits,
    u32 subs,
    u32 lock_prefix,
    u32 forecast_checks,
    u32 forecast_hits,
    u32 resets)
{
    if (slot == 0 || slot > 999u)
        return 0xFFFFFFFFu;

    Result r = fsInit();
    if (R_FAILED(r))
        return (u32)r;

    FS_Archive sdmc;
    r = FSUSER_OpenArchive(&sdmc, ARCHIVE_SDMC, fsMakePath(PATH_EMPTY, ""));
    if (R_FAILED(r))
    {
        fsExit();
        return (u32)r;
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
        return (u32)r;
    }

    u64 off = 0;
    r = FSFILE_GetSize(file, &off);
    if (R_FAILED(r))
    {
        FSFILE_Close(file);
        fsExit();
        return (u32)r;
    }

    const char *hdr =
        "phase_tracker,arm_transitions,arm_fits,arm_subs,arm_lock_prefix,forecast_checks,forecast_hits,resets\n";
    char row[256];
    int n = snprintf(row, sizeof(row),
                     "DIVPHASE,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
                     (unsigned long)transitions,
                     (unsigned long)fits,
                     (unsigned long)subs,
                     (unsigned long)lock_prefix,
                     (unsigned long)forecast_checks,
                     (unsigned long)forecast_hits,
                     (unsigned long)resets);

    u32 written = 0;
    r = FSFILE_Write(file, &written, off, hdr, (u32)strlen(hdr), 0);
    if (R_SUCCEEDED(r))
    {
        off += written;
        written = 0;
        r = FSFILE_Write(file, &written, off, row, n > 0 ? (u32)n : 0u, 0);
    }
    if (R_SUCCEEDED(r))
        FSFILE_Flush(file);

    FSFILE_Close(file);
    fsExit();
    return R_SUCCEEDED(r) ? 0u : (u32)r;
}
