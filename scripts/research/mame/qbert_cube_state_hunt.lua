-- Find cube state array via multiple hops, then fill to trigger level transitions.
local LOG_PATH = "/home/will/WorldFoundry.2026-new-level/scripts/research/mame/cube_state_hunt.txt"
local logfile = io.open(LOG_PATH, "w")
local function log(s) io.write(s); io.flush(); if logfile then logfile:write(s); logfile:flush() end end

local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}
local function decode(b0,b1)
    return DAC[(b1&0xF)+1], DAC[((b0>>4)&0xF)+1], DAC[(b0&0xF)+1]
end

local frame = 0
local fields = {}
local mem = nil
local pal = {}; for i=0,31 do pal[i]=0 end
local pal_written = 0
local last_pal_key = nil
local level_captured = 0

local snap0 = nil  -- before any hops (clean game state)
local snapH = nil  -- after several hops

local function pal_key()
    local t = {}; for i=0,31 do t[i+1]=string.format("%02X",pal[i]) end
    return table.concat(t)
end

local function dump_palette(label)
    level_captured = level_captured + 1
    log(string.format("\n=== PALETTE %s (frame=%d) ===\n", label, frame))
    for i=0,15 do
        local b0,b1=pal[i*2] or 0,pal[i*2+1] or 0
        local r,g,bv=decode(b0,b1)
        log(string.format("  pen%02d: #%02X%02X%02X  (raw: %02X %02X)\n",i,r,g,bv,b0,b1))
    end
end

local function set_input(name, val)
    if fields[name] then fields[name]:set_value(val) end
end

local function read_ram(start, len)
    local t = {}
    for i=0,len-1 do
        local ok,v = pcall(function() return mem:read_u8(start+i) end)
        t[i] = ok and v or 0
    end
    return t
end

-- Hop sequence to visit many cubes (simple zigzag)
local HOPS = {
    "P1 Right (Down-Right)","P1 Right (Down-Right)","P1 Right (Down-Right)",
    "P1 Left (Up-Left)","P1 Left (Up-Left)","P1 Left (Up-Left)",
    "P1 Down (Down-Left)","P1 Down (Down-Left)","P1 Down (Down-Left)",
    "P1 Up (Up-Right)","P1 Up (Up-Right)","P1 Up (Up-Right)",
    "P1 Right (Down-Right)","P1 Right (Down-Right)",
    "P1 Left (Up-Left)","P1 Left (Up-Left)",
}
local FRAMES_PER_HOP = 45
local HOP_PULSE = 8

