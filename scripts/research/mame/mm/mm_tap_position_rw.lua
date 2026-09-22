local S = os.getenv("S")
local frame=0
local fields={}
local mem, tap, tap2, cpu
local log=io.open(S.."/mame/tap4_w.txt","w")
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
  if frame==1100 then
    tap=mem:install_write_tap(0x400020,0x40003F,"wtap",function(offset,data,mask)
      log:write(string.format("W %d %06X %06X %04X\n",frame,cpu.state["PC"].value,offset,data))
    end)
    tap2=mem:install_read_tap(0x400020,0x40003F,"rtap",function(offset,data,mask)
      log:write(string.format("R %d %06X %06X %04X\n",frame,cpu.state["PC"].value,offset,data))
    end)
  end
  if frame==1103 then log:close(); tap:remove(); tap2:remove(); manager.machine:exit() end
end)
