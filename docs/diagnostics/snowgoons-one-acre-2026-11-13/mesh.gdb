set pagination off
set confirm off
set print static-members off
break JoltBodyCreateStaticMesh
commands
silent
python
import gdb
n=int(gdb.parse_and_eval('vertCount'))
v=gdb.parse_and_eval('verts')
print('MESH',n,'bounds',[(min(float(v[i][ax]) for i in range(n)),max(float(v[i][ax]) for i in range(n))) for ax in ['x','y','z']])
end
continue
end
run -pps --frame-step-smoke=2 -L/src/wflevels/snowgoons-standalone.iff -rate20
