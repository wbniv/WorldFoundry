local S = os.getenv("S")
local frame=0
local fields={}
local mem, tap, cpu
local log=io.open(S.."/mame/tap5_data.txt","w")
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
    tap=mem:install_read_tap(0x000000,0x07FFFF,"dtap",function(offset,data,mask)
      local pc=cpu.state["PC"].value
      local d=offset-pc
      if d>40 or d< -8 then
        log:write(string.format("%d %06X %06X %04X\n",frame,pc,offset,data))
      end
    end)
  end
  if frame==1104 then log:close(); tap:remove(); manager.machine:exit() end
end)
