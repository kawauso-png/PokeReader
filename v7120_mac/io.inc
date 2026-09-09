#ifdef __3DS__
static int mac7119_open_sd(FS_Archive*sd){if(R_FAILED(fsInit()))return 0;if(R_FAILED(FSUSER_OpenArchive(sd,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")))){fsExit();return 0;}return 1;}
static int mac7119_write_file(const char*path,const void*data,uint32_t size){
 FS_Archive sd;if(!mac7119_open_sd(&sd))return 0;Writer w={0,0};
 Result e=FSUSER_OpenFile(&w.file,sd,fsMakePath(PATH_ASCII,path),FS_OPEN_WRITE|FS_OPEN_CREATE,0);int ok=!R_FAILED(e);
 if(ok)ok=!R_FAILED(FSFILE_SetSize(w.file,0))&&sd_put(&w,data,size);
 if(w.file){Result f=FSFILE_Flush(w.file),c=FSFILE_Close(w.file);ok=ok&&!R_FAILED(f)&&!R_FAILED(c);}
 FSUSER_CloseArchive(sd);fsExit();return ok;
}
int snapshot7119_prepare(void){uint32_t zero[32]={0};
 if(!mac7119_write_file("/luma/plugins/pokereader/mac_step.req",zero,sizeof(zero)))return 0;
 const char text[]="{\"software\":7120,\"phase\":\"ready\",\"guest_input_sent\":false,\"encounter_launch_armed\":false}\n";
 return mac7119_write_file("/luma/plugins/pokereader/mac_step.json",text,sizeof(text)-1);
}
int snapshot7119_request(uint32_t*w){
 FS_Archive sd;if(!mac7119_open_sd(&sd))return -1;Handle file=0;uint64_t size=0;uint32_t got=0;
 Result e=FSUSER_OpenFile(&file,sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/mac_step.req"),FS_OPEN_READ,0);int ok=!R_FAILED(e);
 if(ok)ok=!R_FAILED(FSFILE_GetSize(file,&size))&&size==128&&!R_FAILED(FSFILE_Read(file,&got,0,w,128))&&got==128;
 if(file){Result c=FSFILE_Close(file);ok=ok&&!R_FAILED(c);}FSUSER_CloseArchive(sd);fsExit();return ok?1:0;
}
int snapshot7119_report(const char*text,uint32_t n){return mac7119_write_file("/luma/plugins/pokereader/mac_step.json",text,n);}
int snapshot7120_samples(const void*data,uint32_t n){return mac7119_write_file("/luma/plugins/pokereader/mac_samples.bin",data,n);}
#endif
