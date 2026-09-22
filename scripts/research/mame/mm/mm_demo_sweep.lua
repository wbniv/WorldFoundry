local S = os.getenv("S")
local frame=0
local mem
local D=os.getenv("MM_SWEEP_DIR") or (S.."/mame/sweep")
local log=io.open(D.."/log.txt","w")
local function dump(name,lo,hi)
  local f=io.open(D.."/"..name,"wb")
  for a=lo,hi,2 do local v=mem:read_u16(a); f:write(string.char(v>>8, v&0xFF)) end
  f:close()
end
emu.register_frame_done(function()
  frame=frame+1
  if frame==1 then mem=manager.machine.devices[":maincpu"].spaces["program"] end
  if frame>=150 and frame<=1750 and frame%50==0 then
    dump("ram_"..frame..".bin",0x400000,0x401FFF); dump("vram_"..frame..".bin",0xA00000,0xA03FFF)
    if frame==150 then dump("bank.bin",0x080000,0x081FFF) end
    manager.machine.video:snapshot()
    log:write(string.format("%d lvl=%d scroll=%04X X=%08X Y=%08X Z=%08X tbl=%08X\n",frame,mem:read_u16(0x400394),mem:read_u16(0x40097E),mem:read_u32(0x400024),mem:read_u32(0x400028),mem:read_u32(0x40002C),mem:read_u32(0x40065A)))
  end
  if frame==1751 then log:close(); manager.machine:exit() end
end)
