"""Reconstruct CVS trunk snapshots from archived RCS reverse deltas."""
from pathlib import Path
import re

def history(path):
 s=Path(path).read_text();header,body=s.split('\ndesc\n',1)
 meta={r:{'date':d,'author':a,'state':state,'next':n} for r,d,a,state,n in re.findall(r'(?m)^(\d+(?:\.\d+)+)\ndate\s+([^;]+);\s+author\s+([^;]+);\s+state\s+([^;]+);\s+branches[^;]*;\s+next\s*([^;]*);',header)}
 tokens=re.findall(r'@(?:[^@]|@@)*@|[^\s;:]+|[;:]',body)
 def string(t):
  assert t.startswith('@') and t.endswith('@');return t[1:-1].replace('@@','@')
 string(tokens.pop(0));deltas={}
 while tokens:
  rev,log,logtext,text,textbody=tokens[:5];del tokens[:5];assert log=='log' and text=='text';deltas[rev]=(string(logtext),string(textbody))
 def patch(current,delta):
  lines=current.splitlines(keepends=True);commands=iter(delta.splitlines(keepends=True));offset=0
  for cmd in commands:
   m=re.fullmatch(r'([ad])(\d+) (\d+)\n?',cmd);assert m,repr(cmd)
   op,line,count=m.group(1),int(m.group(2)),int(m.group(3))
   if op=='d':
    pos=line-1+offset;assert 0<=pos and pos+count<=len(lines);del lines[pos:pos+count];offset-=count
   else:
    pos=line+offset;assert 0<=pos<=len(lines);lines[pos:pos]=[next(commands) for _ in range(count)];offset+=count
  return ''.join(lines)
 rev=re.search(r'head\s+([^;]+)',header).group(1);current=deltas[rev][1];result={}
 while rev:
  result[rev]={**meta[rev],'log':deltas[rev][0].strip(),'text':current}
  nxt=meta[rev]['next']
  if nxt:current=patch(current,deltas[nxt][1])
  rev=nxt
 if '1.1.1.1' in deltas:
  result['1.1.1.1']={**meta['1.1.1.1'],'log':deltas['1.1.1.1'][0].strip(),'text':patch(result['1.1']['text'],deltas['1.1.1.1'][1])}
 return result

if __name__=='__main__':
 import sys
 rows=history(sys.argv[1]);sys.stdout.write(rows[sys.argv[2]]['text'])
