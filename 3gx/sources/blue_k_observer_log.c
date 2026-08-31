#include <3ds.h>
#include <stdio.h>
#include <string.h>

typedef struct
{
    u32 seq;
    u8 k;
    u8 div_step;
    u8 gap;
    u8 phase4;
} KObsRow;

u32 host_blue_kobserver_append_csv(
    u32 slot,
    const KObsRow *rows,
    u32 count,
    u32 valid_total,
    u32 invalid_total)
{
    if (slot == 0 || slot > 999u || rows == NULL || count > 512u)
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

    char buf[160];
    u32 written = 0;
    int n = snprintf(buf, sizeof(buf),
                     "k_observer_summary,valid_total,invalid_total,arm_rows\nKOBSSUM,%lu,%lu,%lu\n",
                     (unsigned long)valid_total,
                     (unsigned long)invalid_total,
                     (unsigned long)count);
    r = FSFILE_Write(file, &written, off, buf, n > 0 ? (u32)n : 0u, 0);
    if (R_FAILED(r))
        goto done;
    off += written;

    const char *hdr = "k_observer,seq,k,div_step,gap,phase4\n";
    written = 0;
    r = FSFILE_Write(file, &written, off, hdr, (u32)strlen(hdr), 0);
    if (R_FAILED(r))
        goto done;
    off += written;

    for (u32 i = 0; i < count; i++)
    {
        n = snprintf(buf, sizeof(buf),
                     "KOBS,%lu,%02X,%02X,%u,%u\n",
                     (unsigned long)rows[i].seq,
                     rows[i].k,
                     rows[i].div_step,
                     rows[i].gap,
                     rows[i].phase4);
        written = 0;
        r = FSFILE_Write(file, &written, off, buf, n > 0 ? (u32)n : 0u, 0);
        if (R_FAILED(r))
            goto done;
        off += written;
    }

    r = FSFILE_Flush(file);

done:
    FSFILE_Close(file);
    fsExit();
    return R_SUCCEEDED(r) ? 0u : (u32)r;
}
