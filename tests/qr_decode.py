"""A small QR Code reader for tests: module matrix in, text out (byte mode, versions 1 to 9, no error correction).

Written from ISO/IEC 18004 so the phone controller's QR code (engine/vendor/qrcodegen, via
wfsource/source/hal/phonepad/phonepad_overlay.cc) can be checked by reading it back, without a new dependency.
It reads the format bits (and checks their BCH code), removes the mask, walks the codeword zigzag around the
function patterns, de-interleaves the blocks and parses a byte-mode segment. It does not correct errors: a test
input is either a perfect code or a failure, which is what a test wants. tests/test_phone_qr.py proves the reader
itself on codes made by segno, an independent encoder.
"""

from __future__ import annotations

# ISO/IEC 18004 Table 9, versions 1..9: (ECC codewords per block, number of blocks) per level.
ECC_PER_BLOCK = {
    "L": [7, 10, 15, 20, 26, 18, 20, 24, 30],
    "M": [10, 16, 26, 18, 24, 16, 18, 22, 22],
    "Q": [13, 22, 18, 26, 18, 24, 18, 22, 20],
    "H": [17, 28, 22, 16, 22, 28, 26, 26, 24],
}
NUM_BLOCKS = {
    "L": [1, 1, 1, 1, 1, 2, 2, 2, 2],
    "M": [1, 1, 1, 2, 2, 4, 4, 4, 5],
    "Q": [1, 1, 2, 2, 4, 4, 6, 6, 8],
    "H": [1, 1, 2, 4, 4, 4, 5, 6, 8],
}
LEVEL_BITS = {1: "L", 0: "M", 3: "Q", 2: "H"}
MASKS = [
    lambda x, y: (x + y) % 2 == 0,
    lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
]


class QrError(ValueError):
    pass


def alignment_positions(ver: int) -> list[int]:
    if ver == 1:
        return []
    n = ver // 7 + 2
    step = (ver * 8 + n * 3 + 5) // (n * 4 - 4) * 2
    pos = [6] + [0] * (n - 1)
    p = ver * 4 + 10
    for i in range(n - 1, 0, -1):
        pos[i] = p
        p -= step
    return pos


def function_modules(size: int, ver: int) -> list[list[bool]]:
    f = [[False] * size for _ in range(size)]

    def box(x0, y0, w, h):
        for y in range(max(0, y0), min(size, y0 + h)):
            for x in range(max(0, x0), min(size, x0 + w)):
                f[y][x] = True

    for i in range(size):                        # timing patterns
        f[6][i] = f[i][6] = True
    box(0, 0, 9, 9)                              # finders, separators and format bits
    box(size - 8, 0, 8, 9)
    box(0, size - 8, 9, 8)
    al = alignment_positions(ver)
    last = len(al) - 1
    for i, ax in enumerate(al):
        for j, ay in enumerate(al):
            if (i, j) in ((0, 0), (0, last), (last, 0)):
                continue
            box(ax - 2, ay - 2, 5, 5)
    if ver >= 7:
        box(size - 11, 0, 3, 6)
        box(0, size - 11, 6, 3)
    return f


def format_info(m: list[list[int]]) -> tuple[str, int]:
    """(error-correction level, mask) from the copy of the format bits beside the top-left finder."""
    size = len(m)
    bits = 0
    coords = [(8, i) for i in range(6)] + [(8, 7), (8, 8), (7, 8)] + [(14 - i, 8) for i in range(9, 15)]
    for i, (x, y) in enumerate(coords):          # (x, y): bit i, as the standard places it
        bits |= (m[y][x] & 1) << i
    bits ^= 0x5412
    data = bits >> 10
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    if ((data << 10) | (rem & 0x3FF)) != bits:
        raise QrError("format bits fail their BCH check")
    assert size >= 21
    return LEVEL_BITS[data >> 3], data & 7


def raw_data_modules(ver: int) -> int:
    r = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2
        r -= (25 * n - 10) * n - 55
        if ver >= 7:
            r -= 36
    return r


def data_modules(size: int) -> list[tuple[int, int]]:
    """(x, y) of every data and error-correction module, in the order their bits are read (the zigzag)."""
    ver = (size - 17) // 4
    func = function_modules(size, ver)
    out = []
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                upward = ((right + 1) & 2) == 0
                y = size - 1 - vert if upward else vert
                if not func[y][x]:
                    out.append((x, y))
        right -= 2
    return out


