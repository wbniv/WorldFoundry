-- Capture the arcade collision map; no WF geometry or old converter involved.
local root=assert(os.getenv('MM3D_CAPTURE_DIR'))
local frame=0
local mem=manager.machine.devices[':maincpu'].spaces['program']
local queries={}
local function input(name,value)
 for _,port in pairs(manager.machine.ioport.ports) do
  for key,field in pairs(port.fields) do if key==name then field:set_value(value) end end
 end
end
local function dump(name,start,length)
 local f=assert(io.open(root..'/'..name..'.bin','wb'))
 for a=start,start+length-1 do f:write(string.char(mem:read_u8(a))) end
 f:close()
end
emu.register_frame_done(function()
 frame=frame+1
 if frame==180 then input('Coin 1',1) end
 if frame==185 then input('Coin 1',0) end
 if frame==210 then input('1 Player Start',1) end
 if frame==215 then input('1 Player Start',0) end
 if frame>=350 and mem:read_u32(0x400474)==0x2bee2 then
  local h={}
  for i=0,15 do h[#h+1]=tostring(mem:read_u16(0x401c28+2*i)) end
  queries[#queries+1]=string.format('{"x":%d,"y":%d,"h":[%s]}',mem:read_u16(0x400696),mem:read_u16(0x400698),table.concat(h,','))
 end
 if frame==600 then
  dump('ram',0x400000,0x2000)
  dump('pf',0xa00000,0x4000)
  local f=assert(io.open(root..'/queries.json','w'))
  f:write('['..table.concat(queries,',')..']');f:close()
  manager.machine:exit()
 end
end)
