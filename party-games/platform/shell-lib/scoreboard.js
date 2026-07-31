// Scoreboard rendering — shared by game receivers.
//
// Both the reaction and image games want the same two patterns:
//   - a compact running scoreboard during ROUND_ENDED (highlight changed rows)
//   - a decorated final scoreboard on GAME_OVER (trophy on the winner)
//
// Kept deliberately tiny; if a game outgrows it, copy into that game's
// client folder rather than letting this accrete game-specific branches.

/**
 * Render a "current scores" list.
 * @param {HTMLElement} el        target <ul>/<ol>; cleared before write
 * @param {object}      scores    { [playerId]: points }
 * @param {Array}       players   [{ id, name }]
 * @param {object}      lastScores previous scores snapshot; rows with a
 *                                 changed value get a .changed class so CSS
 *                                 can pulse them
 */
export function renderScoreboard(el, scores, players, lastScores = {}) {
  el.innerHTML = '';
  const nameById = new Map(players.map((p) => [String(p.id), p.name]));
  const rows = Object.entries(scores || {})
    .map(([id, pts]) => {
      const prev = lastScores[id] ?? 0;
      return {
        id,
        name: nameById.get(String(id)) ?? `#${id}`,
        pts,
        changed: pts !== prev,
      };
    })
    .sort((a, b) => b.pts - a.pts);
  for (const row of rows) {
    const li = document.createElement('li');
    if (row.changed) li.classList.add('changed');
    li.textContent = `${row.name}: ${row.pts}`;
    el.appendChild(li);
  }
}

/**
 * Render the final-scoreboard for GAME_OVER.
 * @param {HTMLElement} el        target <ol>; cleared before write
 * @param {object}      scores    { [playerId]: points }
 * @param {number}      winnerId  id of the winning player (styled with .winner)
 * @param {Array}       players   [{ id, name }]
 */
export function renderFinalScoreboard(el, scores, winnerId, players) {
  el.innerHTML = '';
  const nameById = new Map(players.map((p) => [String(p.id), p.name]));
  const rows = Object.entries(scores || {})
    .map(([id, pts]) => ({
      id: Number(id),
      name: nameById.get(String(id)) ?? `#${id}`,
      pts,
    }))
    .sort((a, b) => b.pts - a.pts);
  for (const row of rows) {
    const li = document.createElement('li');
    if (row.id === winnerId) li.classList.add('winner');
    const nameEl = document.createElement('span');
    nameEl.className = 'name';
    nameEl.textContent = row.name;
    const ptsEl = document.createElement('span');
    ptsEl.className = 'pts';
    ptsEl.textContent = `${row.pts} pt${row.pts === 1 ? '' : 's'}`;
    li.appendChild(nameEl);
    li.appendChild(ptsEl);
    el.appendChild(li);
  }
}
