-- Capture state-0 + post-hop screenshots for L1R1–L4R4.
-- Uses DIP Start=Adv cheat to advance rounds, but triggers each state-0 snap
-- IMMEDIATELY when RAM 0x081 (round counter) changes — so the snap captures the
-- freshly reset cubes before Demo AI has time to hop on any of them.

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/round_shots.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local frame, fields, mem = 0, {}, nil
local round_num = 0
local MAX_ROUNDS = 22   -- 16 visual rounds + 3 transitions + buffer for L4R4 hop and reattempts

local COIN_FRAME    = 500
local START_FRAME   = 700
local GAME_READY    = 1100

-- Per-round cycle (from ram-change detection).
-- We do TWO hops: Down-Right to (1,1), then Up-Left back to apex.
-- After the round-trip, Q*bert is at apex but cube (1,1) has been visited once
-- and cube apex has been visited once. Sampling apex (120,56) and (1,1) (134,82)
-- both give us the post-1-visit color (state 1 in 2-step rounds, state 2 in
-- 1-step). Q*bert sprite is on apex, not on (1,1), so (1,1) sample is clean.
local HOP_DELAY     = 30  -- frames after state-0 snap before hop1 begins
local HOP_HOLD      = 12  -- joystick hold duration per hop
local INTER_HOP     = 35  -- frames between hop1 release and hop2 start
local POST_HOP_WAIT = 30  -- frames after hop2 release until post-hop snap
local ADVANCE_DELAY = 5
local ADVANCE_HOLD  = 30

local PHASE        = "BOOT"
local last_ram     = -1
local hop1_at      = -1
local hop1_rel_at  = -1
local hop2_at      = -1
local hop2_rel_at  = -1
local hop_snap_at  = -1
local adv_at       = -1
local adv_rel_at   = -1
local done         = false

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for _, port in pairs(manager.machine.ioport.ports) do
            for name, field in pairs(port.fields) do fields[name] = field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if fields["Demo Mode (Unlim Lives, Start=Adv (Cheat)"] then
            fields["Demo Mode (Unlim Lives, Start=Adv (Cheat)"]:set_value(1)
            log("[INFO] DIP Start=Adv enabled\n")
        end
        log(string.format("[INFO] MAX_ROUNDS=%d\n", MAX_ROUNDS))
    end

    -- Boot-window coin + start
    if fields["Coin 1"] then
        fields["Coin 1"]:set_value(frame >= COIN_FRAME and frame < COIN_FRAME + 60 and 1 or 0)
    end
    if fields["1 Player Start"] then
        local boot_press = frame >= START_FRAME and frame < START_FRAME + 60
        fields["1 Player Start"]:set_value(boot_press and 1 or 0)
    end

    if done then return end

    -- Default joystick to 0 each frame; HOP phase will override
    if fields["P1 Right (Down-Right)"] then
        fields["P1 Right (Down-Right)"]:set_value(0)
    end
    if fields["P1 Left (Up-Left)"] then
        fields["P1 Left (Up-Left)"]:set_value(0)
    end

    if PHASE == "BOOT" then
        if frame >= GAME_READY then PHASE = "WAIT_RAM" end
        return
    end

    local cur_ram = mem and mem:read_u8(0x081) or 0

    if PHASE == "WAIT_RAM" then
        -- Snap state-0 the moment ram_0x081 reaches a new round value
        if cur_ram >= 0x04 and cur_ram ~= last_ram then
            round_num = round_num + 1
            manager.machine.video:snapshot()
            log(string.format("[s0]  round_num=%d frame=%d ram=0x%02X\n",
                round_num, frame, cur_ram))
            last_ram = cur_ram
            if round_num >= MAX_ROUNDS then
                log("[done]\n")
                if f then f:close() end
                done = true
                manager.machine:exit()
                return
            end
            PHASE        = "HOP"
            hop1_at      = frame + HOP_DELAY
            hop1_rel_at  = hop1_at + HOP_HOLD
            hop2_at      = hop1_rel_at + INTER_HOP
            hop2_rel_at  = hop2_at + HOP_HOLD
            hop_snap_at  = hop2_rel_at + POST_HOP_WAIT
        end
        return
    end

    if PHASE == "HOP" then
        if fields["P1 Right (Down-Right)"] then
            local h1 = frame >= hop1_at and frame < hop1_rel_at
            fields["P1 Right (Down-Right)"]:set_value(h1 and 1 or 0)
        end
        if fields["P1 Left (Up-Left)"] then
            local h2 = frame >= hop2_at and frame < hop2_rel_at
            fields["P1 Left (Up-Left)"]:set_value(h2 and 1 or 0)
        end
        if frame == hop_snap_at then
            manager.machine.video:snapshot()
            log(string.format("[hop] round_num=%d frame=%d ram=0x%02X\n",
                round_num, frame, cur_ram))
            PHASE      = "ADVANCE"
            adv_at     = frame + ADVANCE_DELAY
            adv_rel_at = adv_at + ADVANCE_HOLD
        end
        return
    end

    if PHASE == "ADVANCE" then
        if fields["1 Player Start"] then
            local active = frame >= adv_at and frame < adv_rel_at
            -- Override boot-window default with our advance press
            if active then fields["1 Player Start"]:set_value(1) end
        end
        if frame >= adv_rel_at then
            PHASE = "WAIT_RAM"
            -- Now poll ram each frame; on next change, snap next state-0
        end
        return
    end
end)
