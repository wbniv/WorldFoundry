-- Q*bert palette capture via real gameplay.
-- Coin+Start, then Warnsdorff 30-hop walk to complete each round.
-- Write-tap on 0x5000-0x501F captures palette writes at each real round transition.
-- Lives kept at 3 via direct RAM write so deaths don't derail the sequence.

local LOG_PATH = "/home/will/WorldFoundry.2026-new-level/scripts/research/mame/palette_gameplay_output.txt"
local logfile = io.open(LOG_PATH, "w")
local function log(s)
    io.write(s); io.flush()
    if logfile then logfile:write(s); logfile:flush() end
end

local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}
local function decode_color(b0, b1)
    local r = DAC[(b1 & 0xF) + 1]
    local g = DAC[((b0 >> 4) & 0xF) + 1]
    local bv = DAC[(b0 & 0xF) + 1]
    return r, g, bv
end

-- 30-hop Warnsdorff covering walk (visits all 28 cells from apex, verified)
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
local ALL_DIRS = {"P1 Down (Down-Left)","P1 Right (Down-Right)","P1 Up (Up-Right)","P1 Left (Up-Left)"}
local FRAMES_PER_HOP = 30
local HOP_PULSE = 6
-- Round-clear animation takes ~200 frames; give 400 to be safe before next round starts
local INTER_ROUND_PAUSE = 400
local CYCLE = #HOP_SEQ * FRAMES_PER_HOP + INTER_ROUND_PAUSE
local HOP_START = 500   -- frames after game start before first hop

local frame = 0
local fields = {}
local mem = nil
local tap_installed = false

-- Palette accumulator
local pending_writes = {}
local write_log = {}    -- {frame, rel_off, val}

local round_count = 0
local game_started = false
local game_start_frame = 0

local function dump_palette(label)
    -- Diagnostics: when were writes received?
    if #write_log > 0 then
        log(string.format("[diag] %d writes; first=f%d last=f%d\n",
            #write_log, write_log[1].f, write_log[#write_log].f))
    end
    log(string.format("\n=== PALETTE %s (frame=%d) ===\n", label, frame))
    -- Pixel samples at known cube face coords
    for tag, scr in pairs(manager.machine.screens) do
        local pts = {{118,57,"apex_top"},{91,89,"lit_side"},{111,89,"shadow_side"}}
        for _, p in ipairs(pts) do
            local ok, px = pcall(function() return scr:pixel(p[1],p[2]) end)
            if ok and px then
                local r=(px>>16)&0xFF; local g=(px>>8)&0xFF; local b=px&0xFF
                log(string.format("  pixel %-12s (%3d,%3d): #%02X%02X%02X\n",p[3],p[1],p[2],r,g,b))
            end
        end
    end
    -- Decode pen data
    local any = false
    for i = 0, 15 do
        local b0 = pending_writes[i*2]
        local b1 = pending_writes[i*2+1]
        if b0 and b1 then
            any = true
            local r,g,bv = decode_color(b0,b1)
            log(string.format("  pen%02d: #%02X%02X%02X  (raw: %02X %02X)\n",i,r,g,bv,b0,b1))
        end
    end
    if not any then log("  (no palette writes captured)\n") end
    pending_writes = {}
    write_log = {}
    -- Screenshot: snapshot() saves to ~/.mame/snap/qbert/<next>.png; rename immediately.
    local ok_snap = pcall(function() manager.machine.video:snapshot() end)
    if ok_snap then
        -- Find the highest-numbered auto-snap and move it to gameplay_rN.png
        local dest = string.format("/home/will/.mame/snap/qbert/gameplay_r%d.png", round_count)
        local newest, newest_n = nil, -1
        local f = io.popen("ls /home/will/.mame/snap/qbert/*.png 2>/dev/null | grep -E '/[0-9]+\\.png$' | sort -t/ -k7 -V | tail -1")
        if f then
            local p = f:read("*l"); f:close()
            if p and p ~= "" then newest = p end
        end
        if newest then
            os.rename(newest, dest)
            log(string.format("[snap] saved %s\n", dest))
        else
            log("[snap] could not locate auto-snap\n")
        end
    else
        log("[snap] snapshot() failed\n")
    end
end

local function set_input(name, val)
    if fields[name] then fields[name]:set_value(val) end
end
local function all_dirs_off()
    for _, d in ipairs(ALL_DIRS) do set_input(d, 0) end
end

emu.register_frame_done(function()
    frame = frame + 1

    -- Frame 1: init fields, memory, tap
    if frame == 1 then
        for tag, port in pairs(manager.machine.ioport.ports) do
            for name, field in pairs(port.fields) do fields[name] = field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        if cpu then mem = cpu.spaces["program"] end
        if mem then
            local ok = pcall(function()
                mem:install_write_tap(0x5000, 0x501F, "pal_tap", function(off, data, mask)
                    local rel = off - 0x5000
                    pending_writes[rel] = data & 0xFF
                    write_log[#write_log+1] = {f=frame, off=rel, val=data&0xFF}
                end)
                tap_installed = true
            end)
            log(string.format("[INFO] tap=%s mem=%s\n", tostring(ok), tostring(mem~=nil)))
        end
    end

    -- Coin insert + Start to begin a real game
    set_input("Coin 1",         frame >= 60  and frame < 90)
    set_input("1 Player Start", frame >= 180 and frame < 210)

    if frame == 210 then
        game_started = true
        game_start_frame = frame
        log("[INFO] Game started at frame " .. frame .. "\n")
        -- Flush the startup palette writes; first real round dump will catch R1
        pending_writes = {}
        write_log = {}
    end

    -- Keep lives at 3 so deaths don't interrupt the sequence
    if game_started and mem then
        pcall(function() mem:write_u8(0x0D00, 3) end)
    end

    -- Hop sequence: starts HOP_START frames after game start, loops per round
    if game_started then
        local elapsed = frame - (game_start_frame + HOP_START)
        if elapsed >= 0 then
            local cycle_t = elapsed % CYCLE
            all_dirs_off()
            if cycle_t < #HOP_SEQ * FRAMES_PER_HOP then
                local hop_i = math.floor(cycle_t / FRAMES_PER_HOP) + 1
                local hop_t = cycle_t % FRAMES_PER_HOP
                if hop_i >= 1 and hop_i <= #HOP_SEQ and hop_t < HOP_PULSE then
                    set_input(HOP_SEQ[hop_i], 1)
                end
            end
            -- Dump palette near end of inter-round pause (round just completed)
            if cycle_t == #HOP_SEQ * FRAMES_PER_HOP + INTER_ROUND_PAUSE - 30 then
                round_count = round_count + 1
                dump_palette("R" .. round_count)
            end
        end
    end

    -- Stop after 16 rounds
    if round_count >= 16 then
        log("\n=== CAPTURE COMPLETE ===\n")
        if logfile then logfile:close() end
        manager.machine:exit()
    end

    -- Safety exit
    if frame > 200000 then
        log("[WARN] Safety exit at frame " .. frame .. "\n")
        if logfile then logfile:close() end
        manager.machine:exit()
    end
end)
