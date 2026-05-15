-- qbert_pos_calibrate.lua: build the full pos_byte → (row, col) lookup table.
--
-- Boots clean (no DIP cheat), pokes lives=9. Drives Q*bert through a fixed
-- 28-cube hamiltonian-ish path during the L1R1 enemy-free window (~boot to
-- frame 5000). At each landing, reads RAM 0x0D64 and records the mapping.
--
-- Output: prints a Lua table literal that can be pasted into qbert_walker.lua.

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/pos_calibrate.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local DIRS = {
    DR = {dr= 1, dc= 1, name="P1 Right (Down-Right)"},
    DL = {dr= 1, dc= 0, name="P1 Down (Down-Left)"},
    UR = {dr=-1, dc= 0, name="P1 Up (Up-Right)"},
    UL = {dr=-1, dc=-1, name="P1 Left (Up-Left)"},
}
-- Combine MULTIPLE candidate bytes to find a unique-per-cube key.
-- 0x0D64 alone collides (e.g. (6,0)=(6,2)=0x26). Combining two bytes gives
-- 65536 possible values, more than enough for 28 cubes.
local PROBE_ADDRS = {0x0D58, 0x0D59, 0x0D5A, 0x0D5B, 0x0D64, 0x0D6A, 0x0D6C, 0x0D6D, 0x0F20, 0x0F22}
local LIVES_ADDR = 0x0D00

local function read_probes(m)
    local t = {}
    if m == nil then return t end
    for _, a in ipairs(PROBE_ADDRS) do
        local ok, v = pcall(function() return m:read_u8(a) end)
        t[a] = ok and v or 0
    end
    return t
end

local function probes_str(t)
    local s = ""
    for _, a in ipairs(PROBE_ADDRS) do
        local v = t[a]
        if v == nil then v = 0 end
        s = s .. string.format("%02X ", v)
    end
    return s
end

-- Hardcoded path covering all 28 cubes from apex.
-- Manually computed: snake through left edge, sweep rows 6→5 zigzag, then
-- climb right diagonal, then fill interior diamonds.
-- Each entry: direction to take. After execution from apex (0,0) we visit
-- a known sequence of cubes.
local PATH = {
    -- Left edge down: (0,0)→(1,0)→(2,0)→(3,0)→(4,0)→(5,0)→(6,0)
    "DL", "DL", "DL", "DL", "DL", "DL",
    -- Up to (5,0), DR/UR pattern across row 6 + row 5
    "UR", "DR", "UR", "DR", "UR", "DR", "UR", "DR", "UR", "DR", "UR", "DR",
    -- Now at (6,6). Climb right diagonal to apex
    "UL", "UL", "UL", "UL", "UL", "UL",
    -- Back at apex. Now visit interior cubes.
    -- Down to (1,1), then fan out to row 4 interior cubes, etc.
    "DR", "DL", "DL", "DL", "UR", "DR", "UR", "DR", "UL", "UL",
}

local frame, fields, mem = 0, {}, nil
local STATE = "BOOT"
local qrow, qcol = 0, 0
local path_idx = 0
local hop_dir = nil
local hop_start = 0
local last_hop = 0
-- cube_to_probes[(r,c)] = full probe table observed at that cube
local cube_to_probes = {}

local HOP_HOLD = 12
local HOP_COOLDOWN = 50

local function set(name, on) if fields[name] then fields[name]:set_value(on and 1 or 0) end end
local function valid_cube(r, c) return r >= 0 and r <= 6 and c >= 0 and c <= r end

local function record_cube(r, c, probes)
    local key = string.format("%d,%d", r, c)
    if not cube_to_probes[key] then
        cube_to_probes[key] = probes
        log(string.format("[learn] (%d,%d) → %s\n", r, c, probes_str(probes)))
    end
