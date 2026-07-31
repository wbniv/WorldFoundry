local f1 = io.open("/home/will/WorldFoundry.2026-new-level/scripts/research/mame/test_output.txt", "w")
local f2 = io.open("/home/will/WorldFoundry.2026-new-level/docs/investigations/test_output.txt", "w")
if f1 then f1:write("scripts dir ok\n"); f1:close() end
if f2 then f2:write("docs dir ok\n"); f2:close() end
local frame = 0
emu.register_frame_done(function()
    frame = frame + 1
    if frame >= 10 then manager.machine:exit() end
end)
