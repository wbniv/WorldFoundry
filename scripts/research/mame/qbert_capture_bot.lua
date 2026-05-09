-- qbert_capture_bot.lua: capture all 3 cube states (0, 1, 2) for every round.
--
-- Design: real gameplay (NO DIP cheat → no Demo AI interference).
-- Per round:
--   1. Snap state-0 (Q*bert at apex, all cubes unvisited)
--   2. Hop DR → land on (1,1). Snap "after 1 visit" (state 1 of (1,1))
--   3. Hop UL → return to apex. Hop DR → land on (1,1) 2nd time. Snap
--      "after 2 visits" (state 2 of (1,1) for 2-step rounds; or state 0 if
--      reverting and 1-step round)
--   4. Hop UL back to apex. Then Warnsdorff to complete the round naturally.
--   5. Round auto-advances → wait for next round → loop.
--
-- Unlim lives via mem:write_u8(0x0D00, 9) every frame.

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/capture_bot.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

-- ── Pyramid topology ────────────────────────────────────────────────────────
local DIRS = {
    DR = {dr= 1, dc= 1}, DL = {dr= 1, dc= 0},
    UR = {dr=-1, dc= 0}, UL = {dr=-1, dc=-1},
}
local DIR_FIELD = {
    DR = "P1 Right (Down-Right)", DL = "P1 Down (Down-Left)",
    UR = "P1 Up (Up-Right)",      UL = "P1 Left (Up-Left)",
}
local function cidx(r, c) return r * (r + 1) / 2 + c end
local function valid_cube(r, c) return r >= 0 and r <= 6 and c >= 0 and c <= r end

