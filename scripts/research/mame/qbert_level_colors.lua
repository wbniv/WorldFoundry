-- Scan for Q*bert palette and force level advancement.
-- Strategy:
--  1. Start normal gameplay.
--  2. Every frame, read the MAME palette entries (via palette device) and
--     scan candidate RAM addresses for the cube-state data.
--  3. Dump the palette at level start for L1, L2, L3, L4.
--  4. Force round clears by writing all cube state bytes to "target" value
--     once we've identified the cube state base address.

local frame = 0
local fields = {}
local maincpu_mem = nil
local palette_device = nil
local coin_done = false
local start_done = false

-- Will be filled in after we identify the cube state base address
local cube_state_base = nil
local cube_target_val = nil

-- Track which levels we've already dumped
local dumped_levels = {}

local function press(name, on)
  if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

emu.register_frame_done(function()
  frame = frame + 1

  -- Frame 1: cache fields and get memory + palette references
  if frame == 1 then
    for tag, port in pairs(manager.machine.ioport.ports) do
      for name, field in pairs(port.fields) do fields[name] = field end
    end

    -- Get maincpu memory space
    local cpu = manager.machine.devices[":maincpu"]
    if cpu then
      maincpu_mem = cpu.spaces["program"]
      print("Got maincpu memory space")
    else
      print("ERROR: no :maincpu device")
    end

    -- Try to find palette device
    for tag, dev in pairs(manager.machine.devices) do
      if tag:find("palette") or tag:find("pal") then
        palette_device = dev
        print("Found palette device: " .. tag)
      end
    end
  end

  -- Coin at frame 150, Start at frame 300
  press("Coin 1",         frame >= 150 and frame < 180)
  press("1 Player Start", frame >= 300 and frame < 330)

  -- Dump palette and scan candidate cube state RAM every 300 frames from frame 500
  if frame >= 500 and (frame % 300) == 0 and maincpu_mem then
    -- Try to read Gottlieb palette RAM at candidate addresses
    -- Gottlieb hardware palette is 16 entries × 2 bytes = 32 bytes
    -- Based on MAME source, likely at 0x3000-0x301F or similar
    for _, base in ipairs({0x2800, 0x3000, 0x3800, 0x4000, 0x5000, 0x5800}) do
      local ok, err = pcall(function()
        -- Read 32 bytes starting at base
        local bytes = {}
        for i = 0, 31 do
          bytes[i] = maincpu_mem:read_u8(base + i)
        end
        -- Print if any non-zero values
        local any_nonzero = false
        for i = 0, 31 do if bytes[i] ~= 0 then any_nonzero = true; break end end
        if any_nonzero then
          io.write(string.format("PAL@0x%04X: ", base))
          for i = 0, 31 do io.write(string.format("%02X ", bytes[i])) end
          io.write("\n")
          io.flush()
        end
      end)
      if not ok then
        print(string.format("  0x%04X: read error: %s", base, tostring(err)))
      end
    end

    -- Scan for cube state data: look for 28 bytes in a range 0x0000-0x2000
    -- where values are 0-2 (matching cube state range)
    -- Print first 64 bytes of RAM
    io.write(string.format("RAM[0x00-0x3F]@f%d: ", frame))
    for i = 0, 63 do
      io.write(string.format("%02X ", maincpu_mem:read_u8(i)))
    end
    io.write("\n")

    -- Print a candidate range for video color RAM
    io.write(string.format("RAM[0x2000-0x203F]@f%d: ", frame))
    for i = 0, 63 do
      io.write(string.format("%02X ", maincpu_mem:read_u8(0x2000+i)))
    end
    io.write("\n")
    io.flush()
  end

  -- Hop sequence: simple repeating LR (down-right) to flip some cubes
  -- so we can track which RAM addresses change
  if frame >= 400 then
    local CYCLE = 40
    local t = (frame - 400) % CYCLE
    press("P1 Right (Down-Right)", t < 6)
    -- Every 8th cycle, press UL (up-left) to go back toward apex
    local big_cycle = (frame - 400) % (CYCLE * 7)
    if big_cycle >= CYCLE * 6 then
      press("P1 Left (Up-Left)", t < 6)
    end
  end

  -- Take snapshot every 600 frames
  if frame >= 500 and (frame % 600) == 0 then
    manager.machine.video:snapshot()
    print("snap at frame " .. frame)
  end

  if frame >= 6000 then
    print("Done at frame " .. frame)
    manager.machine:exit()
  end
end)
