#!/usr/bin/env python3
"""Carry a generator change's script delta onto a committed .lev, without re-exporting it.

    patch_lev_scripts.py BEFORE.lev AFTER.lev COMMITTED.lev OUT.lev

BEFORE.lev and AFTER.lev are two exports from the same pipeline, without and with the
generator change. For every object whose Script differs between them, the token-level
edit BEFORE -> AFTER is replayed onto the COMMITTED object whose script has the same first
(sigil) line (the importer renames some objects, so names cannot match them). That script
must have the same token count as BEFORE: they may differ only in numbers such as actor
indices. Inserted actor indices (the token before `write-actor-mailbox`) are mapped from
the export's object order to the committed object order by object name. Everything else in
COMMITTED.lev is copied byte for byte.

Used for docs/plans/2026-11-14-qbert-remote-hop.md, where the Blender pipeline at HEAD
cannot produce a loadable Q*bert level (see the plan's "Regeneration is blocked at HEAD").
"""
import difflib
import json
import re
import sys

SCRIPT_RE = re.compile(r'(\{ \'STR\' \{ \'NAME\' "Script" \} \{ \'STR\' )("(?:\\.|[^"\\])*")')
NAME_RE = re.compile(r'^\t\t\{ \'NAME\' "([^"]*)" \}$', re.M)


def objects(text):
    parts = text.split("{ 'OBJ'")
    return parts[0], parts[1:]


def name_of(block):
    return NAME_RE.search(block).group(1)


def script_of(block):
    m = SCRIPT_RE.search(block)
    return json.loads(m.group(2)) if m else None


def tokens(script):
    return re.split(r'(\s+)', script)   # keep whitespace so the result round-trips


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        return 0
    before, after, committed, out = sys.argv[1:5]
    _, b_objs = objects(open(before).read())
    _, a_objs = objects(open(after).read())
    head, c_objs = objects(open(committed).read())
    export_index = {name_of(o): i for i, o in enumerate(a_objs, start=1)}
    commit_index = {name_of(o): i for i, o in enumerate(c_objs, start=1)}
    export_name = {i: n for n, i in export_index.items()}
    b_by_name = {name_of(o): script_of(o) for o in b_objs}
    a_by_name = {name_of(o): script_of(o) for o in a_objs}
    changed = [n for n in a_by_name if a_by_name[n] != b_by_name.get(n)]
    for name in changed:
        bt, at = tokens(b_by_name[name]), tokens(a_by_name[name])
        # The importer renames some objects (Director -> director_9); match the
        # scripted object by its sigil line ("\\ wf qbert director MVP") instead.
        sigil = a_by_name[name].split('\n', 1)[0]
        ci = next(i for i, o in enumerate(c_objs) if (script_of(o) or '').split('\n', 1)[0] == sigil)
        ct = tokens(script_of(c_objs[ci]))
        assert len(bt) == len(ct), f'{name}: committed script does not align with the export ({len(ct)} vs {len(bt)} tokens)'
        result = []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, bt, at, autojunk=False).get_opcodes():
            if op == 'equal':
                result += ct[i1:i2]
                continue
            new = list(at[j1:j2])
            for k, tok in enumerate(new):
                nxt = next((t for t in new[k + 1:] if t.strip()), None)
                if nxt == 'write-actor-mailbox' and tok.isdigit():
                    new[k] = str(commit_index[export_name[int(tok)]])
            result += new
        patched = ''.join(result)
        block = c_objs[ci]
        m = SCRIPT_RE.search(block)
        c_objs[ci] = block[:m.start(2)] + json.dumps(patched, ensure_ascii=True) + block[m.end(2):]
        print(f'{name}: {len(patched) - len(script_of(block)):+d} chars')
    open(out, 'w').write(head + ''.join("{ 'OBJ'" + o for o in c_objs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