local function neighbors(r, c)
    local res = {}
    for name, d in pairs(DIRS) do
        local nr, nc = r + d.dr, c + d.dc
        if valid_cube(nr, nc) then res[#res + 1] = {dir=name, r=nr, c=nc} end
    end
    return res
end

local function warnsdorff_next(r, c, visited)
    local cands = {}
    for _, n in ipairs(neighbors(r, c)) do
        if not visited[cidx(n.r, n.c)] then
            local s = 0
            for _, nn in ipairs(neighbors(n.r, n.c)) do
                if not visited[cidx(nn.r, nn.c)] then s = s + 1 end
            end
            cands[#cands + 1] = {dir=n.dir, r=n.r, c=n.c, score=s}
        end
    end
    if #cands == 0 then return nil end
    table.sort(cands, function(a, b)
        if a.score ~= b.score then return a.score < b.score end
        return a.r > b.r
    end)
    return cands[1]
end

local function bfs_to_unvisited(r, c, visited)
    local q = {{r=r, c=c, first=nil}}
    local seen = {[cidx(r,c)] = true}
    while #q > 0 do
        local cur = table.remove(q, 1)
        if not visited[cidx(cur.r, cur.c)] and cur.first then return cur.first end
        for _, n in ipairs(neighbors(cur.r, cur.c)) do
            local ni = cidx(n.r, n.c)
            if not seen[ni] then
                seen[ni] = true
                q[#q+1] = {r=n.r, c=n.c, first=cur.first or n.dir}
            end
        end
    end
    return nil
end

-- ── State ────────────────────────────────────────────────────────────────────
local frame, fields, mem = 0, {}, nil
local STATE = "BOOT"  -- BOOT → SNAP_S0 → HOP1_OUT → SNAP_HOP1 → HOP1_BACK
                      --     → HOP2_OUT → SNAP_HOP2 → HOP2_BACK → COMPLETE_ROUND
                      --     → WAIT_NEW_ROUND → SNAP_S0
local round_num = 0
local MAX_ROUNDS = 16

local qrow, qcol = 0, 0
local visit_count = {}  -- per-cube visit count
local cubes_complete = 0  -- cubes that reached final state (state 2 for 2-step, or state 1 for L1)
local hop_dir = nil
local hop_start = 0
local last_hop = 0
local phase_start = 0

local LIVES = 0x0D00
local POS   = 0x0081  -- visit/hop counter, useful for death detection
local last_pos = 0
local last_pos_byte = 0  -- RAM 0x81 reading before last hop (for hop verification)
local last_hop_dir = nil
local stuck_retries = 0

local HOP_HOLD = 8
local HOP_COOLDOWN = 30

local function set(name, on) if fields[name] then fields[name]:set_value(on and 1 or 0) end end

local function snap(label)
    manager.machine.video:snapshot()
    local rr = mem and mem:read_u8(POS) or 0
    log(string.format("[snap %s] round=%d frame=%d 0x81=0x%02X qpos=(%d,%d)\n",
        label, round_num, frame, rr, qrow, qcol))
end

local function start_hop(dir)
    hop_dir = dir
    hop_start = frame
    last_hop = frame
    set(DIR_FIELD[dir], true)
    local d = DIRS[dir]
    qrow, qcol = qrow + d.dr, qcol + d.dc
end

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for _, port in pairs(manager.machine.ioport.ports) do
            for name, fld in pairs(port.fields) do fields[name] = fld end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        log("[INFO] qbert_capture_bot starting\n")
    end

    -- Boot: coin + start
    set("Coin 1", frame >= 500 and frame < 540)
    set("1 Player Start", frame >= 700 and frame < 740)

    -- Unlim lives
    if mem and frame > 750 then mem:write_u8(LIVES, 9) end

    -- Release held hop after HOP_HOLD frames
    if hop_dir and frame - hop_start >= HOP_HOLD then
        set(DIR_FIELD[hop_dir], false)
        hop_dir = nil
    end

    -- Wait for game to be playable (Q*bert spawn animation completes)
    if STATE == "BOOT" then
        if frame >= 1200 then
            STATE = "SNAP_S0"
            phase_start = frame
            qrow, qcol = 0, 0
            visit_count = {}
            cubes_complete = 0
            round_num = round_num + 1
            last_hop = frame + 90  -- give 90 extra frames for Q*bert spawn anim
            log(string.format("[round %d START] frame=%d\n", round_num, frame))
        end
        return
    end

    -- Wait between hops (cooldown)
    if hop_dir or frame < last_hop + HOP_COOLDOWN then return end

    if STATE == "SNAP_S0" then
        snap("s0")
        STATE = "HOP1_OUT"
        return
    end

    if STATE == "HOP1_OUT" then
        start_hop("DR")
        STATE = "WAIT_HOP1_LAND"
        return
    end

    if STATE == "WAIT_HOP1_LAND" then
        snap("hop1")  -- (1,1) visited once
        local ci = cidx(qrow, qcol)
        visit_count[ci] = (visit_count[ci] or 0) + 1
        STATE = "HOP1_BACK"
        return
    end

    if STATE == "HOP1_BACK" then
        start_hop("UL")
        STATE = "WAIT_BACK1_LAND"
        return
    end

    if STATE == "WAIT_BACK1_LAND" then
        local ci = cidx(qrow, qcol)
        visit_count[ci] = (visit_count[ci] or 0) + 1
        STATE = "HOP2_OUT"
        return
    end

    if STATE == "HOP2_OUT" then
        start_hop("DR")
        STATE = "WAIT_HOP2_LAND"
        return
    end

    if STATE == "WAIT_HOP2_LAND" then
        snap("hop2")  -- (1,1) visited twice
        local ci = cidx(qrow, qcol)
        visit_count[ci] = (visit_count[ci] or 0) + 1
        STATE = "HOP2_BACK"
        return
    end

    if STATE == "HOP2_BACK" then
        start_hop("UL")
        STATE = "WAIT_BACK2_LAND"
        return
    end

    if STATE == "WAIT_BACK2_LAND" then
        local ci = cidx(qrow, qcol)
        visit_count[ci] = (visit_count[ci] or 0) + 1
        -- Now visit all 28 cubes via Warnsdorff to actually complete the round.
        -- For 2-step rounds, may need 2 visits per cube.
        STATE = "WARNSDORFF"
        return
    end

    if STATE == "WARNSDORFF" then
        local ci = cidx(qrow, qcol)
        visit_count[ci] = (visit_count[ci] or 0) + 1
        local cands = {}
        for _, n in ipairs(neighbors(qrow, qcol)) do
            local nci = cidx(n.r, n.c)
            local vc = visit_count[nci] or 0
            cands[#cands+1] = {dir=n.dir, r=n.r, c=n.c, vc=vc}
        end
        table.sort(cands, function(a, b)
            if a.vc ~= b.vc then return a.vc < b.vc end
            return a.r > b.r
        end)
        if cands[1] then
            start_hop(cands[1].dir)
        else
            log("[bot] no neighbors? STUCK\n")
            STATE = "DONE"
        end

        local min_vc = 9
        for r = 0, 6 do
            for c = 0, r do
                min_vc = math.min(min_vc, visit_count[cidx(r, c)] or 0)
            end
        end
        if min_vc >= 2 then
            log(string.format("[round %d] all cubes visited 2+ times → wait for round-end animation\n", round_num))
            STATE = "WAIT_NEW_ROUND"
            phase_start = frame
        end
        return
    end

    if STATE == "WAIT_NEW_ROUND" then
        -- Wait ~5s for round-end animation + new round to spawn Q*bert at apex
        if frame > phase_start + 300 then
            if round_num >= MAX_ROUNDS then
                log("[done]\n")
                if f then f:close() end
                manager.machine:exit()
                return
            end
            STATE = "SNAP_S0"
            phase_start = frame
            qrow, qcol = 0, 0
            visit_count = {}
            cubes_complete = 0
            round_num = round_num + 1
            last_hop = frame + 90  -- spawn drop-in settle (mirrors BOOT path; needed for L4R1)
            last_hop_dir = nil
            stuck_retries = 0
            log(string.format("[round %d START] frame=%d\n", round_num, frame))
        end
        return
    end
end)
