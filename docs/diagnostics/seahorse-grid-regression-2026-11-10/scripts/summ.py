import json,glob,statistics,sys
rows={}
for d in sys.argv[1:]:
    for f in sorted(glob.glob(f'{d}/*/run-1/summary.json')):
        lab=f.split('/')[-3]; s=json.load(open(f)); rows.setdefault(lab.rstrip('0123456789'),[]).append((lab,round(1000/s['fps'],2)))
for k,v in sorted(rows.items()): print(k,v,'median',round(statistics.median(x[1] for x in v),2))
