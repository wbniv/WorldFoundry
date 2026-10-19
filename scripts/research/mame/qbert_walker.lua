-- qbert_walker.lua: DIP-cheat-driven multi-round walker. Captures state-0
-- and state-1 screenshots for all 16 visual rounds using the same +119-frame
-- timing window proven by qbert_round_byte_hunt.lua and qbert_l4r1_walker.lua.
--
-- Why DIP cheat (and not bot-driven Warnsdorff):
--
--   The bot-driven approach (Phase C) hit drift — sprite X/Y position bytes
--   have animation transients so per-cube tracking is unreliable; ROM never
--   round-cleared because some cubes weren't actually visited 2x in ROM. DIP
--   "Demo Mode (Unlim Lives, Start=Adv)" cheat sidesteps both issues:
--   - Demo AI handles round-clearing internally.
--   - Start=Adv lets us shortcut to the next round whenever we want.
--
-- Per round (round_num 1..19, see VISUAL_TAG mapping for off-by-one):
--   1. WAIT_RAM: detect ram[0x081] change.
--   2. AT ram-change frame X: snap("state0") — apex pristine.
--   3. X+30: inject DR hop. X+42: release.
--   4. X+77: inject UL hop. X+89: release.
--   5. X+119: snap("state1") — apex with (1,1) cube flipped exactly once.
--      HUD has updated to current visual round by this frame.
--   6. ADVANCE: press Start to trigger cheat-advance.
--
-- Output: walker_snaps.txt logs each snap with index, round_num, label, frame.
-- Use sample_cube_colors.py to extract per-round state colors from the saved
-- PNGs.

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/docs/investigations/qbert_walker_run.log"
local SNAP_LOG = BASE .. "/scripts/research/mame/walker_snaps.txt"
local logfile = io.open(LOG, "w")
local snaplog = io.open(SNAP_LOG, "w")
local function log(s) io.write(s); io.flush(); if logfile then logfile:write(s); logfile:flush() end end

local CHEAT = "Demo Mode (Unlim Lives, Start=Adv (Cheat)"

