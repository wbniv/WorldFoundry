-- qbert_bot.lua: AI bot that plays Q*bert to:
--   1. Complete all 28 cubes per round → trigger real L2/L3/L4 palette writes
--   2. Log enemy sprite positions per frame for WF reimplementation
--   3. Dead-reckon position via injected inputs; use 0x0081 for death detection

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG_PATH    = BASE .. "/docs/investigations/qbert_bot_run.log"
local ENEMY_PATH  = BASE .. "/docs/investigations/qbert_bot_enemies.csv"

local logfile   = io.open(LOG_PATH, "w")
local enemyfile = io.open(ENEMY_PATH, "w")
local function log(s)
    io.write(s); io.flush()
    if logfile then logfile:write(s); logfile:flush() end
end

if not logfile   then io.write("[ERROR] cannot open log: " .. LOG_PATH .. "\n") end
if not enemyfile then io.write("[ERROR] cannot open enemy: " .. ENEMY_PATH .. "\n") end
if enemyfile then
    enemyfile:write("frame,sprite_id,x,y,tile\n"); enemyfile:flush()
end

-- Gottlieb 4-bit DAC table
local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}
local function decode_pal(b0, b1)
    local r  = DAC[(b1 & 0xF) + 1]
    local g  = DAC[((b0 >> 4) & 0xF) + 1]
    local bv = DAC[(b0 & 0xF) + 1]
    return r, g, bv
end

-- ── Pyramid topology ────────────────────────────────────────────────────────
-- 7 rows (0..6); row r has cols 0..r; 28 cubes total
-- cube index: idx(r,c) = r*(r+1)/2 + c
-- adjacency: DR=(+1,+1), DL=(+1,0), UR=(-1,0), UL=(-1,-1)
local DIRS = {
    DR = {dr= 1, dc= 1},
    DL = {dr= 1, dc= 0},
    UR = {dr=-1, dc= 0},
    UL = {dr=-1, dc=-1},
}
-- MAME joystick field names (verified via qbert_fields.lua dump)
local DIR_FIELD = {
    DR = "P1 Right (Down-Right)",
    DL = "P1 Down (Down-Left)",
    UR = "P1 Up (Up-Right)",
    UL = "P1 Left (Up-Left)",
}

local function cidx(r, c) return r * (r + 1) / 2 + c end
local function valid_cube(r, c) return r >= 0 and r <= 6 and c >= 0 and c <= r end

