#ifdef __3DS__
/* Fixed-name rendezvous for the read-only GDB SD transport. */
int snapshot7118_save(const Snapshot7116Meta*m,const uint8_t*code,const uint8_t*data,const uint8_t*rom,uint32_t hashes[4],uint32_t pid){
 if(R_FAILED(fsInit()))return 0;FS_Archive sd;
 if(R_FAILED(FSUSER_OpenArchive(&sd,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")))){fsExit();return 0;}
 const char *manifest="/luma/plugins/pokereader/mac_state.json";
 const char *payload="/luma/plugins/pokereader/mac_state.bin";
 Writer mw={0,0},bw={0,0};
 Result e=FSUSER_OpenFile(&mw.file,sd,fsMakePath(PATH_ASCII,manifest),FS_OPEN_WRITE|FS_OPEN_CREATE,0);
 int ok=!R_FAILED(e);
 /* Invalidate previous manifest before replacing its payload. */
 if(ok)ok=!R_FAILED(FSFILE_SetSize(mw.file,0))&&!R_FAILED(FSFILE_Flush(mw.file));
 if(ok){e=FSUSER_OpenFile(&bw.file,sd,fsMakePath(PATH_ASCII,payload),FS_OPEN_WRITE|FS_OPEN_CREATE,0);ok=!R_FAILED(e);}
 if(ok)ok=!R_FAILED(FSFILE_SetSize(bw.file,0))&&snapshot7116_emit(m,code,data,rom,sd_put,&bw,hashes);
 if(bw.file){Result f=FSFILE_Flush(bw.file),c=FSFILE_Close(bw.file);ok=ok&&!R_FAILED(f)&&!R_FAILED(c);}
 if(ok){char text[768];int n=snprintf(text,sizeof(text),
 "{\"software\":7118,\"state_id\":\"%016llX\",\"pid_real\":%lu,\"pid_gdb\":%lu,\"advance\":%lu,\"seed\":\"%04lX\",\"clock_tick\":%llu,\"clock_ms\":%llu,\"snapshot_bytes\":3145864,\"hashes\":[%lu,%lu,%lu,%lu],\"snapshot\":\"/luma/plugins/pokereader/mac_state.bin\",\"plan_armed\":false,\"guest_input_sent\":false}\n",
 (unsigned long long)m->search_id,(unsigned long)pid,(unsigned long)(pid+1),(unsigned long)m->advance,(unsigned long)m->seed,
 (unsigned long long)m->clock_tick,(unsigned long long)m->clock_ms,(unsigned long)hashes[0],(unsigned long)hashes[1],(unsigned long)hashes[2],(unsigned long)hashes[3]);
 ok=n>0&&(unsigned)n<sizeof(text)&&sd_put(&mw,text,(uint32_t)n);}
 if(mw.file){Result f=FSFILE_Flush(mw.file),c=FSFILE_Close(mw.file);ok=ok&&!R_FAILED(f)&&!R_FAILED(c);}
 FSUSER_CloseArchive(sd);fsExit();return ok;
}
#endif