-- Timing (matches qbert_round_shots.lua's proven hop_snap_at = X+119)
local HOP_DELAY     = 30
local HOP_HOLD      = 12
local INTER_HOP     = 35
local POST_HOP_WAIT = 30
local ADVANCE_DELAY = 5
local ADVANCE_HOLD  = 30

-- Per qbert_round_byte_hunt: round_num 1..19 maps to visual rounds with
-- L2/L3/L4 transitions interleaved at indices 5/10/15.
local VISUAL_TAG = {
    [1]="L1R1", [2]="L1R2", [3]="L1R3", [4]="L1R4",
    [5]="L2-trans", [6]="L2R1", [7]="L2R2", [8]="L2R3", [9]="L2R4",
    [10]="L3-trans", [11]="L3R1", [12]="L3R2", [13]="L3R3", [14]="L3R4",
    [15]="L4-trans", [16]="L4R1", [17]="L4R2", [18]="L4R3", [19]="L4R4",
}
-- Skip transition rounds (their HUD shows e.g. "LEVEL 4" zoom, not gameplay)
local IS_TRANSITION = {[5]=true, [10]=true, [15]=true}
local MAX_ROUND = 19

local frame, fields, mem = 0, {}, nil
local PHASE = "BOOT"
local round_num = 0
local last_ram = -1
local hop1_at, hop1_rel_at, hop2_at, hop2_rel_at, hop_snap_at = -1,-1,-1,-1,-1
local adv_at, adv_rel_at = -1, -1
local snap_idx = 0
local done = false

local function set(name, on) if fields[name] then fields[name]:set_value(on and 1 or 0) end end

local function snap_record(label)
    snap_idx = snap_idx + 1
    manager.machine.video:snapshot()
    local tag = VISUAL_TAG[round_num] or "?"
    if snaplog then
        snaplog:write(string.format("%04d round_num=%d %s %s frame=%d\n",
            snap_idx-1, round_num, tag, label, frame))
        snaplog:flush()
    end
    log(string.format("[snap] idx=%04d round=%d %s %s frame=%d\n",
        snap_idx-1, round_num, tag, label, frame))
end

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for _, port in pairs(manager.machine.ioport.ports) do
            for name, fld in pairs(port.fields) do fields[name] = fld end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if fields[CHEAT] then
            fields[CHEAT]:set_value(1)
            log("[INFO] cheat ON (Demo Mode + Unlim Lives + Start=Adv)\n")
        else
            log("[ERR] cheat field not found!\n")
        end
    end

    -- Boot inputs (explicit conditional-set so Start releases properly)
    set("Coin 1",         frame >= 500 and frame < 560)
    if PHASE == "BOOT" or PHASE == "WAIT_RAM" or PHASE == "ADVANCE" then
        -- Start press is managed below for ADVANCE; otherwise just boot window
        if PHASE == "BOOT" or PHASE == "WAIT_RAM" then
            set("1 Player Start", frame >= 700 and frame < 760)
        end
    end

    -- Default joystick low (HOP phase overrides)
    if PHASE ~= "HOP" then
        set("P1 Right (Down-Right)", false)
        set("P1 Left (Up-Left)", false)
    end

    if done then return end

    if PHASE == "BOOT" then
        if frame >= 1100 then PHASE = "WAIT_RAM"; log("[INFO] WAIT_RAM\n") end
        return
    end

    local cur_ram = mem and mem:read_u8(0x081) or 0

    if PHASE == "WAIT_RAM" then
        if cur_ram >= 0x04 and cur_ram ~= last_ram then
            round_num = round_num + 1
            last_ram = cur_ram
            log(string.format("[round %d] %s ram=0x%02X frame=%d\n",
                round_num, VISUAL_TAG[round_num] or "?", cur_ram, frame))

            if round_num > MAX_ROUND then
                log("[done]\n")
                done = true
                if logfile then logfile:close() end
                if snaplog then snaplog:close() end
                manager.machine:exit()
                return
            end

            -- Skip transition screens (no usable cube state to capture)
            if IS_TRANSITION[round_num] then
                log(string.format("[skip] %s transition\n", VISUAL_TAG[round_num]))
                PHASE = "ADVANCE"
                adv_at = frame + ADVANCE_DELAY
                adv_rel_at = adv_at + ADVANCE_HOLD
                return
            end

            -- DON'T snap state0 at ram-change — schedule it to fire DURING
            -- the HOP phase a few frames later, so we don't disrupt ROM
            -- transition timing. State0 fires at frame X+5 (still pristine,
            -- before any hop input).
            PHASE = "HOP"
            hop1_at = frame + HOP_DELAY
            hop1_rel_at = hop1_at + HOP_HOLD
            hop2_at = hop1_rel_at + INTER_HOP
            hop2_rel_at = hop2_at + HOP_HOLD
            hop_snap_at = hop2_rel_at + POST_HOP_WAIT
        end
        return
    end

    if PHASE == "HOP" then
        -- Fire state0 a few frames into HOP (before any input goes), giving
        -- ROM time to settle past the ram-change instant
        if frame == hop1_at - HOP_DELAY + 5 then
            snap_record("state0")
        end
        set("P1 Right (Down-Right)", frame >= hop1_at and frame < hop1_rel_at)
        set("P1 Left (Up-Left)",     frame >= hop2_at and frame < hop2_rel_at)
        if frame == hop_snap_at then
            snap_record("state1")
            PHASE = "ADVANCE"
            adv_at = frame + ADVANCE_DELAY
            adv_rel_at = adv_at + ADVANCE_HOLD
        end
        return
    end

    if PHASE == "ADVANCE" then
        set("1 Player Start", frame >= adv_at and frame < adv_rel_at)
        if frame >= adv_rel_at then
            PHASE = "WAIT_RAM"
        end
        return
    end
end)
