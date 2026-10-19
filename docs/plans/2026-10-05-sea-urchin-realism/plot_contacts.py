#!/usr/bin/env python3
"""Plot saved contact correctness traces; no desktop performance measurements."""
from pathlib import Path
import json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/wf-urchin-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
matplotlib.rcParams['svg.fonttype']='none'
matplotlib.rcParams['svg.hashsalt']='urchin-contacts'
HERE=Path(__file__).resolve().parent
trace=json.loads((HERE/'evidence/phase-2/native/trace.json').read_text())
x=[r['frame'] for r in trace]
fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True,gridspec_kw={'height_ratios':[2,1,1]})
fig.patch.set_facecolor('#faf7ee')
axes[0].plot(x,[r['poses']['Player'][0]+.25 for r in trace],color='#654784',label='Body attachment X')
axes[0].plot(x,[r['contacts']['0'][0] for r in trace],color='#167e83',label='Foot 0 pad X')
axes[0].set_ylabel('World X');axes[0].legend(loc='upper left',ncols=2)
axes[0].set_title('Actual contact trace · correctness only, no desktop performance data')
for k,color in [(0,'#167e83'),(4,'#bc7343')]:
    axes[1].step(x,[r['contacts'][str(k)][2] for r in trace],where='post',label=f'Foot {k}',color=color,alpha=.85)
axes[1].set_yticks([0,1,2,3],['Support','Release','Recover','Reach'])
axes[1].legend(ncols=2,loc='upper left')
axes[2].plot(x,[r['contacts']['0'][3] for r in trace],color='#167e83')
axes[2].set_ylabel('Pad lift');axes[2].set_xlabel('Stepped simulation frame (not wall-clock time or rendering FPS)')
for ax in axes:
    ax.set_facecolor('#faf7ee');ax.grid(alpha=.2)
    for start in [40,140,240,340]:ax.axvline(start,color='#839c99',linewidth=.8,linestyle=':')
for start,end,label in [(0,40,'Idle'),(40,140,'Right'),(140,240,'Diagonal'),(240,340,'Reverse'),(340,400,'Release')]:
    axes[0].text((start+end)/2,1.03,label,transform=axes[0].get_xaxis_transform(),ha='center',fontsize=9)
fig.tight_layout();fig.savefig(HERE/'contact-trace.svg',metadata={'Date':None});plt.close(fig)
p=HERE/'contact-trace.svg';p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
