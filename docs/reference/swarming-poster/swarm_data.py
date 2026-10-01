"""swarm_data.py: the data sheet behind the swarming poster. Every number the poster prints is one row here (quantity, value, unit, chip, sources).

Chips (the honest part), the same four as the clownfish poster:
  verified       the source's own page was opened and the number is on it
  unverified     widely cited, or from a summary, or measured here but not yet against anything independent
  ours           a game tunable or our own maths / our own measurement, not the literature
  other-species  measured in another species; a hint only
Rows that point at a measured file (sweep.json, tank.json, measured.json) read their value from it, so a re-run redraws the poster.

Plan: docs/plans/2026-10-01-swarming-poster.md.   Run `python3 swarm_data.py` to print the sheet; `-h` for usage.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DATE = "2026-10-01"
STATUS_TEXT = {"verified": "verified", "unverified": "unverified", "ours": "ours", "other-species": "other species"}

SOURCES = {
    "S1": dict(short="Couzin et al. 2002, J. Theor. Biol.", url="https://jmvidal.cse.sc.edu/library/couzin02a.pdf", opened=True,
               backs="zone model, states, metrics, Fig. 3"),
    "S2": dict(short="Couzin et al. 2005, Nature", url="https://www.nature.com/articles/nature03236", opened=False,
               backs="informed minority guides a group"),
    "S3": dict(short="Pitcher 1983, via Wikipedia", url="https://en.wikipedia.org/wiki/Shoaling_and_schooling", opened=False,
               backs="shoal to school: a continuum"),
    "S4": dict(short="Ocellaris clownfish (Florida Museum)", url="https://www.floridamuseum.ufl.edu/discover-fish/species-profiles/clown-anemonefish/", opened=False,
               backs="site-attached: not schooling fish"),
    "S5": dict(short="the aquarium level and this repository", url=None, opened=True,
               backs="tank, fish, zForth, our runs"),
}
GAME = "S5"


def load(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


def constants():
    """Tank and fish sizes in the level, read from the level's constants (WORLD_SCALE etc.)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("aqc", HERE.parents[2] / "wflevels/aquarium/aquarium_constants.py")
    c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
    return c


def paper_turn():
    """Distance a fish at the paper's s = 3 and θ = 40°/s travels while turning 90°, and its turning radius, in body lengths."""
    s, th = 3.0, 40.0
    return s * (90.0 / th), s / math.radians(th)


def game_turn(s=2.0, th=120.0):
    return s * (90.0 / th), s / math.radians(th)


def rows():
    m, t, sw = load("measured.json"), load("tank.json"), load("sweep.json")
    pd, pr = paper_turn(); gd, gr = game_turn()
    R = []
    add = lambda id, q, v, status, srcs: R.append(dict(id=id, quantity=q, value=v, status=status, sources=srcs))
    add("n", "Fish in Fig. 3", "N = 100", "verified", ["S1"])
    add("rr", "Repulsion zone r_r", "1 body length", "verified", ["S1"])
    add("alpha", "Field of perception α", "270° (blind 90° behind)", "verified", ["S1"])
    add("theta", "Turn rate θ", "40°/s", "verified", ["S1"])
    add("s", "Speed s", "3 BL/s", "verified", ["S1"])
    add("sigma", "Error σ", "0.05 rad", "verified", ["S1"])
    add("reps", "Replicates in the paper", "30 per cell", "verified", ["S1"])
    if sw:
        add("reps_us", "Replicates here", f"{sw['reps']} per cell, {sw['steps']} steps", "ours", [GAME])
    add("states", "Collective states", "swarm, torus, dynamic parallel, highly parallel", "verified", ["S1"])
    add("hyst", "Hysteresis (collective memory)", "reported by the paper", "verified", ["S1"])
    add("hyst_us", "Hysteresis in our sweep", "not reproduced (too coarse)", "ours", [GAME])
    add("lead", "Informed minority steers a group", "small fraction suffices", "unverified", ["S2"])
    add("cont", "Shoal to school", "a continuum", "unverified", ["S3"])
    add("clown", "Real ocellaris clownfish", "not schooling fish", "unverified", ["S4"])
    add("wl", "Leader weight w", "3 in the game; 1, 3, 6 tried in the tank runs; not tuned", "ours", [GAME])
    add("s_us", "Our speed and turn rate", "2 BL/s and 120°/s", "ours", [GAME])
    add("turn_paper", "A 90° turn at the paper’s s, θ", f"{pd:.2f} BL ahead, radius {pr:.1f} BL", "ours", [GAME])
    add("turn_us", "A 90° turn at ours", f"{gd:.2f} BL ahead, radius {gr:.2f} BL", "ours", [GAME])
    try:
        k = constants()
        add("tank", "Tank width", f"{k.TANK_W / k.FISH_LEN:.1f} BL", "ours", [GAME]) if hasattr(k, "TANK_W") else None
    except Exception:  # noqa: BLE001
        pass
    if m:
        add("bytes", "school.fth in the dictionary", f"{sum(w['bytes'] for w in m['words'])} B of {m['dictionary_size']}", "ours", [GAME])
        add("lines", "school.fth source", f"{m['code_lines']} code lines, {m['source_lines']} with comments", "ours", [GAME])
        add("err", "Forth vs numpy, one tick", f"position {m['error']['pos_max']:.0e}, heading {m['error']['head_max']:.0e}", "ours", [GAME])
        if m.get("engine"):
            e = m["engine"]
            add("eng_before", "Director script per tick, in the engine, as found", f"{e['before']['director_ms'][0]:.0f} to {e['before']['director_ms'][1]:.0f} ms, {e['before']['mailbox_us']} µs a mailbox call, {e['before']['fps']:.0f} fps", "ours", [GAME])
            add("eng_after", "The same after the engine fix", f"{e['after']['director_ms'][0]:.1f} ms, {e['after']['mailbox_us']} µs a mailbox call, {e['after']['fps']:.1f} fps", "ours", [GAME])
        if m.get("engine", {}).get("level"):
            lv = m["engine"]["level"]
            add("eng_level", "The aquarium level with ten followers, on the Chromecast", f"{lv['fps']:.1f} fps, p90 {lv['frame_p90_ms']:.1f} ms; Director {lv['director_ms']:.1f} ms a tick", "ours", [GAME])
        if m.get("device"):
            add("dev", "One tick, 11 fish, on the Chromecast HD", f"{m['device']['ms']:.1f} ms", "ours", [GAME])
    return R


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(__doc__); sys.exit(0)
    for r in rows():
        print(f"{r['id']:11s} {r['status']:13s} {r['quantity']:40s} {r['value']}")
