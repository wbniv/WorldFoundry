local S = os.getenv("S")
local frame=0
local fields={}
local mem, tap, cpu
local log=io.open(S.."/mame/tap6_cell.txt","w")
emu.register_frame_done(function()
  frame=frame+1
  if frame==1 then
    for _,port in pairs(manager.machine.ioport.ports) do
      for name,field in pairs(port.fields) do fields[name]=field end
    end
    cpu=manager.machine.devices[":maincpu"]
    mem=cpu.spaces["program"]
  end
  if frame==300 then fields["Coin 1"]:set_value(1) end
  if frame==310 then fields["Coin 1"]:set_value(0) end
  if frame==400 then fields["1 Player Start"]:set_value(1) end
  if frame==410 then fields["1 Player Start"]:set_value(0) end
  if frame==1050 then
    tap=mem:install_read_tap(0x000000,0x07FFFF,"dtap",function(offset,data,mask)
      local pc=cpu.state["PC"].value
      if pc>=0x1CA00 and pc<0x1D000 then
        local d=offset-pc
        if d>40 or d< -8 then
          log:write(string.format("%d %06X %06X %04X X=%08X Y=%08X Z=%08X cx=%d cy=%d\n",frame,pc,offset,data,mem:read_u32(0x400024),mem:read_u32(0x400028),mem:read_u32(0x40002C),mem:read_u16(0x400696),mem:read_u16(0x400698)))
        end
      end
    end)
  end
  if frame==1250 then log:close(); tap:remove(); manager.machine:exit() end
end)
