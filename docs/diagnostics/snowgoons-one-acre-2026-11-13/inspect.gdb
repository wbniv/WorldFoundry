set pagination off
set confirm off
set print static-members off
set print max-depth 4
break WFGame::StepFrame
ignore 1 20
run -pps --frame-step-smoke=22 -L/src/wflevels/snowgoons-standalone.iff -rate20
python
import gdb,json
v=gdb.parse_and_eval('this->_curLevel->_theAssetManager')
for i in range(3):
 try:
  slot=v['_assets'][i]
  if int(slot)==0:continue
  mem=slot.dereference()['_assetsMemory']
  used=int(mem['_currentFree']-mem['_memory'])
  total=int(mem['_endMemory']-mem['_memory'])
  print('ROOM_POOL',i,used,total)
 except Exception as ex: print('POOL_ERROR',str(ex))

end
quit