def block_layout(size: int, level: str) -> list[tuple[int, int, int]]:
    """For each codeword in reading order: (block, index in that block, codewords in that block's ECC)."""
    ver = (size - 17) // 4
    total = raw_data_modules(ver) // 8
    ecc, nblocks = ECC_PER_BLOCK[level][ver - 1], NUM_BLOCKS[level][ver - 1]
    short_len = total // nblocks
    n_short = nblocks - total % nblocks
    data_len = [short_len - ecc + (0 if b < n_short else 1) for b in range(nblocks)]
    order = []
    for i in range(max(data_len)):
        for b in range(nblocks):
            if i < data_len[b]:
                order.append((b, i, ecc))
    for i in range(ecc):
        for b in range(nblocks):
            order.append((b, data_len[b] + i, ecc))
    return order


def codewords_per_block_touched(size: int, level: str, modules) -> list[tuple[int, int]]:
    """For a set of (x, y) modules that may be wrong: per block, (codewords touched, codewords it can correct)."""
    where = {xy: i // 8 for i, xy in enumerate(data_modules(size)[:8 * len(block_layout(size, level))])}
    layout = block_layout(size, level)
    nblocks = max(b for b, _, _ in layout) + 1
    touched = [set() for _ in range(nblocks)]
    for xy in modules:
        if xy in where:
            b, i, _ = layout[where[xy]]
            touched[b].add(i)
    ecc = layout[0][2]
    return [(len(t), ecc // 2) for t in touched]


def codeword_blocks(m: list[list[int]]):
    """(level, mask, data blocks, error-correction blocks), de-interleaved, from a module matrix."""
    size = len(m)
    if size < 21 or (size - 17) % 4 or any(len(row) != size for row in m):
        raise QrError(f"not a QR matrix: {size} rows")
    ver = (size - 17) // 4
    if ver > 9:
        raise QrError("versions above 9 are not supported here")
    level, mask = format_info(m)
    func = function_modules(size, ver)

    bits = [(m[y][x] & 1) ^ (1 if MASKS[mask](x, y) else 0) for x, y in data_modules(size)]
    total = raw_data_modules(ver) // 8
    codewords = iter([int("".join(map(str, bits[i * 8:i * 8 + 8])), 2) for i in range(total)])

    ecc, nblocks = ECC_PER_BLOCK[level][ver - 1], NUM_BLOCKS[level][ver - 1]
    short_len = total // nblocks
    n_short = nblocks - total % nblocks
    data_len = [short_len - ecc + (0 if b < n_short else 1) for b in range(nblocks)]
    data: list[list[int]] = [[] for _ in range(nblocks)]
    for i in range(max(data_len)):
        for b in range(nblocks):
            if i < data_len[b]:
                data[b].append(next(codewords))
    eccs: list[list[int]] = [[] for _ in range(nblocks)]
    for _ in range(ecc):
        for b in range(nblocks):
            eccs[b].append(next(codewords))
    return level, mask, data, eccs


def decode(m: list[list[int]], correct: bool = False) -> str:
    """The text. With correct=True, each block is first repaired with Reed-Solomon (up to ECC/2 wrong
    codewords per block, as a phone's reader does); without it, any damage makes the text wrong or raises."""
    ver = (len(m) - 17) // 4
    _, _, blocks, eccs = codeword_blocks(m)
    if correct:
        blocks = [rs_correct(d + e, len(e))[:len(d)] for d, e in zip(blocks, eccs)]
    data = [c for b in blocks for c in b]
    stream = "".join(f"{c:08b}" for c in data)
    if stream[:4] != "0100":
        raise QrError(f"first segment is not byte mode: mode bits {stream[:4]}")
    count_bits = 8 if ver <= 9 else 16
    n = int(stream[4:4 + count_bits], 2)
    start = 4 + count_bits
    payload = bytes(int(stream[start + 8 * i:start + 8 * i + 8], 2) for i in range(n))
    return payload.decode("utf-8")


# ---- Reed-Solomon over GF(256) with the QR polynomial 0x11D, to check a code's error-correction bytes ----

def gf_mul(x: int, y: int) -> int:
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def rs_remainder(data: list[int], degree: int) -> list[int]:
    gen = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            gen[j] = gf_mul(gen[j], root)
            if j + 1 < degree:
                gen[j] ^= gen[j + 1]
        root = gf_mul(root, 2)
    rem = [0] * degree
    for b in data:
        factor = b ^ rem.pop(0)
        rem.append(0)
        for i in range(degree):
            rem[i] ^= gf_mul(gen[i], factor)
    return rem


def ecc_ok(m: list[list[int]]) -> bool:
    """True when every block's error-correction bytes are the Reed-Solomon remainder of its data."""
    _, _, data, eccs = codeword_blocks(m)
    return all(rs_remainder(d, len(e)) == e for d, e in zip(data, eccs))


# ---- Reed-Solomon error correction (Berlekamp-Massey, Chien search, Forney), first consecutive root alpha^0 ----

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _div(a, b):
    return 0 if a == 0 else _EXP[(_LOG[a] + 255 - _LOG[b]) % 255]


def _pow(a, n):
    return _EXP[(_LOG[a] * n) % 255]


def _inv(a):
    return _EXP[255 - _LOG[a]]


def _p_scale(p, x):
    return [_mul(c, x) for c in p]


def _p_add(p, q):
    r = [0] * max(len(p), len(q))
    for i, c in enumerate(p):
        r[i + len(r) - len(p)] = c
    for i, c in enumerate(q):
        r[i + len(r) - len(q)] ^= c
    return r


def _p_mul(p, q):
    r = [0] * (len(p) + len(q) - 1)
    for j, b in enumerate(q):
        for i, a in enumerate(p):
            r[i + j] ^= _mul(a, b)
    return r


def _p_eval(p, x):
    y = p[0]
    for c in p[1:]:
        y = _mul(y, x) ^ c
    return y


def _p_divmod(dividend, divisor):
    out = list(dividend)
    for i in range(len(dividend) - (len(divisor) - 1)):
        coef = out[i]
        if coef:
            for j in range(1, len(divisor)):
                if divisor[j]:
                    out[i + j] ^= _mul(divisor[j], coef)
    sep = -(len(divisor) - 1)
    return out[:sep], out[sep:]


def rs_correct(msg: list[int], nsym: int) -> list[int]:
    """Correct up to nsym // 2 wrong codewords in msg (data + ECC, highest degree first); QrError beyond that."""
    synd = [0] + [_p_eval(msg, _pow(2, i)) for i in range(nsym)]
    if max(synd) == 0:
        return list(msg)
    err_loc, old_loc = [1], [1]
    for i in range(nsym):
        k = i + 1
        delta = synd[k]
        for j in range(1, len(err_loc)):
            delta ^= _mul(err_loc[-(j + 1)], synd[k - j])
        old_loc = old_loc + [0]
        if delta:
            if len(old_loc) > len(err_loc):
                new_loc = _p_scale(old_loc, delta)
                old_loc = _p_scale(err_loc, _inv(delta))
                err_loc = new_loc
            err_loc = _p_add(err_loc, _p_scale(old_loc, delta))
    while err_loc and err_loc[0] == 0:
        err_loc = err_loc[1:]
    errs = len(err_loc) - 1
    if errs * 2 > nsym:
        raise QrError("too many errors to correct")
    rev = err_loc[::-1]
    err_pos = [len(msg) - 1 - i for i in range(len(msg)) if _p_eval(rev, _pow(2, i)) == 0]
    if len(err_pos) != errs:
        raise QrError("too many errors to correct (Chien search)")
    coef_pos = [len(msg) - 1 - p for p in err_pos]
    e_loc = [1]
    for i in coef_pos:
        e_loc = _p_mul(e_loc, _p_add([1], [_pow(2, i), 0]))
    _, rem = _p_divmod(_p_mul(synd[::-1], e_loc), [1] + [0] * len(e_loc))
    err_eval = rem[::-1]
    X = [_pow(2, -(255 - p)) for p in coef_pos]
    E = [0] * len(msg)
    for i, Xi in enumerate(X):
        Xi_inv = _inv(Xi)
        prime = 1
        for j, Xj in enumerate(X):
            if j != i:
                prime = _mul(prime, 1 ^ _mul(Xi_inv, Xj))
        y = _mul(Xi, _p_eval(err_eval[::-1], Xi_inv))
        if prime == 0:
            raise QrError("could not correct (Forney)")
        E[err_pos[i]] = _div(y, prime)
    fixed = _p_add(msg, E)
    if max(_p_eval(fixed, _pow(2, i)) for i in range(nsym)) != 0:
        raise QrError("could not correct (residual syndrome)")
    return fixed