local function neighbors_of(r, c)
    local res = {}
    for name, d in pairs(DIRS) do
        local nr, nc = r + d.dr, c + d.dc
        if valid_cube(nr, nc) then
            res[#res + 1] = {dir = name, r = nr, c = nc}
        end
    end
    return res
end

-- Warnsdorff: pick the unvisited neighbor with the fewest *its own* unvisited neighbors.
-- Ties broken by preferring higher row (deeper into pyramid).
local function is_done(visited, ci) return (visited[ci] or 0) >= 2 end

local function warnsdorff_next(r, c, visited)
    local cands = {}
    for _, n in ipairs(neighbors_of(r, c)) do
        if not is_done(visited, cidx(n.r, n.c)) then
            local score = 0
            for _, nn in ipairs(neighbors_of(n.r, n.c)) do
                if not is_done(visited, cidx(nn.r, nn.c)) then score = score + 1 end
            end
            -- Prefer cubes with fewer visits (state 0 over state 1)
            local visit_bonus = visited[cidx(n.r, n.c)] or 0
            cands[#cands + 1] = {dir = n.dir, r = n.r, c = n.c, score = score, vc = visit_bonus}
        end
    end
    if #cands == 0 then return nil end
    table.sort(cands, function(a, b)
        if a.vc ~= b.vc then return a.vc < b.vc end       -- fewer visits first
        if a.score ~= b.score then return a.score < b.score end
        return a.r > b.r
    end)
    return cands[1]
end

-- BFS to nearest unvisited cube; returns first direction to take (string like "DR").
-- Can traverse already-visited cubes to reach unvisited ones.
local function bfs_to_unvisited(r, c, visited)
    local queue = {{r = r, c = c, first = nil}}
    local seen  = {[cidx(r, c)] = true}
    while #queue > 0 do
        local cur = table.remove(queue, 1)
        if not is_done(visited, cidx(cur.r, cur.c)) and cur.first ~= nil then
            return cur.first
        end
        for _, n in ipairs(neighbors_of(cur.r, cur.c)) do
            local ni = cidx(n.r, n.c)
            if not seen[ni] then
                seen[ni] = true
                queue[#queue + 1] = {
                    r = n.r, c = n.c,
                    first = cur.first or n.dir,
                }
            end
        end
    end
    return nil
end

-- ── Palette state ────────────────────────────────────────────────────────────
local pal = {}; for i = 0, 31 do pal[i] = 0 end
local pal_writes      = 0
local last_pal_frame  = -1
local last_pal_key    = nil

local function pal_key()
    local t = {}
    for i = 0, 31 do t[i + 1] = string.format("%02X", pal[i]) end
    return table.concat(t)
end

-- Write palette data into the logfile (io.open inside callbacks is restricted in MAME)
local function save_palette(lv, rnd)
    log(string.format("=== PALETTE L%dR%d (frame %d) ===\n", lv, rnd, frame))
    for i = 0, 15 do
        local b0, b1 = pal[i * 2], pal[i * 2 + 1]
        local r, g, bv = decode_pal(b0, b1)
        log(string.format("pen%02d: #%02X%02X%02X  (raw: %02X %02X)\n", i, r, g, bv, b0, b1))
    end
    log("===\n")
end

-- ── Game state ───────────────────────────────────────────────────────────────
local frame         = 0
local fields        = {}
local mem           = nil

local STATE         = "BOOT"   -- BOOT → PLAY → DONE
local qrow, qcol   = 0, 0     -- Q*bert position (dead-reckoned)
local visited       = {}       -- visited[cidx] = visit count (1=state-1 in 2-step, 2=state-2)
local cubes_done    = 0        -- count of cubes with visit_count >= 1 (used by snap_phase)
local cubes_fully   = 0        -- count of cubes with visit_count >= 2 (used for round-clear)
local level         = 1
local round         = 1
local total_rounds  = 0
local deaths        = 0

-- 0x0081 observed to be 1 at apex and increments with hops (cube-visited counter?).
-- We use it purely for death detection: if it resets to ≤1 when we're not at apex.
local POS_ADDR       = 0x0081
local APEX_POS_VAL   = 1    -- value when Q*bert is at apex (observed from full_diff)
local LIVES_ADDR     = 0x0D00
local last_pos_val   = APEX_POS_VAL

local HOP_HOLD_FRAMES  = 12  -- frames to hold joystick input
local HOP_COOLDOWN     = 90  -- generous: ensures ROM fully processes each hop animation
local hop_dir          = nil -- current held direction or nil
local hop_start_frame  = 0
local last_hop_frame   = 0
local pal_capture_at   = -1  -- frame to snapshot pal[] as new-round palette (-1=disabled)

-- Stall detection: if no new cube visited in this many hops, force reset
local STALL_HOPS     = 8
local stall_counter  = 0

-- ── Per-round screenshot capture (walker protocol) ──────────────────────────
-- snap_phase:
--   "PRE"  = at apex, first move not yet made → snap state 0, force DR move
--   "POST" = first DR hop in flight → after it lands and cooldown clears, snap state 1
--   "DONE" = both snaps taken for this round; resume normal Warnsdorff
local snap_phase     = "PRE"
local snap_log_path  = BASE .. "/scripts/research/mame/walker_snaps.txt"
local snap_log       = io.open(snap_log_path, "w")
local snap_idx       = 0
local function snap_record(label)
    snap_idx = snap_idx + 1
    manager.machine.video:snapshot()
    if snap_log then
        snap_log:write(string.format("%04d L%dR%d %s frame=%d\n",
            snap_idx - 1, level, round, label, frame))
        snap_log:flush()
    end
    log(string.format("[walker-snap] idx=%04d L%dR%d %s frame=%d\n",
        snap_idx - 1, level, round, label, frame))
end

local function set_input(name, val)
    if fields[name] then fields[name]:set_value(val and 1 or 0) end
end

local function reset_to_apex()
    qrow, qcol = 0, 0
    visited = {}
    visited[cidx(0, 0)] = 1
    cubes_done = 1
    cubes_fully = 0
    hop_dir = nil
    stall_counter = 0
    last_hop_frame = frame + HOP_COOLDOWN * 3  -- wait for respawn animation
    deaths = deaths + 1
    snap_phase = "PRE"
    log(string.format("[bot] reset_to_apex  L%dR%d  cubes=%d  deaths=%d  frame=%d\n",
        level, round, cubes_done, deaths, frame))
end

-- ── Main loop ────────────────────────────────────────────────────────────────
emu.register_frame_done(function()
    frame = frame + 1

    -- Frame 1: enumerate inputs, get memory space, install palette tap
    if frame == 1 then
        for tag, port in pairs(manager.machine.ioport.ports) do
            for name, field in pairs(port.fields) do
                fields[name] = field
            end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if mem then
            local ok = pcall(function()
                mem:install_write_tap(0x5000, 0x501F, "pal_bot", function(off, data, mask)
                    pal[off - 0x5000] = data & 0xFF
                    pal_writes = pal_writes + 1
                    last_pal_frame = frame
                end)
            end)
            log("[INFO] palette tap=" .. tostring(ok) .. "\n")
            -- Log all known direction fields for verification
            for dir, fname in pairs(DIR_FIELD) do
                log(string.format("[INFO] field '%s' found=%s\n",
                    fname, tostring(fields[fname] ~= nil)))
            end
        else
            log("[ERROR] no maincpu program space\n")
        end
        last_pal_key = pal_key()
    end

    -- Coin + 1P Start (delayed to allow self-test to complete, ~8-12s emulated)
    set_input("Coin 1",         frame >= 500 and frame < 530)
    set_input("1 Player Start", frame >= 700 and frame < 730)

    -- Keep lives at 9 every frame once game is active
    if mem and frame > 700 then
        pcall(function() mem:write_u8(LIVES_ADDR, 9) end)
    end

    -- Log Q*bert position every 300 frames to confirm movement
    if mem and frame > 700 and frame % 300 == 0 then
        local pv = 0; pcall(function() pv = mem:read_u8(POS_ADDR) end)
        log(string.format("[pos] frame=%d 0x%04X=%d (qrow=%d qcol=%d cubes=%d)\n",
            frame, POS_ADDR, pv, qrow, qcol, cubes_done))
    end

    -- Transition from BOOT to PLAY (wait until after coin+start settled)
    if STATE == "BOOT" and frame >= 1000 then
        STATE = "PLAY"
        reset_to_apex()
        last_pal_key = pal_key()
        pal_capture_at = frame + 60  -- capture initial palette after game loads
        log(string.format("[bot] PLAY started at frame %d\n", frame))
    end

    if STATE ~= "PLAY" then return end

    -- ── Scheduled palette snapshot (mid-transition, using write-tap pal[]) ────
    -- Palette RAM is write-only from CPU; pal[] is the only readable copy.
    -- We sample after the round-clear animation has played (frame+240 into pause).
    if pal_capture_at > 0 and frame == pal_capture_at then
        local key = pal_key()
        local new_lv = level  -- level/round already incremented by round-complete
        local new_rnd = round
        log(string.format("=== PALETTE L%dR%d (frame %d, pal_writes=%d) ===\n",
            new_lv, new_rnd, frame, pal_writes))
        for _pi = 0, 15 do
            local _b0, _b1 = pal[_pi * 2], pal[_pi * 2 + 1]
            local _r  = DAC[(_b1 & 0xF) + 1]
            local _g  = DAC[((_b0 >> 4) & 0xF) + 1]
            local _bv = DAC[(_b0 & 0xF) + 1]
            log(string.format("pen%02d: #%02X%02X%02X  (raw: %02X %02X)\n",
                _pi, _r, _g, _bv, _b0, _b1))
        end
        log("===\n")
        if key ~= last_pal_key then
            log(string.format("[palette] changed at L%dR%d\n", new_lv, new_rnd))
            last_pal_key = key
        else
            log(string.format("[palette] unchanged at L%dR%d\n", new_lv, new_rnd))
        end
        pal_capture_at = -1
    end

    -- ── Enemy sprite logging (every 4 frames) ────────────────────────────────
    if frame % 4 == 0 and mem and enemyfile then
        pcall(function()
            -- Sprite RAM at 0x3000; each entry is 4 bytes: Y, X, tile, attr
            for i = 0, 15 do
                local base = 0x3000 + i * 4
                local sy   = mem:read_u8(base)
                local sx   = mem:read_u8(base + 1)
                local tile = mem:read_u8(base + 2)
                if sy > 8 and sx > 8 and sy < 248 and sx < 248 then
                    enemyfile:write(string.format("%d,%d,%d,%d,%d\n",
                        frame, i, sx, sy, tile))
                end
            end
            enemyfile:flush()
        end)
    end

    -- ── Release held joystick input ───────────────────────────────────────────
    if hop_dir then
        if frame - hop_start_frame >= HOP_HOLD_FRAMES then
            set_input(DIR_FIELD[hop_dir], false)
            hop_dir = nil
        else
            set_input(DIR_FIELD[hop_dir], true)
        end
    end

    -- ── Death detection via 0x0081 ────────────────────────────────────────────
    if mem and frame % 4 == 0 then
        local pos_val = 0
        pcall(function() pos_val = mem:read_u8(POS_ADDR) end)
        if pos_val ~= last_pos_val then
            -- Detected a reset to apex value when we shouldn't be there
            if pos_val <= APEX_POS_VAL and cubes_done > 3 then
                log(string.format("[bot] death detected: 0x%04X=%d→%d at (%d,%d)  frame=%d\n",
                    POS_ADDR, last_pos_val, pos_val, qrow, qcol, frame))
                reset_to_apex()
            end
            last_pos_val = pos_val
        end
    end

    -- ── Bot movement ─────────────────────────────────────────────────────────
    if hop_dir ~= nil then return end  -- still holding a hop
    if frame < last_hop_frame + HOP_COOLDOWN then return end  -- cooldown

    -- Mark current cube as visited (track count, not just bool)
    local ci = cidx(qrow, qcol)
    local prev_count = visited[ci] or 0
    local was_new = (prev_count == 0)
    visited[ci] = prev_count + 1
    if was_new then
        cubes_done = cubes_done + 1
        stall_counter = 0
        log(string.format("[bot] new cube (%d,%d) idx=%d  %d/28  L%dR%d  frame=%d\n",
            qrow, qcol, ci, cubes_done, level, round, frame))
    elseif visited[ci] == 2 then
        cubes_fully = cubes_fully + 1
        stall_counter = 0
    end

    -- Round complete? (every cube visited at least 2x → covers both 1-step and 2-step rounds)
    if cubes_fully >= 28 then
        log(string.format("[bot] ROUND COMPLETE L%dR%d  total_rounds=%d  frame=%d\n",
            level, round, total_rounds + 1, frame))
        total_rounds = total_rounds + 1
        round = round + 1
        if round > 4 then round = 1; level = level + 1 end
        -- Reset cube tracking for new round; wait for transition animation
        visited = {}
        cubes_done = 0
        cubes_fully = 0
        qrow, qcol = 0, 0
        stall_counter = 0
        snap_phase = "PRE"  -- arm walker snaps for next round
        -- Schedule palette capture for after transition animation (240 frames in)
        pal_capture_at = frame + 240
        last_hop_frame = frame + 360  -- ~6 s pause for level transition
        return
    end

    -- ── Walker snap state machine ─────────────────────────────────────────────
    -- PRE       → at apex, no hops yet → snap state 0, force DR hop to (1,1)
    -- AFTER_DR  → at (1,1) after DR landed → force UL hop back to apex
    -- AFTER_UL  → back at apex with (1,1) visited once, no Q*bert-sprite
    --             occlusion at sample point (137, 80) → snap state 1
    -- DONE      → resume normal Warnsdorff to clear round
    if snap_phase == "PRE" and qrow == 0 and qcol == 0 and cubes_done == 1 then
        snap_record("state0")
        snap_phase = "AFTER_DR"
        hop_dir       = "DR"
        hop_start_frame = frame
        last_hop_frame  = frame
        local d = DIRS["DR"]
        qrow, qcol    = qrow + d.dr, qcol + d.dc
        set_input(DIR_FIELD["DR"], true)
        return
    end

    if snap_phase == "AFTER_DR" and qrow == 1 and qcol == 1 then
        -- (1,1) was just marked visited at the top of this iteration
        snap_phase = "AFTER_UL"
        hop_dir       = "UL"
        hop_start_frame = frame
        last_hop_frame  = frame
        local d = DIRS["UL"]
        qrow, qcol    = qrow + d.dr, qcol + d.dc
        set_input(DIR_FIELD["UL"], true)
        return
    end

    if snap_phase == "AFTER_UL" and qrow == 0 and qcol == 0 then
        snap_record("state1")
        snap_phase = "DONE"
        -- fall through to normal Warnsdorff
    end

    -- Pick next direction
    local next_move = warnsdorff_next(qrow, qcol, visited)

    if not next_move then
        -- All unvisited neighbors exhausted; BFS through visited cubes
        local dir = bfs_to_unvisited(qrow, qcol, visited)
        if dir then
            local d = DIRS[dir]
            next_move = {dir = dir, r = qrow + d.dr, c = qcol + d.dc}
        end
    end

    -- Stall detection
    if not was_new then
        stall_counter = stall_counter + 1
        if stall_counter >= STALL_HOPS then
            log(string.format("[bot] stall detected after %d same-cube hops  frame=%d\n",
                stall_counter, frame))
            reset_to_apex()
            return
        end
    else
        stall_counter = 0
    end

    if next_move == nil then
        -- Fully stuck (all 28 reachable but cubes_done < 28 — shouldn't happen)
        log(string.format("[bot] STUCK at (%d,%d) cubes=%d; forcing reset  frame=%d\n",
            qrow, qcol, cubes_done, frame))
        reset_to_apex()
        return
    end

    if not valid_cube(next_move.r, next_move.c) then
        log(string.format("[bot] invalid move %s from (%d,%d); skipping  frame=%d\n",
            next_move.dir, qrow, qcol, frame))
        last_hop_frame = frame
        return
    end

    -- Inject hop
    hop_dir       = next_move.dir
    hop_start_frame = frame
    last_hop_frame  = frame
    qrow, qcol    = next_move.r, next_move.c
    set_input(DIR_FIELD[hop_dir], true)

    -- Periodic status
    if frame % 1800 == 0 then
        log(string.format("[status] frame=%d  L%dR%d  cubes=%d/28  rounds=%d  deaths=%d  pal_writes=%d\n",
            frame, level, round, cubes_done, total_rounds, deaths, pal_writes))
    end

    -- Exit after L4 (~56 visits/round × 16 rounds × 30 frames/hop = ~27000 frames; 144000 = 40 min budget)
    if level > 4 or frame >= 144000 then
        log(string.format("[done] L%dR%d  rounds=%d  deaths=%d  pal_writes=%d  frame=%d\n",
            level, round, total_rounds, deaths, pal_writes, frame))
        if logfile    then logfile:close() end
        if enemyfile  then enemyfile:close() end
        manager.machine:exit()
    end
end)
