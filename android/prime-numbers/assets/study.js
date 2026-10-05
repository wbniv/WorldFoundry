(function () {
  'use strict';
  function isPrime(n) {
    if (n < 2) return false;
    for (var d = 2; d * d <= n; d++) if (n % d === 0) return false;
    return true;
  }
  var state = { mode:'study', selected:1, focus:'grid', tab:0, panel:'intro', marked:{}, checked:false };
  var held = null, delay = null, repeat = null;
  var el = function (id) { return document.getElementById(id); };
  var cells = [];
  for (var n = 1; n <= 100; n++) {
    var cell = document.createElement('button');
    cell.type = 'button'; cell.className = 'number'; cell.dataset.number = String(n);
    cell.setAttribute('role','gridcell'); cell.textContent = n;
    el('grid').appendChild(cell); cells.push(cell);
    if (isPrime(n)) {
      var primeItem = document.createElement('span'); primeItem.textContent = n;
      primeItem.setAttribute('role','listitem'); el('prime-values').appendChild(primeItem);
    }
    cell.addEventListener('click', function () { stop(); state.selected = Number(this.dataset.number); state.focus = 'grid'; open(); });
  }
  function render() {
    var study = state.mode === 'study';
    document.body.dataset.mode = state.mode;
    el('study').classList.toggle('active',study); el('recall').classList.toggle('active',!study);
    el('study').setAttribute('aria-pressed',String(study)); el('recall').setAttribute('aria-pressed',String(!study));
    el('check').hidden = study;
    el('ok-hint').textContent = study ? 'Select mode' : 'Mark / Unmark';
    [el('study'),el('recall'),el('check')].forEach(function (node) { node.classList.remove('remote-focus'); node.tabIndex = -1; });
    cells.forEach(function (node, i) {
      var number = i + 1, revealed = study || state.checked, marked = Boolean(state.marked[number]);
      node.classList.toggle('prime',revealed && isPrime(number));
      node.classList.toggle('marked',!study && marked);
      node.classList.toggle('wrong',!study && state.checked && marked && !isPrime(number));
      node.classList.toggle('missed',!study && state.checked && !marked && isPrime(number));
      node.classList.toggle('selected',state.focus === 'grid' && number === state.selected);
      node.setAttribute('aria-label',String(number) + (revealed ? (isPrime(number) ? ', prime' : number === 1 ? ', neither prime nor composite' : ', composite') : marked ? ', marked' : ', unmarked'));
      node.setAttribute('aria-selected',String(number === state.selected));
      node.tabIndex = state.focus === 'grid' && number === state.selected ? 0 : -1;
    });
    el('legend-prime').hidden = !study; el('legend-other').hidden = !study;
    el('progress').textContent = study ? '25 primes · 100 numbers' : Object.keys(state.marked).length + ' marked';
    var showList = study && state.panel === 'intro';
    el('prime-list').hidden = !showList; el('details').hidden = showList;
    el('panel-hint').hidden = showList;
    el('review-missing').hidden = state.panel !== 'review'; el('review-wrong').hidden = state.panel !== 'review';
    if (state.panel === 'intro') {
      el('panel-label').textContent = 'RECALL';
      el('panel-title').textContent = 'Mark the primes.';
      el('panel-body').textContent = 'Press OK to mark or unmark a number. Choose Check when you’re ready.';
      el('panel-hint').textContent = 'No timer. Answers stay hidden until you check.';
    } else if (state.panel === 'review') {
      var result = score();
      el('panel-label').textContent = 'YOUR RESULTS';
      el('panel-title').textContent = result.correct + ' of 25 found.';
      el('panel-body').textContent = result.wrong.length === 0 && result.missing.length === 0 ? 'All 25 primes. Well remembered.' : result.wrong.length + ' incorrect marks · ' + result.missing.length + ' missed primes';
      el('review-missing').textContent = result.missing.length ? 'Missed: ' + result.missing.join(' · ') : 'No missed primes.';
      el('review-wrong').textContent = result.wrong.length ? 'Incorrect marks are shown in coral on the chart.' : 'No incorrect marks.';
      el('panel-hint').textContent = 'Move and press OK to change your marks. Back hides the results.';
    }
    var target;
    if (state.focus === 'tabs') target = el(['study','recall','check'][state.tab]);
    else target = cells[state.selected - 1];
    target.tabIndex = 0;
    if (state.focus !== 'grid') target.classList.add('remote-focus');
    target.focus({preventScroll:true});
    console.log('PRIME_STATE ' + JSON.stringify({mode:state.mode, selected:state.selected}));
  }
  function mode(next) {
    stop(); state.mode = next; state.tab = next === 'study' ? 0 : 1;
    state.marked = {}; state.checked = false; state.panel = 'intro'; state.focus = 'grid'; render();
    console.log('PRIME_MODE ' + next);
  }
  function open() {
    if (state.mode === 'recall') { toggleMark(); return; }
    console.log('PRIME_STUDY_REFERENCE');
  }
  function toggleMark() {
    if (state.marked[state.selected]) delete state.marked[state.selected];
    else state.marked[state.selected] = true;
    state.checked = false; state.panel = 'intro'; state.focus = 'grid'; render();
    console.log('PRIME_MARK ' + state.selected + ' ' + (state.marked[state.selected] ? 'on' : 'off'));
  }
  function score() {
    var result = {correct:0, missing:[], wrong:[]};
    for (var n = 1; n <= 100; n++) {
      if (isPrime(n)) { if (state.marked[n]) result.correct++; else result.missing.push(n); }
      else if (state.marked[n]) result.wrong.push(n);
    }
    return result;
  }
  function check() {
    stop(); state.checked = true; state.panel = 'review'; state.focus = 'grid'; render();
    var result = score();
    console.log('PRIME_CHECK ' + result.correct + ' correct ' + result.wrong.length + ' wrong ' + result.missing.length + ' missing');
  }
  function back() {
    stop();
    if (state.panel !== 'intro') { state.panel = 'intro'; state.checked = false; state.focus = 'grid'; render(); return true; }
    if (state.mode === 'recall') { mode('study'); return true; }
    if (state.focus === 'tabs') { state.focus = 'grid'; render(); return true; }
    return false;
  }
  function move(key) {
    if (state.focus === 'tabs') {
      if (key === 'ArrowLeft') state.tab = Math.max(0,state.tab - 1);
      if (key === 'ArrowRight') state.tab = Math.min(state.mode === 'recall' ? 2 : 1,state.tab + 1);
      if (key === 'ArrowDown') state.focus = 'grid';
    } else {
      var col = (state.selected - 1) % 10;
      if (key === 'ArrowLeft' && col > 0) state.selected--;
      if (key === 'ArrowRight' && col < 9) state.selected++;
      if (key === 'ArrowDown' && state.selected <= 90) state.selected += 10;
      if (key === 'ArrowUp') {
        if (state.selected > 10) state.selected -= 10;
        else { state.focus = 'tabs'; state.tab = state.mode === 'study' ? 0 : 1; }
      }
    }
    render(); console.log('PRIME_FOCUS ' + state.selected + ' ' + state.focus);
  }
  function stop() { held = null; clearTimeout(delay); clearInterval(repeat); delay = null; repeat = null; }
  function down(event) {
    var key = event.key;
    if (key.indexOf('Arrow') === 0) {
      event.preventDefault();
      if (event.repeat || held === key) return;
      stop(); held = key; move(key);
      delay = setTimeout(function () { repeat = setInterval(function () { move(key); },130); },350);
    } else if (key === 'Enter' || key === ' ') {
      event.preventDefault(); if (event.repeat) return; stop();
      if (state.focus === 'tabs') { if (state.tab === 2) check(); else mode(state.tab === 0 ? 'study' : 'recall'); }
      else open();
    } else if (key === 'Escape') { event.preventDefault(); if (!event.repeat) back(); }
  }
  document.addEventListener('keydown',down);
  document.addEventListener('keyup',function (event) { if (event.key === held) stop(); });
  window.addEventListener('blur',stop);
  document.addEventListener('visibilitychange',function () { if (document.hidden) stop(); });
  el('study').onclick = function () { mode('study'); }; el('recall').onclick = function () { mode('recall'); };
  el('check').onclick = check;
  window.primeTvSuspend = stop;
  window.primeTvBack = back;
  window.primeStudy = { isPrime:isPrime, snapshot:function () { return JSON.parse(JSON.stringify(state)); },
    restore:function (saved) {
      if (!saved || (saved.mode !== 'study' && saved.mode !== 'recall') || !Number.isInteger(saved.selected) || saved.selected < 1 || saved.selected > 100) return;
      stop(); state.mode = saved.mode; state.selected = saved.selected; state.tab = saved.mode === 'study' ? 0 : 1;
      state.panel = 'intro'; state.focus = 'grid'; state.marked = {}; state.checked = false; render();
    }
  };
  render(); console.log('PRIME_READY 100 numbers 25 primes');
}());
