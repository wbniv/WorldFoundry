-- qbert_walker.lua: ROM-grounded Q*bert Warnsdorff bot.
--
-- Plays through L1R1 → L4R4 capturing 2 screenshots per round (state-0 at apex,
-- state-1 at apex after a DR+UL dance). No DIP cheat — boots clean, pokes
-- 0x0D00=9 every frame for unlim lives.
--
-- Key fix vs qbert_bot.lua: position is read from RAM 0x0D64 (per
-- qbert_position_hunt.lua), so hops are verified, not dead-reckoned. Round
-- transitions are detected via palette write-tap delta (≥16 writes = palette
-- changed = ROM advanced rounds).

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG_PATH = BASE .. "/docs/investigations/qbert_walker_run.log"
local SNAP_LOG = BASE .. "/scripts/research/mame/walker_snaps.txt"
local logfile = io.open(LOG_PATH, "w")
local snaplog = io.open(SNAP_LOG, "w")
local function log(s) io.write(s); io.flush(); if logfile then logfile:write(s); logfile:flush() end end

-- Topology
local DIRS = {
    DR = {dr= 1, dc= 1, name="P1 Right (Down-Right)"},
    DL = {dr= 1, dc= 0, name="P1 Down (Down-Left)"},
    UR = {dr=-1, dc= 0, name="P1 Up (Up-Right)"},
    UL = {dr=-1, dc=-1, name="P1 Left (Up-Left)"},
}
local function cidx(r, c) return r * (r + 1) / 2 + c end
local function valid_cube(r, c) return r >= 0 and r <= 6 and c >= 0 and c <= r end
local function neighbors_of(r, c)
    local res = {}
    for name, d in pairs(DIRS) do
        local nr, nc = r + d.dr, c + d.dc
        if valid_cube(nr, nc) then res[#res+1] = {dir=name, r=nr, c=nc} end
    end
    return res
end

-- ── State ────────────────────────────────────────────────────────────────────
local frame, fields, mem = 0, {}, nil
local STATE = "BOOT"
local qrow, qcol = 0, 0
local visited = {}        -- visited[ci] = visit count
local cubes_done = 0      -- cubes with visit_count >= 1
local cubes_fully = 0     -- cubes with visit_count >= 2
local hop_dir = nil
local hop_start_frame = 0
local last_hop_frame = 0
local pending_dir = nil   -- direction issued last; verify on next iteration
local pos_at_hop_start = 0
local stuck_retries = 0
local deaths = 0

local level, round, total_rounds = 1, 1, 0

-- Snap protocol: PRE → AFTER_DR → AFTER_UL → DONE per round
local snap_phase = "PRE"
local snap_idx = 0
local pending_snap_label = nil   -- snap on the frame the bot is back at apex

-- RAM addresses
local POS_ADDR  = 0x0D64  -- Q*bert position byte (verified via qbert_position_hunt)
local APEX_VAL  = 0xB8    -- value of POS_ADDR when at apex
local LIVES_ADDR = 0x0D00

-- Palette write-tap (round-clear detection)
local pal_writes = 0
local pal_writes_last_round = 0

local HOP_HOLD = 12
local HOP_COOLDOWN = 50

local function set_input(name, val) if fields[name] then fields[name]:set_value(val and 1 or 0) end end

local function snap_record(label)
    snap_idx = snap_idx + 1
    manager.machine.video:snapshot()
    if snaplog then
        snaplog:write(string.format("%04d L%dR%d %s frame=%d pos=0x%02X\n",
            snap_idx-1, level, round, label, frame,
            mem and mem:read_u8(POS_ADDR) or 0))
        snaplog:flush()
    end
    log(string.format("[snap] idx=%04d L%dR%d %s frame=%d\n", snap_idx-1, level, round, label, frame))
end

-- Warnsdorff: prefer cubes with fewer visits, then fewer unvisited neighbors, then deeper row
local function warnsdorff_next(r, c)
    local cands = {}
    for _, n in ipairs(neighbors_of(r, c)) do
        local vc = visited[cidx(n.r, n.c)] or 0
        if vc < 2 then
            local score = 0
            for _, nn in ipairs(neighbors_of(n.r, n.c)) do
                if (visited[cidx(nn.r, nn.c)] or 0) < 2 then score = score + 1 end
            end
            cands[#cands+1] = {dir=n.dir, r=n.r, c=n.c, vc=vc, score=score}
        end
    end
    if #cands == 0 then return nil end
    table.sort(cands, function(a, b)
        if a.vc ~= b.vc then return a.vc < b.vc end
        if a.score ~= b.score then return a.score < b.score end
        return a.r > b.r
    end)
    return cands[1]
end

-- BFS to nearest non-fully-visited cube (for when neighbors are all done)
local function bfs_to_unvisited(r, c)
    local q = {{r=r, c=c, first=nil}}
    local seen = {[cidx(r, c)] = true}
    while #q > 0 do
        local cur = table.remove(q, 1)
        if (visited[cidx(cur.r, cur.c)] or 0) < 2 and cur.first then return cur.first end
        for _, n in ipairs(neighbors_of(cur.r, cur.c)) do
            local ni = cidx(n.r, n.c)
            if not seen[ni] then
                seen[ni] = true
                q[#q+1] = {r=n.r, c=n.c, first=cur.first or n.dir}
            end
        end
    end
    return nil
end

local function reset_round()
    qrow, qcol = 0, 0
    visited = {[cidx(0,0)] = 1}
    cubes_done = 1
    cubes_fully = 0
    hop_dir = nil
    pending_dir = nil
    snap_phase = "PRE"
    stuck_retries = 0
    last_hop_frame = frame + 90  -- spawn drop-in settle
end

-- ── Main loop ────────────────────────────────────────────────────────────────
emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for _, port in pairs(manager.machine.ioport.ports) do
            for name, fld in pairs(port.fields) do fields[name] = fld end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if mem then
            mem:install_write_tap(0x5000, 0x501F, "pal_walker", function(off, data, mask)
                pal_writes = pal_writes + 1
            end)
        end
        log("[INFO] walker boot\n")
    end

    set_input("Coin 1",         frame >= 500 and frame < 530)
    set_input("1 Player Start", frame >= 700 and frame < 730)
    if mem and frame > 700 then pcall(function() mem:write_u8(LIVES_ADDR, 9) end) end

    -- Release held hop input
    if hop_dir and frame - hop_start_frame >= HOP_HOLD then
        set_input(DIRS[hop_dir].name, false)
        hop_dir = nil
    end

    if STATE == "BOOT" then
        if frame >= 1200 then
            STATE = "PLAY"
            reset_round()
            pal_writes_last_round = pal_writes
            log(string.format("[INFO] PLAY at frame %d\n", frame))
        end
        return
    end

    if STATE ~= "PLAY" then return end

    -- Periodic status (logs always, even during cooldown waits)
    if frame % 600 == 0 then
        local p = mem and mem:read_u8(POS_ADDR) or 0
        log(string.format("[status] frame=%d L%dR%d at(%d,%d) pos=0x%02X cubes=%d/28 fully=%d phase=%s pending=%s hop=%s pal=%d cool_left=%d\n",
            frame, level, round, qrow, qcol, p, cubes_done, cubes_fully,
            snap_phase, tostring(pending_dir), tostring(hop_dir), pal_writes,
            (last_hop_frame + HOP_COOLDOWN) - frame))
    end

    -- Detect round-clear: palette delta ≥16 since last round
    if pal_writes - pal_writes_last_round >= 32 then
        log(string.format("[bot] ROUND CLEAR detected (pal_writes %d→%d)  L%dR%d  frame=%d\n",
            pal_writes_last_round, pal_writes, level, round, frame))
        pal_writes_last_round = pal_writes
        total_rounds = total_rounds + 1
        round = round + 1
        if round > 4 then round = 1; level = level + 1 end
        reset_round()
        last_hop_frame = frame + 360  -- transition animation buffer
        return
    end

    -- Wait while held hop or cooldown
    if hop_dir or frame < last_hop_frame + HOP_COOLDOWN then return end

    -- Read true Q*bert position from ROM
    local cur_pos = mem and mem:read_u8(POS_ADDR) or 0

    -- ── Verify pending hop landed (or retry) ─────────────────────────────────
    if pending_dir then
        if cur_pos == pos_at_hop_start then
            -- Hop dropped — retry same direction. Cap retries.
            stuck_retries = stuck_retries + 1
            if stuck_retries > 6 then
                log(string.format("[bot] STUCK (>6 retries) — assuming death; reset frame=%d\n", frame))
                reset_round()
                deaths = deaths + 1
                return
            end
            -- Reissue same dir without changing qrow/qcol
            hop_dir = pending_dir
            hop_start_frame = frame
            last_hop_frame = frame
            pos_at_hop_start = cur_pos
            set_input(DIRS[pending_dir].name, true)
            return
        end
        -- Hop confirmed — advance bot's qrow/qcol per the issued direction.
        local d = DIRS[pending_dir]
        qrow, qcol = qrow + d.dr, qcol + d.dc
        stuck_retries = 0
        pending_dir = nil

        -- If we arrived back at apex AND were waiting to snap state-1, do it now.
        if pending_snap_label and cur_pos == APEX_VAL then
            snap_record(pending_snap_label)
            pending_snap_label = nil
            snap_phase = "DONE"
        end
    end

    -- ── Mark current cube ────────────────────────────────────────────────────
    local ci = cidx(qrow, qcol)
    local prev = visited[ci] or 0
    visited[ci] = prev + 1
    if prev == 0 then cubes_done = cubes_done + 1
    elseif prev == 1 then cubes_fully = cubes_fully + 1 end

    -- ── Walker snap state machine ────────────────────────────────────────────
    if snap_phase == "PRE" and qrow == 0 and qcol == 0 and cur_pos == APEX_VAL then
        snap_record("state0")
        -- Force DR hop
        snap_phase = "AFTER_DR"
        pending_dir = "DR"
        pos_at_hop_start = cur_pos
        hop_dir = "DR"; hop_start_frame = frame; last_hop_frame = frame
        set_input(DIRS["DR"].name, true)
        return
    end

    if snap_phase == "AFTER_DR" and qrow == 1 and qcol == 1 then
        -- Force UL back to apex
        snap_phase = "AFTER_UL"
        pending_dir = "UL"
        pos_at_hop_start = cur_pos
        hop_dir = "UL"; hop_start_frame = frame; last_hop_frame = frame
        set_input(DIRS["UL"].name, true)
        pending_snap_label = "state1"  -- snap when we land back at apex
        return
    end

    -- ── Normal Warnsdorff move ───────────────────────────────────────────────
    local move = warnsdorff_next(qrow, qcol)
    if not move then
        local d = bfs_to_unvisited(qrow, qcol)
        if d then
            local dd = DIRS[d]
            move = {dir=d, r=qrow + dd.dr, c=qcol + dd.dc}
        end
    end

    if not move then
        -- All cubes visited 2x — wait for round transition (palette tap will fire)
        last_hop_frame = frame  -- spin until palette change
        return
    end

    -- Issue hop
    pending_dir = move.dir
    pos_at_hop_start = cur_pos
    hop_dir = move.dir
    hop_start_frame = frame
    last_hop_frame = frame
    set_input(DIRS[move.dir].name, true)


    -- Exit
    if level > 4 or frame >= 200000 then
        log(string.format("[done] L%dR%d rounds=%d deaths=%d pal_writes=%d frame=%d\n",
            level, round, total_rounds, deaths, pal_writes, frame))
        if logfile then logfile:close() end
        if snaplog then snaplog:close() end
        manager.machine:exit()
    end
end)
