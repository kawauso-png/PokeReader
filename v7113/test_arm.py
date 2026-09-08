"""Differential register/flag tests against Unicorn (Mac developer test)."""
from pathlib import Path
import ctypes as ct, random, struct, subprocess, tempfile
import unicorn
from unicorn import arm_const as ar
r=Path(__file__).resolve().parent
class CPU(ct.Structure):
 _fields_=[('r',ct.c_uint32*16),('flags',ct.c_uint32),('error',ct.c_uint32),('pc',ct.c_uint32),('op',ct.c_uint32),('steps',ct.c_uint64)]
READ=ct.CFUNCTYPE(ct.c_uint32,ct.c_uint32,ct.c_uint)
WRITE=ct.CFUNCTYPE(None,ct.c_uint32,ct.c_uint32,ct.c_uint)
with tempfile.TemporaryDirectory() as td:
 lib=Path(td)/'arm.so';subprocess.run(['cc','-O2','-shared','-fPIC',str(r/'arm_core.c'),'-o',str(lib)],check=True)
 c=ct.CDLL(str(lib));c.arm7113_step.argtypes=[ct.POINTER(CPU),READ,WRITE]
 uc=unicorn.Uc(unicorn.UC_ARCH_ARM,unicorn.UC_MODE_ARM);uc.mem_map(0x1000,4096)
 rng=random.Random(7113);regs=[getattr(ar,'UC_ARM_REG_R'+str(i)) for i in range(13)]+[ar.UC_ARM_REG_SP,ar.UC_ARM_REG_LR,ar.UC_ARM_REG_PC]
 opcode=0
 @READ
 def read(a,n):
  assert a==0x1000 and n==4
  return opcode
 @WRITE
 def write(a,v,n):raise AssertionError('register test wrote memory')
 cases=[]
 for _ in range(4000):
  kind=rng.choice([0,1,2]);k=rng.randrange(16);rd,rn,rm,rs=[rng.randrange(13) for _ in range(4)];s=rng.randrange(2) if k not in (8,9,10,11) else 1
  if k in (8,9,10,11):rd=0
  if k in (13,15):rn=0
  op=(rng.randrange(15)<<28)|(k<<21)|(s<<20)|(rn<<16)|(rd<<12)
  if kind==0:op|=1<<25|rng.randrange(4096)
  elif kind==1:op|=rng.randrange(32)<<7|rng.randrange(4)<<5|rm
  else:op|=rs<<8|rng.randrange(4)<<5|16|rm
  cases.append(op)
 for base in [0xe6ff0070,0xe6ef0070,0xe6bf0070,0xe6af0070,0xe6bf0fb0,0xe6bf0f30,0xe6ff0fb0,0xe16f0f10]:
  for _ in range(32):cases.append(base|rng.randrange(13)<<12|rng.randrange(13))
 for opcode in cases:
  a=CPU();vals=[rng.getrandbits(32) for _ in range(15)];a.flags=rng.randrange(16)<<28;a.r[:15]=vals;a.r[15]=0x1000
  uc.reg_write(ar.UC_ARM_REG_CPSR,a.flags|0x10)
  for reg,v in zip(regs[:15],vals):uc.reg_write(reg,v)
  uc.mem_write(0x1000,struct.pack('<I',opcode));uc.ctl_remove_cache(0x1000,0x1004);uc.reg_write(ar.UC_ARM_REG_PC,0x1000)
  try:uc.emu_start(0x1000,0x1004,count=1)
  except Exception as e:raise RuntimeError(hex(opcode)) from e
  c.arm7113_step(ct.byref(a),read,write)
  expected=[uc.reg_read(reg) for reg in regs];flags=uc.reg_read(ar.UC_ARM_REG_CPSR)&0xf0000000
  assert not a.error and list(a.r)==expected and a.flags&0xf0000000==flags,(hex(opcode),a.error,list(a.r),expected,hex(a.flags),hex(flags))
 print('PASS',len(cases),'ARM register, condition, flags, shifts and extension differential cases')
