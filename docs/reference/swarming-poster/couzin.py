"""couzin.py: a numpy implementation of the Couzin et al. (2002) zone model of collective motion, used for the swarming poster and as the
reference the Forth implementation (wflevels/aquarium/school.fth) is tested against.

Rules (Couzin, Krause, James, Ruxton & Franks 2002, J. Theor. Biol. 218:1-11, eqns 1-3), per individual i with unit heading v_i:
  - neighbours are seen unless they are in a blind volume behind (field of perception alpha, 270 deg in the paper's Fig. 3);
  - repulsion (highest priority): if anyone is within r_r, d = -sum(unit vectors to them), normalised;
  - otherwise orientation d_o = normalised sum of the headings of those in the orientation zone [r_r, r_r+dro) and attraction
    d_a = normalised sum of the unit vectors toward those in the attraction zone [r_r+dro, r_r+dro+dra);
    d = d_o if only orientation neighbours, d_a if only attraction neighbours, (d_o + d_a)/2 if both;
  - no neighbours (or a zero vector): keep the heading;
  - error: the direction is rotated by a random angle (sigma, rad);
  - turning: at most theta*tau toward the desired direction; constant speed s; time step tau.
Metrics (eqns 4, 5): p_group = |mean v_i|; m_group = |mean(r_ic x v_i)| with r_ic the unit vector from the group centre to i.

Ours, NOT from the paper (the swarming poster labels them so): an optional LEADER (index 0) whose heading is given from outside (the player's fish):
followers count it with weight w_leader in the orientation and attraction sums, and it never reacts.
"""
import numpy as np

PAPER = dict(N=100, rr=1.0, alpha=270.0, theta=40.0, s=3.0, sigma=0.05, tau=0.1)     # the paper's Fig. 3 values (verified from the PDF)


def unit(a, eps=1e-12):
    n = np.linalg.norm(a, axis=-1, keepdims=True)
    return a / np.maximum(n, eps), n[..., 0]


def rotate_toward(v, d, max_angle):
    """Rotate unit v toward unit d by at most max_angle (rad), in the plane of both."""
    cosang = np.clip((v * d).sum(-1), -1.0, 1.0)
    ang = np.arccos(cosang)
    perp = d - cosang[..., None] * v
    pu, pn = unit(perp)
    flip = pn < 1e-9                                           # (anti)parallel: any perpendicular will do
    alt = np.cross(v, np.array([0.0, 0.0, 1.0])) + 1e-9
    alt, _ = unit(alt)
    pu = np.where(flip[..., None], alt, pu)
    step = np.minimum(ang, max_angle)
    out = np.cos(step)[..., None] * v + np.sin(step)[..., None] * pu
    out = np.where((ang <= max_angle)[..., None], d, out)
    return unit(out)[0]


def step(pos, vel, dro, dra, rng, p=PAPER, leader=None, w_leader=1.0, dt_noise=True):
    N = len(pos)
    rr, alpha, s, tau = p["rr"], p["alpha"], p["s"], p["tau"]
    r = pos[None, :, :] - pos[:, None, :]                      # r[i, j] = c_j - c_i
    rhat, d = unit(r)
    np.fill_diagonal(d, np.inf)
    cosang = (vel[:, None, :] * rhat).sum(-1)
    seen = cosang >= np.cos(np.radians(alpha / 2.0))           # not in the blind volume
    zr = seen & (d < rr)
    zo = seen & (d >= rr) & (d < rr + dro)
    za = seen & (d >= rr + dro) & (d < rr + dro + dra)
    if leader is not None:                                     # a leader is never repelled by the followers, and is not a follower
        zr[leader, :] = zo[leader, :] = za[leader, :] = False
    w = np.ones(N)
    if leader is not None:
        w[leader] = w_leader
    dr = -(rhat * zr[..., None]).sum(1)
    do = (vel[None, :, :] * (zo * w[None, :])[..., None]).sum(1)
    da = (rhat * (za * w[None, :])[..., None]).sum(1)
    nr, no, na = zr.sum(1), zo.sum(1), za.sum(1)
    dru, _ = unit(dr); dou, _ = unit(do); dau, _ = unit(da)
    des = np.where((no > 0)[:, None] & (na > 0)[:, None], 0.5 * (dou + dau),
                   np.where((no > 0)[:, None], dou, np.where((na > 0)[:, None], dau, vel)))
    des = np.where((nr > 0)[:, None], dru, des)
    des, n = unit(des)
    des = np.where((n < 1e-9)[:, None], vel, des)
    if dt_noise and p["sigma"] > 0:                            # a random rotation of the direction (a small Gaussian perturbation, renormalised)
        des, _ = unit(des + rng.normal(0.0, p["sigma"], des.shape))
    new = rotate_toward(vel, des, np.radians(p["theta"]) * tau)
    if leader is not None:
        new[leader] = vel[leader]
    pos = pos + new * s * tau
    return pos, new


def metrics(pos, vel):
    pg = np.linalg.norm(vel.mean(0))
    c = pos.mean(0)
    rc, _ = unit(pos - c)
    mg = np.linalg.norm(np.cross(rc, vel).mean(0))
    return pg, mg


def init(N, rng, radius=6.0):
    v, _ = unit(rng.normal(size=(N, 3)))
    x, _ = unit(rng.normal(size=(N, 3)))
    pos = x * radius * rng.random((N, 1)) ** (1 / 3)
    return pos, v


def fragmented(pos, reach):
    N = len(pos)
    d = np.linalg.norm(pos[:, None] - pos[None], axis=-1)
    seen, stack = {0}, [0]
    while stack:
        i = stack.pop()
        for j in np.flatnonzero(d[i] < reach):
            if j not in seen:
                seen.add(int(j)); stack.append(int(j))
    return len(seen) < N


def run(dro, dra, steps=1200, seed=1, N=None, p=PAPER, pos=None, vel=None, tail=200):
    """Simulate and return (pos, vel, mean p_group, mean m_group over the last `tail` steps, fragmented?)."""
    rng = np.random.default_rng(seed)
    n = N or p["N"]
    if pos is None:
        pos, vel = init(n, rng)
    ps, ms = [], []
    for t in range(steps):
        pos, vel = step(pos, vel, dro, dra, rng, p)
        if t >= steps - tail:
            a, b = metrics(pos, vel); ps.append(a); ms.append(b)
    return pos, vel, float(np.mean(ps)), float(np.mean(ms)), fragmented(pos, p["rr"] + dro + dra)
