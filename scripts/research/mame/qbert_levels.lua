local frame = 0
local fields = {}

-- 30-hop covering walk verified by Python DFS/Warnsdorff (visits all 28 cells from apex)
local HOP_SEQ = {
  "P1 Right (Down-Right)", "P1 Right (Down-Right)", "P1 Right (Down-Right)",
  "P1 Right (Down-Right)", "P1 Right (Down-Right)", "P1 Right (Down-Right)",
  "P1 Left (Up-Left)",     "P1 Down (Down-Left)",   "P1 Left (Up-Left)",
  "P1 Down (Down-Left)",   "P1 Left (Up-Left)",     "P1 Up (Up-Right)",
  "P1 Left (Up-Left)",     "P1 Left (Up-Left)",     "P1 Left (Up-Left)",
  "P1 Down (Down-Left)",   "P1 Down (Down-Left)",   "P1 Down (Down-Left)",
  "P1 Down (Down-Left)",   "P1 Down (Down-Left)",   "P1 Up (Up-Right)",
  "P1 Right (Down-Right)", "P1 Up (Up-Right)",      "P1 Right (Down-Right)",
  "P1 Up (Up-Right)",      "P1 Right (Down-Right)", "P1 Up (Up-Right)",
  "P1 Left (Up-Left)",     "P1 Left (Up-Left)",     "P1 Down (Down-Left)"
}
local ALL_DIRS = {
  "P1 Down (Down-Left)", "P1 Right (Down-Right)",
  "P1 Up (Up-Right)",    "P1 Left (Up-Left)"
}
-- 30 frames/hop gives more time for hop animation + enemy clearing
local FRAMES_PER_HOP = 30
local HOP_PULSE = 6
-- Cycle: 30 hops × 30 frames = 900 + 200-frame pause for round-clear animation
local CYCLE = #HOP_SEQ * FRAMES_PER_HOP + 200

emu.register_frame_done(function()
  frame = frame + 1

  -- Frame 1: cache all input fields + enable Demo Mode DIP (unlimited lives)
  if frame == 1 then
    for tag, port in pairs(manager.machine.ioport.ports) do
      for name, field in pairs(port.fields) do
        fields[name] = field
      end
    end
    -- "On" state for this DIP = value 1 in MAME Lua (selects non-default/active state)
    local demo = fields["Demo Mode (Unlim Lives, Start=Adv (Cheat)"]
    if demo then
      demo:set_value(1)
      print("Demo Mode (unlimited lives) enabled")
    else
      print("WARNING: Demo Mode field not found — Q*bert will die normally")
    end
  end

  local function press(name, on)
    if fields[name] then fields[name]:set_value(on and 1 or 0) end
  end
  local function all_off()
    for _, d in ipairs(ALL_DIRS) do press(d, false) end
  end

  -- Coin + Start to begin game
  press("Coin 1",         frame >= 120 and frame < 150)
  press("1 Player Start", frame >= 240 and frame < 270)

  -- Hop sequence starts at frame 360, loops forever
  if frame >= 360 then
    local t = (frame - 360) % CYCLE
    all_off()
    if t < #HOP_SEQ * FRAMES_PER_HOP then
      local hop_idx = math.floor(t / FRAMES_PER_HOP) + 1
      local dir = HOP_SEQ[hop_idx]
      if (t % FRAMES_PER_HOP) < HOP_PULSE then
        press(dir, true)
      end
    end
    -- During the 200-frame pause, all keys are off (already done by all_off above)
  end

  -- Snapshot every 400 frames from frame 1500 onward, up to 30000 frames
  -- This gives ~70 snapshots; scan the resulting PNGs for level transitions
  if frame >= 1500 and frame <= 30000 and ((frame - 1500) % 400) == 0 then
    manager.machine.video:snapshot()
    print(string.format("snap at frame %d (cycle t=%d)", frame,
      frame >= 360 and (frame - 360) % CYCLE or -1))
  end

  if frame >= 30000 then
    print("Done — exiting after " .. frame .. " frames")
    manager.machine:exit()
  end
end)
