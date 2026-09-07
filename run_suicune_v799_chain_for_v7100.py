#!/usr/bin/env python3
from pathlib import Path
import subprocess, tempfile

p=Path('.github/workflows/build_suicune_v799.yml')
lines=p.read_text().splitlines()
started=False
i=0
while i < len(lines):
    line=lines[i]
    if line.startswith('      - name: '):
        name=line[len('      - name: '):]
        if name == 'Generate v7.4.4 baseline':
            started=True
        if name == 'Build v7.9.9':
            break
        j=i+1
        while j < len(lines) and not lines[j].startswith('      - name: ') and not lines[j].startswith('      - uses: '):
            if started and lines[j] == '        run: |':
                k=j+1; body=[]
                while k < len(lines) and (lines[k].startswith('          ') or lines[k]==''):
                    body.append(lines[k][10:] if lines[k].startswith('          ') else '')
                    k+=1
                script='\n'.join(body)+'\n'
                print(f'=== v799 chain: {name} ===',flush=True)
                with tempfile.NamedTemporaryFile('w',delete=False,suffix='.sh') as f:
                    f.write(script); fn=f.name
                subprocess.run(['sh',fn],check=True)
                i=k-1
                break
            if started and lines[j].startswith('        run: ') and lines[j] != '        run: |':
                cmd=lines[j][13:]
                print(f'=== v799 chain: {name} ===',flush=True)
                subprocess.run(['sh','-c',cmd],check=True)
                i=j
                break
            j+=1
    i+=1
print('v799 generated source + invariants complete; stopping before v799 make')
