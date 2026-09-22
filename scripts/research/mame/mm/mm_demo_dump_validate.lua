local S = os.getenv("S")
local frame=0
local mem, cpu, tap
local traj=io.open(S.."/mame/demo_traj.txt","w")
local tlog=io.open(S.."/mame/demo_tbl_reads.txt","w")
local function dump(name,lo,hi)
  local f=io.open(S.."/mame/"..name,"wb")
  for a=lo,hi,2 do local v=mem:read_u16(a); f:write(string.char(v>>8, v&0xFF)) end
  f:close()
end
emu.register_frame_done(function()
  frame=frame+1
  if frame==1 then cpu=manager.machine.devices[":maincpu"]; mem=cpu.spaces["program"]
    tap=mem:install_read_tap(0x080000,0x081FFF,"banktap",function(offset,data,mask)
      local pc=cpu.state["PC"].value
      if pc>=0x1CA00 and pc<0x1D000 then tlog:write(string.format("%d %06X %06X %04X\n",frame,pc,offset,data)) end
    end)
  end
  if frame>=200 and frame<=1700 then
    traj:write(string.format("%d %08X %08X %08X %d %d %d %d %d\n",frame,mem:read_u32(0x400024),mem:read_u32(0x400028),mem:read_u32(0x40002C),mem:read_u16(0x400696),mem:read_u16(0x400698),mem:read_u16(0x40069E),mem:read_u16(0x4006A0),mem:read_u16(0x4006A2)))
  end
  if frame==600 or frame==1000 or frame==1400 then
    dump("demo_ram_"..frame..".bin",0x400000,0x401FFF); dump("demo_vram_"..frame..".bin",0xA00000,0xA03FFF); dump("demo_bank_"..frame..".bin",0x080000,0x081FFF)
    manager.machine.video:snapshot()
    local s=string.format("frame %d lvl=%04X scroll=%04X lvlptr=%08X tbl=%08X cx=%d cy=%d heights:",frame,mem:read_u16(0x400394),mem:read_u16(0x40097E),mem:read_u32(0x400474),mem:read_u32(0x40065A),mem:read_u16(0x400696),mem:read_u16(0x400698))
    for i=0,15 do s=s..string.format(" %04X",mem:read_u16(0x401C28+2*i)) end
    print(s)
  end
  if frame==1701 then traj:close(); tlog:close(); tap:remove(); manager.machine:exit() end
end)
