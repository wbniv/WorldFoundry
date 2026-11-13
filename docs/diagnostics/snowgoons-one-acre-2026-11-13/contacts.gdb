set pagination off
set confirm off
set print static-members off
set print max-depth 2
set print elements 4
break JoltCharacterGetPosition
commands
silent
print gCharacters[0].posCache._arrScalar
python
import gdb
v=gdb.parse_and_eval('gCharacters[0].character.mPtr->mActiveContacts')
for i in range(int(v['mSize'])):
 c=v['mElements'][i]
 print('CONTACT',c['mBodyB'],'distance',c['mDistance'],'position',c['mPosition'],'normal',c['mContactNormal'])
end
continue
end
run --frame-step-smoke=4 -L/src/wflevels/snowgoons-standalone.iff -rate20
