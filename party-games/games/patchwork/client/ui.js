import './geometry.js';
export const G=globalThis.PDGeometry;
export const escape=value=>String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const skins=['linen','night','paper'];
export function patch(cells,label='Patch') {
  const w=Math.max(...cells.map(c=>c[0]))+1,h=Math.max(...cells.map(c=>c[1]))+1;
  return `<svg class="patch" viewBox="-0.15 -0.15 ${w+.3} ${h+.3}" role="img" aria-label="${escape(label)}">${cells.map(([x,y])=>`<rect x="${x}" y="${y}" width=".95" height=".95" rx=".12"/>`).join('')}</svg>`;
}
export function board(values,{ghost=[],invalid=false,highlight=null,empty=false,interactive=false}={}) {
  return `<div class="quilt ${interactive?'interactive':''}" role="group" aria-label="9 by 9 quilt">${values.map((v,i)=>{
    const x=i%9,y=Math.floor(i/9),inGhost=ghost.some(c=>c[0]===x&&c[1]===y);
    let cls=v?'filled color-'+(Number(v)%5):'blank';
    if(inGhost) cls+=' ghost'+(invalid?' invalid':'');
    if(empty&&!v) cls+=' deduction';
    if(highlight&&x>=highlight.x&&y>=highlight.y&&x<highlight.x+highlight.width&&y<highlight.y+highlight.height) {
      const q=Math.min(highlight.width,highlight.height);
      cls+=(x<highlight.x+q&&y<highlight.y+q)?' square':' strip';
    }
    const tag=interactive?'button':'span';
    return `<${tag} class="cell ${cls}" data-cell="${i}" ${interactive?`type="button" aria-label="Row ${y+1}, column ${x+1}, ${v?'filled':'empty'}"`:''}></${tag}>`;
  }).join('')}</div>`;
}
export function phaseTitle(s) {
  if(s.phase==='LOBBY')return 'Gather around';
  if(s.phase==='STARTING')return 'Place your starting patch';
  if(s.phase==='PLACING')return s.round===3&&s.turn===6?'Final turn · choose any remaining patch':`Round ${s.round} · turn ${s.turn} of 6`;
  if(s.phase==='TURN_RESULTS')return `Round ${s.round} · turn ${s.turn} quilts`;
  if(s.phase==='SCORING')return `Round ${s.round} · prepare to score`;
  if(s.phase==='ROUND_RESULTS')return `Round ${s.round} scores`;
  return 'The final stitch';
}
export function standings(s) {
  const ordered=s.players.filter(p=>!p.withdrawn).slice().sort((a,b)=>b.final.total-a.final.total);
  const best=ordered[0]?.final.total;
  return `<ol class="standings">${ordered.map(p=>`<li class="${p.final.total===best?'winner':''}"><span>${escape(p.name)}${p.final.total===best?' · winner':''}</span><strong>${p.final.total}</strong></li>`).join('')}</ol>${ordered.filter(p=>p.final.total===best).length>1?'<p>Shared victory!</p>':''}`;
}
export function skinPicker(current) {return `<label class="skin-picker">Skin <select data-skin>${skins.map(s=>`<option ${s===current?'selected':''}>${s}</option>`).join('')}</select></label>`;}
