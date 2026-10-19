"""Build a local gallery of physical TV frames and browser layout checks."""
from pathlib import Path
import html,json,os
root=Path(__file__).resolve().parents[4]
physical=root/'docs/diagnostics/patchwork-tv-J-2104f8e72e64/frames'
browser=root/'party-games/games/patchwork/test/evidence/tv-states-reviewed'
out=root/'docs/diagnostics/patchwork-tv-review';out.mkdir(exist_ok=True)
frames=json.loads((physical/'manifest.json').read_text())['frames']
checks=json.loads((browser/'report.json').read_text())['states']
assert all((physical/f['image']).exists() for f in frames)
assert all(not s['issues'] for s in checks)
def link(path):return html.escape(os.path.relpath(path,out))
def caption(s):
 phase=s['phase'];rnd=s['round'];turn=s['turn'];ready=s['ready'];cursor=int(s['ceremony'])
 if phase=='FINISHED':return 'Final standings' if cursor==36 else f'Final scoring · player {cursor//6+1} · step {cursor%6+1} of 6'
 if phase=='LOBBY':return 'Lobby · six long player names'
 if phase=='STARTING':return f'Starting patch · ready: {ready}'
 if phase=='SCORING':return f'Round {rnd} · finishing touches · ready: {ready}'
 if phase=='ROUND_RESULTS':return f'Round {rnd} · six-player results'
 return f'Round {rnd} · turn {turn} · ready: {ready}'
figures=[]
for source,folder,states in [('physical',physical,frames),('browser',browser,checks)]:
 for s in states:
  variant=source if source=='physical' else 'browser-'+s['skin']
  figures.append(f'<figure data-source="{variant}" data-phase="{s["phase"]}"><a href="{link(folder/s["image"])}" target="_blank"><img loading="lazy" src="{link(folder/s["image"])}" alt="{html.escape(caption(s))}"></a><figcaption>{html.escape(caption(s))}<small>{"Chromecast HD · recorded frame" if source=="physical" else "Browser · "+s["skin"]}</small></figcaption></figure>')
overview=root/'party-games/games/patchwork/test/evidence'
for skin in ['linen','night','paper']:
 path=overview/f'tv-autoplay-six-boards-{skin}.png'
 assert path.exists(),path
 figures.append(f'<figure data-source="browser-{skin}" data-phase="TURN_RESULTS"><a href="{link(path)}" target="_blank"><img loading="lazy" src="{link(path)}" alt="End of turn: all six player boards"></a><figcaption>End of turn · all six boards<small>Browser preview · {skin} · archived committed-board fixture</small></figcaption></figure>')
regular=root/'docs/diagnostics/patchwork-regular-turn-results-gallery'
two=regular/'tv-turn-results.png'
assert two.exists()
figures.append(f'<figure data-source="browser-linen" data-phase="TURN_RESULTS"><a href="{link(two)}" target="_blank"><img loading="lazy" src="{link(two)}" alt="Regular-game overview after round 1 turn 1"></a><figcaption>Round 1 · turn 1 · both players’ boards<small>Actual regular-game browser capture</small></figcaption></figure>')
for rnd in range(1,4):
 for turn in range(1,7):
  path=regular/f'tv-turn-results-{rnd}-{turn}.png'
  assert path.exists(),path
  figures.append(f'<figure data-source="browser-linen" data-phase="TURN_RESULTS"><a href="{link(path)}" target="_blank"><img loading="lazy" src="{link(path)}" alt="Regular game: round {rnd} turn {turn} committed quilts"></a><figcaption>Round {rnd} · turn {turn} · committed quilts<small>Actual regular-game browser capture · host-controlled Continue</small></figcaption></figure>')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quilt Night · TV state review</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f0e5;color:#233e43;font:16px/1.5 system-ui}main{max-width:1400px;margin:auto;padding:28px}h1{margin:0}p{max-width:1000px}a{color:#206a65}nav{position:sticky;top:0;z-index:1;background:#f5f0e5ed;border-block:1px solid #bdc7bd;padding:12px;display:flex;gap:20px;align-items:center;flex-wrap:wrap}select{font:inherit;padding:8px;border:1px solid #899b96;border-radius:7px;background:white;color:#233e43}.gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:20px}figure{margin:0;border:1px solid #bdc7bd;border-radius:10px;overflow:hidden;background:#fffdf8}img{width:100%;display:block}figcaption{padding:12px;font-weight:650}small{display:block;font-weight:400;color:#61736e}figure[hidden]{display:none}@media(max-width:800px){.gallery{grid-template-columns:1fr}}
</style><main><h1>Quilt Night · TV state review</h1><p>106 frames from an owned Chromecast HD recording: lobby, starting patches, all 18 turns, readiness changes, finishing touches, round results, every player's six scoring steps, and final standings. Click an image to open it at full resolution.</p><p>Browser checks replayed the same 106 public game states in all three skins at the TV's 960×540 CSS viewport: <strong>318 layouts, zero clipping/overlap failures.</strong> This review exercises six players with long names. The physical images use the linen skin; browser previews are labeled separately.</p><p><a href="../patchwork-tv-J-2104f8e72e64/capture.mp4">Full TV recording</a> · <a href="../patchwork-tv-J-2104f8e72e64/receipt.json">Coordinator receipt and verified cleanup</a> · <a href="../../../party-games/games/patchwork/test/evidence/tv-states-reviewed/report.json">Browser fit report</a></p><nav><label>Source <select id="source"><option value="physical">Physical Chromecast</option><option value="browser-linen">Browser · linen</option><option value="browser-night">Browser · night</option><option value="browser-paper">Browser · paper</option></select></label><label>State <select id="phase"><option value="all">All states</option><option>LOBBY</option><option>STARTING</option><option>PLACING</option><option>SCORING</option><option>ROUND_RESULTS</option><option>FINISHED</option></select></label><span id="count"></span></nav><div class="gallery">'''+''.join(figures)+'''</div></main><script>function filter(){let n=0;for(const f of document.querySelectorAll('figure')){f.hidden=f.dataset.source!==source.value||(phase.value!=='all'&&f.dataset.phase!==phase.value);if(!f.hidden)n++}document.querySelector('#count').textContent=n+' images'}const source=document.querySelector('#source'),phase=document.querySelector('#phase');source.onchange=phase.onchange=filter;filter();</script></html>'''
featured=f'''<section id="end-of-turn"><h2>End of turn · every player’s board</h2><p>All six quilt cards appear together on one screen. Regular play waits for the host to tap Continue on their phone; autoplay uses the same shared server phase and continues after four seconds. Both are implemented. All 18 regular-game turn captures are included below.</p><a href="{link(overview/'tv-autoplay-six-boards-linen.png')}" target="_blank"><img src="{link(overview/'tv-autoplay-six-boards-linen.png')}" alt="End-of-turn screen showing every player's quilt board"></a><small>Browser preview using six committed boards from the archived game. <a href="{link(overview/'tv-autoplay-six-boards-night.png')}" target="_blank">Night skin</a> · <a href="{link(overview/'tv-autoplay-six-boards-paper.png')}" target="_blank">Paper skin</a> · <a href="{link(two)}" target="_blank">Actual two-player regular-game capture</a></small></section>'''
page=page.replace('<nav>',featured+'<nav>',1).replace('<option>SCORING</option>','<option value="TURN_RESULTS">End-of-turn boards</option><option>SCORING</option>')
(out/'index.html').write_text(page)
print(out/'index.html')
