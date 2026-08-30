#include <3ds.h>
#include <stdio.h>
#include <string.h>

u32 host_blue_adaptive_append_csv(
    u32 slot, u32 ready, u32 clean_tail, u32 base, u32 base_hits,
    u32 residue20, u32 marker_hits, u32 marker_total,
    u32 core_hits, u32 core_total, u32 sub_count, u32 div_lock)
{
    if (slot == 0 || slot > 999u)
        return 0xFFFFFFFFu;

    Result r = fsInit();
    if (R_FAILED(r)) return (u32)r;

    FS_Archive sdmc;
    r = FSUSER_OpenArchive(&sdmc, ARCHIVE_SDMC, fsMakePath(PATH_EMPTY, ""));
    if (R_FAILED(r)) { fsExit(); return (u32)r; }

    char path[128];
    snprintf(path, sizeof(path),
             "/luma/plugins/pokereader/traces/mewtwo_trace_%04lu.csv",
             (unsigned long)slot);
    Handle file = 0;
    r = FSUSER_OpenFile(&file, sdmc, fsMakePath(PATH_ASCII, path), FS_OPEN_WRITE, 0);
    FSUSER_CloseArchive(sdmc);
    if (R_FAILED(r) || file == 0) { fsExit(); return (u32)r; }

    u64 off = 0;
    r = FSFILE_GetSize(file, &off);
    if (R_FAILED(r)) { FSFILE_Close(file); fsExit(); return (u32)r; }

    char row[384];
    int n = snprintf(row, sizeof(row),
        "adaptive_model,ready,clean_tail,base,base_hits,residue20,marker_hits,marker_total,core_hits,core_total,sub_count,div_lock\n"
        "ADAPT,%lu,%lu,%02lX,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
        (unsigned long)ready, (unsigned long)clean_tail, (unsigned long)(base & 0xFFu),
        (unsigned long)base_hits, (unsigned long)residue20,
        (unsigned long)marker_hits, (unsigned long)marker_total,
        (unsigned long)core_hits, (unsigned long)core_total,
        (unsigned long)sub_count, (unsigned long)div_lock);

    u32 written = 0;
    r = FSFILE_Write(file, &written, off, row, n > 0 ? (u32)n : 0u, 0);
    if (R_SUCCEEDED(r)) r = FSFILE_Flush(file);
    FSFILE_Close(file);
    fsExit();
    return R_SUCCEEDED(r) ? 0u : (u32)r;
}
