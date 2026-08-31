#include <3ds.h>
#include <stdio.h>

u32 host_blue_forecast_append_csv(
    u32 slot,
    u32 valid,
    u32 candidates,
    u32 shiny,
    u32 phase_count,
    u32 next_horizon,
    u32 next_candidates,
    u32 next_shiny,
    u32 target_seq,
    u32 actual_raw,
    u32 actual_hit)
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

    char row[360];
    int n = snprintf(row, sizeof(row),
        "shiny_forecast,valid,candidates,shiny,phase_count,next_horizon,next_candidates,next_shiny,target_seq,actual_raw,actual_hit\n"
        "FORECAST,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%04lX,%lu\n",
        (unsigned long)valid,
        (unsigned long)candidates,
        (unsigned long)shiny,
        (unsigned long)phase_count,
        (unsigned long)next_horizon,
        (unsigned long)next_candidates,
        (unsigned long)next_shiny,
        (unsigned long)target_seq,
        (unsigned long)(actual_raw & 0xFFFFu),
        (unsigned long)actual_hit);

    u32 written = 0;
    r = FSFILE_Write(file, &written, off, row, n > 0 ? (u32)n : 0u, 0);
    if (R_SUCCEEDED(r))
        r = FSFILE_Flush(file);
    FSFILE_Close(file);
    fsExit();
    return R_SUCCEEDED(r) ? 0u : (u32)r;
}
