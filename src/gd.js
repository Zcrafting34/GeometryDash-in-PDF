//TODO
// El parallax no funciona

var EDITOR_MODE = false; // true = editor, false = juego normal

var cameraX = 0;
var vy = 0;
var GRAVITY = -2.9;
var JUMP_FORCE = 27;
var posy = 0;
var SPEED = 8;
var isGameOver = false;
var isOnGround = true;

var playerRotation = 0;
var framesInAir = 0;

var BG_FAR_RATIO = 0.2;

var TILE = 40;
var IMG_W = TILE;
var IMG_H = TILE;
var SPIKE_W = TILE;
var SPIKE_H = TILE;
var BLOCK_SIZE = TILE;
var PLAYER_SCREEN_X = 150;
var CTRL_H = 50;
var PAGE_W = 640;
var PAGE_H = 480;
var MAX_POSY = PAGE_H - TILE;

//Datos
if (typeof spikes === "undefined") {
  var spikes = [];
}
if (typeof blocks === "undefined") {
  var blocks = [];
}

var f_player = this.getField("img_sprite");
var fondo = this.getField("Fondo_Nivel");
var f_floor = this.getField("Piso_Base");
var f_bgFar = this.getField("BG_Far");

function saveLevel() {
  var f = this.getField("level_data");
  if (!f) return;
  f.value = JSON.stringify({ version: 1, spikes: spikes, blocks: blocks });
}

function loadLevel() {
  var f = this.getField("level_data");
  if (!f || !f.value) return;
  try {
    var data = JSON.parse(f.value);
    if (data.spikes) spikes = data.spikes;
    if (data.blocks) blocks = data.blocks;
  } catch (e) {}
}

var MAX_SPIKES = 8;
var MAX_BLOCKS = 32;

function renderSpikes() {
  var i, f, sx;
  for (i = 0; i < MAX_SPIKES; i++) {
    f = this.getField("img_spike_" + i);
    if (!f) continue;
    if (i < spikes.length) {
      sx = spikes[i].worldX - cameraX;
      // [Left, Top, Right, Bottom]
      f.rect = [sx, CTRL_H + TILE, sx + TILE, CTRL_H];
      f.display = display.visible;
    } else {
      f.display = display.hidden;
    }
  }
}

function renderBlocks() {
  var j, f, bx, by;
  for (j = 0; j < MAX_BLOCKS; j++) {
    f = this.getField("img_block_" + j);
    if (!f) continue;
    if (j < blocks.length) {
      bx = blocks[j].worldX - cameraX;
      by = CTRL_H + blocks[j].worldY;
      // [Left, Top, Right, Bottom]
      f.rect = [bx, by + TILE, bx + TILE, by];
      f.display = display.visible;
    } else {
      f.display = display.hidden;
    }
  }
}

//Colisiones

var HIT_MARGIN = 2;
var SPIKE_MARGIN = 6;

function checkSpikes(playerPdfY) {
  var i, sx;
  var pL = PLAYER_SCREEN_X + HIT_MARGIN + SPIKE_MARGIN;
  var pR = PLAYER_SCREEN_X + TILE - HIT_MARGIN - SPIKE_MARGIN;
  var pB = playerPdfY + HIT_MARGIN + SPIKE_MARGIN;
  var pT = playerPdfY + TILE - HIT_MARGIN - SPIKE_MARGIN;

  for (i = 0; i < spikes.length; i++) {
    sx = spikes[i].worldX - cameraX;
    var sL = sx + HIT_MARGIN + 4;
    var sR = sx + TILE - HIT_MARGIN - 4;
    var sB = CTRL_H + HIT_MARGIN + 4;
    var sT = CTRL_H + TILE - HIT_MARGIN;

    if (pR > sL && pL < sR && pT > sB && pB < sT) {
      gameOver();
      return true;
    }
  }
  return false;
}

