// Adapter for the existing cell-stepped solo prototype. It does not implement the movement plan.
(() => {
  const held = new Map();
  const directions = {ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right'};
  let timer = null, paused = false;
  const visible = id => !document.querySelector(id).classList.contains('hidden');
  const playing = () => visible('#play-screen');
  function stop() {
    clearInterval(timer); timer = null; held.clear();
    document.querySelectorAll('[data-dir]').forEach(b => b.dispatchEvent(new PointerEvent('pointercancel')));
  }
  function move() {
    if (!playing() || paused || !held.size) return;
    const key = [...held.keys()].at(-1), button = document.querySelector(`[data-dir="${directions[key]}"]`);
    button.dispatchEvent(new PointerEvent('pointerdown'));
    button.dispatchEvent(new PointerEvent('pointerup'));
  }
  function pause() { if (playing()) { stop(); document.querySelector('#pause').click(); paused = !paused; } }
  window.bombermanTvSuspend = () => { stop(); if (playing() && !paused) pause(); };
  document.addEventListener('keydown', event => {
    if (!(event.key in directions) && event.key !== 'Enter' && event.key !== 'Escape') return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (event.repeat) return;
    if (event.key === 'Escape') { pause(); return; }
    if (event.key === 'Enter') {
      if (visible('#start-screen')) { stop(); paused = false; document.querySelector('#play').click(); }
      else if (visible('#end-screen')) { stop(); paused = false; document.querySelector('#restart').click(); }
      else if (paused) pause();
      else document.querySelector('#drop').dispatchEvent(new PointerEvent('pointerdown'));
      return;
    }
    if (visible('#start-screen')) {
      const cards = [...document.querySelectorAll('[data-cat]')];
      const current = cards.findIndex(b => b.classList.contains('selected'));
      const offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : event.key === 'ArrowDown' ? 10 : -10;
      cards[(current + offset + cards.length) % cards.length].click();
      return;
    }
    if (playing() && !paused) { held.delete(event.key); held.set(event.key, true); move(); if (!timer) timer = setInterval(move, 120); }
  }, true);
  document.addEventListener('keyup', event => {
    if (!(event.key in directions)) return;
    event.preventDefault(); event.stopImmediatePropagation(); held.delete(event.key);
    if (!held.size) { clearInterval(timer); timer = null; }
  }, true);
  window.addEventListener('blur', window.bombermanTvSuspend);
  document.addEventListener('visibilitychange', () => { if (document.hidden) window.bombermanTvSuspend(); }, true);
  document.querySelector('#pause').style.display = 'none';
  document.querySelector('.eyebrow').textContent = 'SOLO · TV REMOTE';
  document.querySelector('.fine').textContent = 'Arrows: choose cat · OK: play · In game: arrows move, OK drops bomb, Back pauses';
  document.querySelector('#firstrun').innerHTML = '<b>Arrows move · OK drops a bomb · Back pauses</b> — Flames hurt you too.';
  console.log('BM_TV_READY');
})();
