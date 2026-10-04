// Original development fixtures. Not a transcription of the physical deck.
// Replace via an independently verified inventory before claiming edition fidelity.
const G = require('./client/geometry');
function fixtures(count, sizeFor, prefix) {
  const cards = [];
  for (let seed = 1; seed <= count; seed++) {
    let n = seed * 731 + 19;
    const random = () => { n = (Math.imul(n, 1664525) + 1013904223) >>> 0; return n / 4294967296; };
    let cells = [[0, 0]];
    while (cells.length < sizeFor(seed)) {
      const [x,y] = cells[Math.floor(random() * cells.length)];
      const [dx,dy] = [[1,0],[-1,0],[0,1],[0,-1]][Math.floor(random()*4)];
      if (!cells.some(c => c[0] === x+dx && c[1] === y+dy)) cells.push([x+dx,y+dy]);
    }
    cards.push({id:`${prefix}${String(seed).padStart(2,'0')}`, cells:G.normalize(cells)});
  }
  return cards;
}
const patches = fixtures(30, seed => 3 + seed % 6, 'D');
const starts = fixtures(10, () => 7, 'S');
module.exports = {patches, starts, provenance:'Original development deck — physical card inventory unverified'};
