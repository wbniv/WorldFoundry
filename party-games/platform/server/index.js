// Party Games Platform — relay server entry point.
// The server logic lives in createServer.js (factory form for tests + prod).

const { createServer } = require('./createServer');

const PORT = Number(process.env.PORT) || 8080;
const GAME_NAME = process.env.WF_GAME ?? 'reaction';   // set WF_GAME=none to run the bare platform

let game = null;
if (GAME_NAME && GAME_NAME !== 'none') {
  try {
    const mod = require(`../../games/${GAME_NAME}/${GAME_NAME}`);
    const factory = mod[`create${GAME_NAME[0].toUpperCase()}${GAME_NAME.slice(1)}Game`];
    if (typeof factory !== 'function') {
      throw new Error(`expected factory create${GAME_NAME[0].toUpperCase()}${GAME_NAME.slice(1)}Game in games/${GAME_NAME}/${GAME_NAME}.js`);
    }
    game = factory();
    console.log(`game plugin: ${game.name}`);
  } catch (e) {
    console.error(`failed to load game '${GAME_NAME}':`, e.message);
    process.exit(1);
  }
}

createServer({ port: PORT, game }).then(({ port, close }) => {
  console.log(`party-games platform ready on http://localhost:${port}`);
  console.log(`  receiver:   http://localhost:${port}/receiver`);
  console.log(`  controller: http://localhost:${port}/controller?name=Alice`);

  const shutdown = (sig) => {
    console.log(`\nreceived ${sig}, shutting down`);
    close().then(() => process.exit(0));
  };
  process.on('SIGINT',  () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}).catch((err) => {
  console.error('server failed to start:', err);
  process.exit(1);
});
