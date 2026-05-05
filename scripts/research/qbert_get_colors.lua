-- Get Q*bert level 2+ palette colors by:
-- 1. Starting gameplay with proper timing (coin at frame 500 = 8s after boot)
-- 2. Writing 99 to candidate lives addresses every frame (keeps Q*bert alive)
-- 3. Reading the live palette device entries when gameplay starts
-- 4. Reading them again after each level transition

local frame = 0
local fields = {}
local mem = nil
local pal_dev = nil
local last_level = -1
local game_started = false

-- Candidate lives counter addresses in 6809 RAM (0x0000-0x01FF)
-- Will write 99 (0x63) to all of these every frame; one of them is the real lives counter
local LIVES_CANDIDATES = {}
for i = 0, 0x1F do LIVES_CANDIDATES[i+1] = i end  -- try first 32 bytes

local function press(name, on)
  if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

local function read_palette()
  -- Read palette device entries directly
  if not pal_dev then return end
  io.write("PALETTE: ")
  -- Try MAME Lua palette API variants
  local ok = pcall(function()
    local p = pal_dev.palette
    if p then
      for i = 0, math.min(15, p.entries-1) do
        local c = p:color(i)
        -- c might be a packed int or have r,g,b fields
        io.write(string.format("[%d]=%08X ", i, c))
      end
    end
  end)
  if not ok then
    -- Try alternate: read from program address space at palette RAM candidates
    for _, base in ipairs({0x5000, 0x5800, 0x3000, 0x4000}) do
      local vals = {}
      for i = 0, 31 do
        local ok2, v = pcall(function() return mem:read_u8(base+i) end)
        vals[i+1] = ok2 and v or 0xFF
      end
      -- Check if any non-0x24, non-0xFF values (these would be real data)
      local interesting = false
      for _, v in ipairs(vals) do
        if v ~= 0x24 and v ~= 0xFF and v ~= 0x00 then interesting = true; break end
      end
      if interesting then
        io.write(string.format("@%04X:", base))
        for i, v in ipairs(vals) do io.write(string.format("%02X", v)) end
        io.write(" ")
      end
    end
  end
  io.write("\n")
  io.flush()
end

emu.register_frame_done(function()
  frame = frame + 1

  if frame == 1 then
    for tag, port in pairs(manager.machine.ioport.ports) do
      for name, field in pairs(port.fields) do fields[name] = field end
    end
    local cpu = manager.machine.devices[":maincpu"]
    if cpu then mem = cpu.spaces["program"] end
    -- Find palette device
    for tag, dev in pairs(manager.machine.devices) do
      if tag == ":palette" then pal_dev = dev end
    end
    print("Init done. mem=" .. tostring(mem ~= nil) .. " pal=" .. tostring(pal_dev ~= nil))
  end

  -- Coin at frame 500, Start at frame 700 (well after Q*bert boot)
  press("Coin 1",         frame >= 500 and frame < 530)
  press("1 Player Start", frame >= 700 and frame < 730)

  if frame == 700 then
    print("Game starting at frame " .. frame)
    game_started = true
  end

  -- Keep lives high by writing 99 to candidate addresses (brute-force)
  if game_started and mem and (frame % 10) == 0 then
    for _, addr in ipairs(LIVES_CANDIDATES) do
      pcall(function() mem:write_u8(addr, 99) end)
    end
  end

  -- Read palette and low RAM every 300 frames after game start
  if game_started and frame > 800 and (frame % 300) == 0 then
    -- Print low RAM
    io.write(string.format("RAM[00-1F]@f%d: ", frame))
    for i = 0, 31 do
      local ok, v = pcall(function() return mem:read_u8(i) end)
      io.write(string.format("%02X ", ok and v or 0xEE))
    end
    io.write("\n")

    -- Try reading color/video RAM
    for _, base in ipairs({0x2000, 0x2800, 0x3000, 0x3800, 0x4800, 0x5000, 0x5800}) do
      local interesting = false
      local vals = {}
      for i = 0, 31 do
        local ok, v = pcall(function() return mem:read_u8(base+i) end)
        vals[i+1] = ok and v or 0
        if ok and v ~= 0 and v ~= 0x24 and v ~= 0xFF then interesting = true end
      end
      if interesting then
        io.write(string.format("  %04X: ", base))
        for _, v in ipairs(vals) do io.write(string.format("%02X ", v)) end
        io.write("\n")
      end
    end
    read_palette()
    io.flush()
  end

  -- Hop sequence: simple LR to flip cubes
  if game_started and frame > 800 then
    local CYCLE = 40
    local t = (frame - 800) % CYCLE
    press("P1 Right (Down-Right)", t < 6)
  end

  -- Screenshot every 1200 frames
  if game_started and (frame % 1200) == 0 then
    manager.machine.video:snapshot()
    print("snap at frame " .. frame)
  end

  if frame >= 10000 then
    print("Done at frame " .. frame)
    manager.machine:exit()
  end
end)
