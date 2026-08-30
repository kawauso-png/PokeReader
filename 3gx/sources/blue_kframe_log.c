#include <3ds.h>
#include <stdio.h>
#include <string.h>

u32 host_blue_kframe_append_csv(
    u32 slot,
    u32 total,
    u32 hits,
    u32 special_total,
    u32 special_hits,
    u32 frame_total,
    u32 frame_hits,
    u32 ignored)
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

    char row[256];
    int n = snprintf(row, sizeof(row),
        "kframe_validator,total,hits,special_total,special_hits,frame_total,frame_hits,ignored\n"
        "KFRAME,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
        (unsigned long)total,
        (unsigned long)hits,
        (unsigned long)special_total,
        (unsigned long)special_hits,
        (unsigned long)frame_total,
        (unsigned long)frame_hits,
        (unsigned long)ignored);

    u32 written = 0;
    r = FSFILE_Write(file, &written, off, row, n > 0 ? (u32)n : 0u, 0);
    if (R_SUCCEEDED(r))
        r = FSFILE_Flush(file);
    FSFILE_Close(file);
    fsExit();
    return R_SUCCEEDED(r) ? 0u : (u32)r;
}