local STATE = "INIT"
local state_frame = 0
local cube_base = nil
local cube_val = nil

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for tag,port in pairs(manager.machine.ioport.ports) do
            for name,field in pairs(port.fields) do fields[name]=field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if mem then
            pcall(function()
                mem:install_write_tap(0x5000, 0x501F, "pal", function(off,data,mask)
                    pal[off-0x5000] = data & 0xFF
                    pal_written = pal_written + 1
                end)
            end)
            log("[INFO] tap installed\n")
        end
        STATE = "BOOT"
        state_frame = frame
    end

    if mem then pcall(function() mem:write_u8(0x0D00, 3) end) end

    -- Boot: coin + start
    if STATE == "BOOT" then
        set_input("Coin 1", frame>=60 and frame<90 and 1 or 0)
        set_input("1 Player Start", frame>=180 and frame<210 and 1 or 0)
        if frame == 400 then STATE="SNAP0"; state_frame=frame end
    end

    -- Snapshot RAM before any hops
    if STATE == "SNAP0" and frame - state_frame >= 5 then
        snap0 = read_ram(0, 0x800)  -- 0x0000-0x07FF
        log(string.format("[frame %d] snap0 taken (pre-hop)\n", frame))
        STATE = "HOPPING"; state_frame = frame
    end

    -- Execute hop sequence
    if STATE == "HOPPING" then
        local elapsed = frame - state_frame
        local hop_i = math.floor(elapsed / FRAMES_PER_HOP)
        local hop_t = elapsed % FRAMES_PER_HOP
        local ALL_DIRS = {"P1 Down (Down-Left)","P1 Right (Down-Right)","P1 Up (Up-Right)","P1 Left (Up-Left)"}
        for _,d in ipairs(ALL_DIRS) do set_input(d, 0) end
        if hop_i < #HOPS and hop_t < HOP_PULSE then
            set_input(HOPS[hop_i+1], 1)
        end
        if hop_i >= #HOPS then
            -- Done hopping — snapshot and diff
            snapH = read_ram(0, 0x800)
            log(string.format("[frame %d] snapH taken (post-%d hops)\n", frame, #HOPS))
            -- Find addresses that changed from 0 to a small value (1-8)
            log("Bytes that went 0->1..8 (cube state candidates):\n")
            local cands = {}
            for i=0,0x7FF do
                local a,b = snap0[i] or 0, snapH[i] or 0
                if a==0 and b>=1 and b<=8 then
                    log(string.format("  0x%04X: 0->%d\n", i, b))
                    cands[#cands+1] = {addr=i, val=b}
                end
            end
            log(string.format("Total candidates: %d\n", #cands))
            -- Look for a run of consecutive 0->nonzero addresses (cube array)
            if #cands >= 3 then
                -- Find longest consecutive run
                local best_start, best_len = cands[1].addr, 1
                local cur_start, cur_len = cands[1].addr, 1
                for i=2,#cands do
                    if cands[i].addr == cands[i-1].addr + 1 then
                        cur_len = cur_len + 1
                        if cur_len > best_len then
                            best_start = cur_start; best_len = cur_len
                        end
                    else
                        cur_start = cands[i].addr; cur_len = 1
                    end
                end
                if best_len >= 3 then
                    cube_base = best_start
                    cube_val = snapH[best_start]
                    log(string.format("\n[CUBE ARRAY CANDIDATE: 0x%04X, len=%d, val=%d]\n",
                        cube_base, best_len, cube_val))
                    STATE = "FILL"
                    state_frame = frame
                else
                    log("[no consecutive run found — dumping all 0->nonzero]\n")
                    -- Try: just look for any 28-ish cluster
                    -- Fallback: use first candidate as base
                    if #cands > 0 then
                        cube_base = cands[1].addr
                        cube_val = cands[1].val
                        log(string.format("[fallback cube base: 0x%04X val=%d]\n", cube_base, cube_val))
                        STATE = "FILL"
                        state_frame = frame
                    else
                        STATE = "DONE"
                    end
                end
            elseif #cands == 0 then
                -- Broaden: any changed byte that was 0
                log("\nNo 0->1..8 found. All changed bytes:\n")
                for i=0,0x7FF do
                    if (snap0[i] or 0) ~= (snapH[i] or 0) then
                        log(string.format("  0x%04X: %02X->%02X\n", i, snap0[i] or 0, snapH[i] or 0))
                    end
                end
                STATE = "DONE"
            else
                cube_base = cands[1].addr; cube_val = cands[1].val
                STATE = "FILL"; state_frame = frame
            end
        end
    end

    -- Fill all cubes with state-complete value
    if STATE == "FILL" and frame - state_frame >= 30 then
        if mem and cube_base then
            for i=0,55 do  -- try 56 bytes (generous for any pyramid layout)
                pcall(function() mem:write_u8(cube_base+i, cube_val) end)
            end
            log(string.format("[frame %d] filled 56 bytes at 0x%04X with %d\n", frame, cube_base, cube_val))
        end
        last_pal_key = pal_key()
        STATE = "WAIT_PAL"; state_frame = frame
    end

    -- Wait for palette write indicating level advance
    if STATE == "WAIT_PAL" then
        local key = pal_key()
        if key ~= last_pal_key then
            dump_palette("L" .. tostring(level_captured+1))
            last_pal_key = key
            STATE = "REFILL"; state_frame = frame
        end
        if frame - state_frame > 900 then
            log("[timeout: no palette change]\n")
            STATE = "DONE"
        end
    end

    -- Refill cubes for next level after transition settles
    if STATE == "REFILL" and frame - state_frame >= 240 then
        if level_captured < 4 and mem and cube_base then
            for i=0,55 do
                pcall(function() mem:write_u8(cube_base+i, cube_val) end)
            end
            log(string.format("[frame %d] refilled for next level\n", frame))
            last_pal_key = pal_key()
            STATE = "WAIT_PAL"; state_frame = frame
        else
            STATE = "DONE"
        end
    end

    if STATE == "DONE" or frame > 20000 then
        log(string.format("\n=== DONE: %d level palettes captured ===\n", level_captured))
        if logfile then logfile:close() end
        manager.machine:exit()
    end
end)