function checkBlocks(playerPdfY) {
  var j, bx, blockBot, blockTop, blockL, blockR;
  var pL, pR, pB, pT;
  var penXLeft, penXRight, penX;
  var penYTop, penYBot, penY;

  pL = PLAYER_SCREEN_X + HIT_MARGIN;
  pR = PLAYER_SCREEN_X + TILE - HIT_MARGIN;
  pB = playerPdfY + HIT_MARGIN;
  pT = playerPdfY + TILE - HIT_MARGIN;

  for (j = 0; j < blocks.length; j++) {
    bx = blocks[j].worldX - cameraX;
    blockBot = CTRL_H + blocks[j].worldY;
    blockTop = blockBot + TILE;
    blockL = bx + HIT_MARGIN;
    blockR = bx + TILE - HIT_MARGIN;

    if (pR <= blockL || pL >= blockR || pT <= blockBot || pB >= blockTop)
      continue;

    penXLeft = pR - blockL;
    penXRight = blockR - pL;
    penX = penXLeft < penXRight ? penXLeft : penXRight;

    penYTop = blockTop - pB;
    penYBot = pT - blockBot;
    penY = penYTop < penYBot ? penYTop : penYBot;

    var landingFromAbove = vy <= 0 && penYTop <= penYBot;

    if (landingFromAbove || penY <= penX) {
      if (penYTop < penYBot) {
        posy = blocks[j].worldY + TILE;
        vy = 0;
        isOnGround = true;
      } else {
        posy = blocks[j].worldY - TILE;
        if (vy > 0) vy = 0;
      }
    } else {
      gameOver();
      return true;
    }
  }
  return false;
}

function gameLoop() {
  if (isGameOver) return;

  cameraX += SPEED;
  vy += GRAVITY;
  posy += vy;
  isOnGround = false;

  // Suelo
  if (posy <= 0) {
    posy = 0;
    vy = 0;
    isOnGround = true;
  }

  if (posy >= MAX_POSY) {
    posy = MAX_POSY;
    vy = 0;
  }

  var playerPdfY = CTRL_H + posy;
  if (!checkSpikes(playerPdfY)) {
    checkBlocks(playerPdfY);
  }

  playerPdfY = CTRL_H + posy;

  this.delay = true;

  f_player.rect = [
    PLAYER_SCREEN_X,
    playerPdfY + TILE,
    PLAYER_SCREEN_X + TILE,
    playerPdfY,
  ];

  var offsetFar = -((cameraX * BG_FAR_RATIO) % PAGE_W);

  if (f_bgFar) {
    f_bgFar.rect = [offsetFar, CTRL_H + PAGE_H, offsetFar + PAGE_W * 2, CTRL_H];
  }

  var i;
  for (i = 0; i < spikes.length; i++) {
    if (spikes[i].worldX - cameraX < -TILE) {
      spikes[i].worldX =
        cameraX + PAGE_W + 200 + Math.floor(Math.random() * 400);
    }
  }

  renderSpikes();
  renderBlocks();

  fondo.display = display.hidden;
  this.delay = false;
  fondo.display = display.visible;

  app.setTimeOut("gameLoop()", 25);
}

function gameOver() {
  isGameOver = true;
  app.alert("Endejo", 3);
}

//Editor de niveles
var editorTool = "block";
var GRID = TILE;

function snapToGrid(v) {
  return Math.floor(v / GRID) * GRID;
}

function editorRender() {
  renderSpikes();
  renderBlocks();
  var fs = this.getField("uwu_save");
  if (fs) fs.buttonSetCaption("Save (x=" + cameraX + ")");
}

function editorClick(mouseX, mouseY) {
  var worldX = snapToGrid(mouseX + cameraX);
  var worldY = snapToGrid(mouseY - CTRL_H);
  if (worldY < 0) return;
  if (editorTool === "spike") {
    spikes.push({ worldX: worldX });
  } else {
    blocks.push({ worldX: worldX, worldY: worldY });
  }
  editorRender();
}

function editorRightClick(mouseX, mouseY) {
  var worldX = mouseX + cameraX;
  var worldY = mouseY - CTRL_H;
  var best = -1,
    bestDist = 9999,
    k,
    d,
    dx,
    dy;

  for (k = 0; k < spikes.length; k++) {
    d = Math.abs(spikes[k].worldX - worldX);
    if (d < bestDist) {
      bestDist = d;
      best = k;
    }
  }
  if (bestDist < TILE && best >= 0) {
    spikes.splice(best, 1);
    editorRender();
    return;
  }

  best = -1;
  bestDist = 9999;
  for (k = 0; k < blocks.length; k++) {
    dx = Math.abs(blocks[k].worldX - worldX);
    dy = Math.abs(blocks[k].worldY - worldY);
    d = dx + dy;
    if (d < bestDist) {
      bestDist = d;
      best = k;
    }
  }
  if (bestDist < TILE * 2 && best >= 0) {
    blocks.splice(best, 1);
    editorRender();
  }
}

loadLevel();

if (EDITOR_MODE) {
  editorRender();
} else {
  gameLoop();
}
