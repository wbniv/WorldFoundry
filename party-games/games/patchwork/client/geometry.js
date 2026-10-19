// Shared pure geometry: CommonJS on the server, side-effect ES module in browsers.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PDGeometry = api;
})(globalThis, () => {
  const key = ([x, y]) => `${x},${y}`;
  function normalize(cells) {
    if (!Array.isArray(cells) || !cells.length) throw new Error('Empty patch');
    const minX = Math.min(...cells.map(c => c[0])), minY = Math.min(...cells.map(c => c[1]));
    return cells.map(([x, y]) => [x - minX, y - minY]).sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  }
  function orient(cells, rotation = 0, flip = false) {
    let result = cells.map(([x, y]) => [flip ? -x : x, y]);
    for (let i = 0; i < ((rotation % 4) + 4) % 4; i++) result = result.map(([x, y]) => [-y, x]);
    return normalize(result);
  }
  function connected(cells) {
    if (!cells.length) return false;
    const remaining = new Set(cells.map(key)), pending = [cells[0]];
    remaining.delete(key(cells[0]));
    while (pending.length) {
      const [x, y] = pending.pop();
      for (const c of [[x-1,y],[x+1,y],[x,y-1],[x,y+1]]) if (remaining.delete(key(c))) pending.push(c);
    }
    return !remaining.size;
  }
  function cuts(cells) {
    const parts = [], seen = new Set();
    for (let axis = 0; axis < 2; axis++) for (let at = 1; at <= Math.max(...cells.map(c => c[axis])); at++) {
      const left = cells.filter(c => c[axis] < at), right = cells.filter(c => c[axis] >= at);
      if (!connected(left) || !connected(right)) continue;
      for (let side = 0; side < 2; side++) {
        const shape = normalize(side ? right : left), id = JSON.stringify(shape);
        if (!seen.has(id)) { seen.add(id); parts.push({axis, at, side, cells: shape}); }
      }
    }
    return parts;
  }
  function fit(board, cells, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) return false;
    const indices = cells.map(([a, b]) => (y+b)*9+x+a);
    return new Set(indices).size === cells.length && cells.every(([a,b]) => x+a>=0 && x+a<9 && y+b>=0 && y+b<9 && !board[(y+b)*9+x+a]);
  }
  function place(board, cells, x, y, marker) {
    if (!fit(board, cells, x, y)) throw new Error('Patch must fit on empty cells inside your quilt.');
    const next = board.slice();
    for (const [a,b] of cells) next[(y+b)*9+x+a] = marker;
    return next;
  }
  function firstFit(board, cells) {
    for (let flip = 0; flip < 2; flip++) for (let rotation = 0; rotation < 4; rotation++) {
      const shape = orient(cells, rotation, !!flip);
      for (let y=0;y<9;y++) for(let x=0;x<9;x++) if (fit(board,shape,x,y)) return {x,y,rotation,flip:!!flip};
    }
    return null;
  }
  return {normalize, orient, connected, cuts, fit, place, firstFit};
});
