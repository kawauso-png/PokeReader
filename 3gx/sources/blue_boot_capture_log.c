#include <3ds.h>
#include <stdio.h>
#include <string.h>

typedef struct
{
    u32 seq;
    u32 rng;
    u8 div;
    u8 status;
    u8 valid;
    u8 first;
    u8 second;
    u8 k;
    u8 div_step;
    u8 gap;
} BootRow;

u32 host_blue_bootcapture_append_csv(
    u32 slot,
    const BootRow *rows,
    u32 count,
    u32 valid_total,
    u32 invalid_total)
{
    if (slot == 0 || slot > 999u || rows == NULL || count > 2048u)
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

    char buf[192];
    u32 written = 0;
    int n = snprintf(buf, sizeof(buf),
        "boot_capture_summary,arm_rows,valid_rows,invalid_rows\n"
        "BOOTSUM,%lu,%lu,%lu\n",
        (unsigned long)count,
        (unsigned long)valid_total,
        (unsigned long)invalid_total);
    r = FSFILE_Write(file, &written, off, buf, n > 0 ? (u32)n : 0u, 0);
    if (R_FAILED(r))
        goto done;
    off += written;

    const char *hdr =
        "boot_capture,seq,rng_add,rng_sub,frame,div,status,valid,first,second,k,div_step,gap\n";
    written = 0;
    r = FSFILE_Write(file, &written, off, hdr, (u32)strlen(hdr), 0);
    if (R_FAILED(r))
        goto done;
    off += written;

    for (u32 i = 0; i < count; i++)
    {
        u32 rng = rows[i].rng;
        n = snprintf(buf, sizeof(buf),
            "BOOT,%lu,%02X,%02X,%02X,%02X,%02X,%u,%02X,%02X,%02X,%02X,%u\n",
            (unsigned long)rows[i].seq,
            (unsigned int)((rng >> 16) & 0xFFu),
            (unsigned int)((rng >> 8) & 0xFFu),
            (unsigned int)(rng & 0xFFu),
            rows[i].div,
            rows[i].status,
            rows[i].valid,
            rows[i].first,
            rows[i].second,
            rows[i].k,
            rows[i].div_step,
            rows[i].gap);
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
