// Party Games Platform — relay server entry point.
// The server logic lives in createServer.js (factory form for tests + prod).

const { createServer } = require('./createServer');

const PORT = Number(process.env.PORT) || 8080;

createServer({ port: PORT }).then(({ port, close }) => {
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
