import { chromium, webkit } from 'playwright';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=path.dirname(fileURLToPath(import.meta.url));
for (const engine of [chromium,webkit]) {
 const browser=await engine.launch();
 for (const [width,height,legacy] of [[960,540,false],[1920,1080,false],[960,540,true]]) {
  const page=await browser.newPage({viewport:{width,height}});const errors=[];
  page.on('pageerror', e=>errors.push(e.message));
  // Older TV WebViews lack Array.at; exercise actual gameplay
  // with that API absent, rather than testing only modern desktop browsers.
  if (legacy) await page.addInitScript(() => { delete Array.prototype.at; });
  await page.clock.install();
  await page.goto('file://'+root+'/build/assets/bomberman/solo-game.html');
  const key=async (type,key)=>page.evaluate(([type,key])=>document.dispatchEvent(new KeyboardEvent(type,{key,bubbles:true})),[type,key]);
  await key('keydown','ArrowRight');await key('keyup','ArrowRight');
  assert.equal(await page.locator('[data-cat="1"]').getAttribute('aria-pressed'),'true');
  await page.screenshot({path:root+`/build/chooser-${engine.name()}-${width}${legacy?'-legacy':''}.png`});
  await key('keydown','Enter');await key('keyup','Enter');
  assert.equal(await page.locator('#play-screen').evaluate(e=>e.classList.contains('hidden')),false);
  const cell=()=>page.locator('#board .cell').evaluateAll(c=>c.findIndex(e=>e.classList.contains('player')));
  const before=await cell();await key('keydown','ArrowRight');await page.clock.runFor(250);await key('keyup','ArrowRight');
  assert.notEqual(await cell(),before);
  const stopped=await cell();await page.clock.runFor(300);assert.equal(await cell(),stopped);
  const tap=async direction=>{await key('keydown',direction);await key('keyup',direction);await page.clock.runFor(150);};
  // Return to spawn, then exercise the other three directions in clear cells.
  for (let n=0;n<11 && await cell()!==before;n++) await tap('ArrowLeft');
  assert.equal(await cell(),before);
  await tap('ArrowDown');assert.equal(await cell(),before+13);
  await tap('ArrowUp');assert.equal(await cell(),before);
  await tap('ArrowRight');assert.equal(await cell(),before+1);
  await tap('ArrowLeft');assert.equal(await cell(),before);
  await key('keydown','Enter');await key('keyup','Enter');await page.clock.runFor(20);assert.equal(await page.locator('.cell.bomb').count(),1);
  await key('keydown','Escape');await key('keyup','Escape');
  assert.match(await page.locator('#toast').innerText(),/Paused/);
  const timer=await page.locator('#timer').innerText();await page.clock.runFor(1000);assert.equal(await page.locator('#timer').innerText(),timer);
  await key('keydown','Enter');await key('keyup','Enter');
  const box=await page.locator('#board').boundingBox();assert.ok(box.y+box.height<=height);
  await page.screenshot({path:root+`/build/game-${engine.name()}-${width}${legacy?'-legacy':''}.png`});
  assert.deepEqual(errors,[]);console.log(`PASS ${engine.name()} ${width}x${height}${legacy?' without Array.at':''}: chooser/start/hold/release/bomb/pause/resume/layout`);
  await page.close();
 }
 await browser.close();
}
