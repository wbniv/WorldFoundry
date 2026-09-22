local S = os.getenv("S")
local frame=0
local mem
local log=io.open(S.."/mame/attract_log.txt","w")
emu.register_frame_done(function()
  frame=frame+1
  if frame==1 then mem=manager.machine.devices[":maincpu"].spaces["program"] end
  if frame%120==0 then
    manager.machine.video:snapshot()
    log:write(string.format("%d lvl=%04X scroll=%04X X=%08X Y=%08X Z=%08X lvlptr=%08X tbl=%08X\n",frame,mem:read_u16(0x400394),mem:read_u16(0x40097E),mem:read_u32(0x400024),mem:read_u32(0x400028),mem:read_u32(0x40002C),mem:read_u32(0x400474),mem:read_u32(0x40065A)))
  end
  if frame==4800 then log:close(); manager.machine:exit() end
end)
