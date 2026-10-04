function scoreBoard(board) {
  const sums = Array.from({length:10}, () => Array(10).fill(0));
  for(let y=0;y<9;y++) for(let x=0;x<9;x++) sums[y+1][x+1] = Number(!!board[y*9+x])+sums[y][x+1]+sums[y+1][x]-sums[y][x];
  let best = {score:0,x:0,y:0,width:0,height:0,square:0,extra:0};
  for(let y=0;y<9;y++) for(let x=0;x<9;x++) for(let h=1;h<=9-y;h++) for(let w=1;w<=9-x;w++) {
    const area=sums[y+h][x+w]-sums[y][x+w]-sums[y+h][x]+sums[y][x];
    if(area!==w*h) continue;
    const square=Math.min(w,h), extra=Math.abs(w-h), score=square*square+extra;
    if(score>best.score) best={score,x,y,width:w,height:h,square,extra};
  }
  return {...best,board:board.slice()};
}
function finalScore(player) {
  const empty=player.board.filter(c=>!c).length;
  const subtotal=player.scores.reduce((n,s)=>n+s.score,0);
  return {subtotal,empty,total:subtotal-empty};
}
module.exports={scoreBoard,finalScore};