end

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for _, port in pairs(manager.machine.ioport.ports) do
            for name, fld in pairs(port.fields) do fields[name] = fld end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
    end

    set("Coin 1",         frame >= 500 and frame < 560)
    set("1 Player Start", frame >= 700 and frame < 760)
    if mem and frame > 700 then pcall(function() mem:write_u8(LIVES_ADDR, 9) end) end

    if hop_dir and frame - hop_start >= HOP_HOLD then
        set(DIRS[hop_dir].name, false)
        hop_dir = nil
    end

    if STATE == "BOOT" then
        if frame >= 1200 then
            STATE = "WALK"
            last_hop = frame + 90
            -- Direct probe read for diagnostic
            for _, a in ipairs(PROBE_ADDRS) do
                local ok, v = pcall(function() return mem:read_u8(a) end)
                log(string.format("[diag-read] frame=%d 0x%04X = ok=%s v=%s\n",
                    frame, a, tostring(ok), tostring(v)))
            end
            record_cube(0, 0, read_probes(mem))
            log(string.format("[INFO] WALK started\n"))
        end
        return
    end

    if STATE ~= "WALK" then return end

    if hop_dir or frame < last_hop + HOP_COOLDOWN then return end

    -- Take next hop in path
    path_idx = path_idx + 1
    if path_idx > #PATH then
        record_cube(qrow, qcol, read_probes(mem))  -- final cube
        STATE = "DONE"
        log("\n=== CUBE_TO_PROBES (per cube, all probe bytes) ===\n")
        log("addr      ")
        for _, a in ipairs(PROBE_ADDRS) do log(string.format("0x%04X ", a)) end
        log("\n")
        for r = 0, 6 do
            for c = 0, r do
                local key = string.format("%d,%d", r, c)
                local p = cube_to_probes[key]
                if p then
                    log(string.format("(%d,%d):    ", r, c))
                    for _, a in ipairs(PROBE_ADDRS) do log(string.format("  0x%02X  ", p[a])) end
                    log("\n")
                end
            end
        end

        -- Find UNIQUE single-byte indicator: an address whose value is distinct
        -- across all mapped cubes
        log("\n=== UNIQUE SINGLE-BYTE CANDIDATES ===\n")
        for _, a in ipairs(PROBE_ADDRS) do
            local seen = {}
            local unique = true
            for _, p in pairs(cube_to_probes) do
                if seen[p[a]] then unique = false; break end
                seen[p[a]] = true
            end
            log(string.format("  0x%04X: %s\n", a, unique and "UNIQUE ✓" or "collides"))
        end

        -- If single bytes collide, find a 2-byte combo that's unique
        log("\n=== UNIQUE 2-BYTE COMBOS ===\n")
        for i, a in ipairs(PROBE_ADDRS) do
            for j = i+1, #PROBE_ADDRS do
                local b = PROBE_ADDRS[j]
                local seen = {}
                local unique = true
                for _, p in pairs(cube_to_probes) do
                    local key = p[a] * 256 + p[b]
                    if seen[key] then unique = false; break end
                    seen[key] = true
                end
                if unique then
                    log(string.format("  (0x%04X, 0x%04X) UNIQUE ✓\n", a, b))
                end
            end
        end

        local n = 0; for _ in pairs(cube_to_probes) do n = n + 1 end
        log(string.format("\nMapped %d / 28 cubes\n", n))
        log("\nMissing cubes:\n")
        for r = 0, 6 do
            for c = 0, r do
                local key = string.format("%d,%d", r, c)
                if not cube_to_probes[key] then
                    log(string.format("  (%d,%d)\n", r, c))
                end
            end
        end
        if f then f:close() end
        manager.machine:exit()
        return
    end

    -- Read probes BEFORE issuing next hop — we've just finished the cooldown
    -- from the prior hop, so qrow,qcol is the cube we're currently sitting on.
    record_cube(qrow, qcol, read_probes(mem))

    local dir = PATH[path_idx]
    local d = DIRS[dir]
    local nr, nc = qrow + d.dr, qcol + d.dc
    if not valid_cube(nr, nc) then
        log(string.format("[SKIP] step %d: %s from (%d,%d) → invalid (%d,%d)\n",
            path_idx, dir, qrow, qcol, nr, nc))
        path_idx = path_idx - 1  -- don't consume this step; try again later
        return
    end

    set(DIRS[dir].name, true)
    hop_dir = dir; hop_start = frame; last_hop = frame
    qrow, qcol = nr, nc
end)
