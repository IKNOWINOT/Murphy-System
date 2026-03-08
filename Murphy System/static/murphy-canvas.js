/* murphy-canvas.js — Murphy System Canvas Rendering Engine
 * © 2020 Inoni Limited Liability Company by Corey Post
 * License: BSL 1.1
 *
 * Licensed under the Business Source License 1.1 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://mariadb.com/bsl11/
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 1 — MURPHY PORT
 * ═══════════════════════════════════════════════════════════════════ */

class MurphyPort {
  /**
   * Creates a connection point on a node.
   * @param {Object} opts
   * @param {string} opts.id          — Unique port identifier
   * @param {'input'|'output'} opts.type — Port direction
   * @param {string} opts.label       — Display label
   * @param {string} opts.nodeId      — Parent node id
   * @param {'left'|'right'|'top'|'bottom'} opts.side — Which side of the node
   */
  constructor({ id, type, label = '', nodeId = '', side = 'left' }) {
    this.id = id;
    this.type = type;
    this.label = label;
    this.nodeId = nodeId;
    this.side = side;
    this.radius = 6;
    this.hovered = false;
    this.connected = false;
    this._color = '#4A90D9';
  }

  /**
   * Renders the port circle on the canvas.
   * Input ports are hollow; output ports are filled.
   * Hovered ports render larger.
   * @param {CanvasRenderingContext2D} ctx — Canvas 2D context
   * @param {number} x — Port center x in screen space
   * @param {number} y — Port center y in screen space
   * @param {Object} transform — { offsetX, offsetY, scale }
   */
  draw(ctx, x, y, transform) {
    const r = (this.hovered ? this.radius * 1.6 : this.radius) * transform.scale;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    if (this.type === 'output') {
      ctx.fillStyle = this._color;
      ctx.fill();
    } else {
      ctx.fillStyle = '#0C1017';
      ctx.fill();
      ctx.strokeStyle = this._color;
      ctx.lineWidth = 2 * transform.scale;
      ctx.stroke();
    }
    if (this.hovered) {
      ctx.save();
      ctx.shadowColor = this._color;
      ctx.shadowBlur = 8 * transform.scale;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      if (this.type === 'output') {
        ctx.fillStyle = this._color;
        ctx.fill();
      } else {
        ctx.strokeStyle = this._color;
        ctx.lineWidth = 2 * transform.scale;
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  /**
   * Tests whether a world-space point is within this port's hit area.
   * @param {number} worldX — Test x in world space
   * @param {number} worldY — Test y in world space
   * @param {number} portX  — Port center x in world space
   * @param {number} portY  — Port center y in world space
   * @returns {boolean}
   */
  hitTest(worldX, worldY, portX, portY) {
    const hitRadius = this.radius + 4;
    const dx = worldX - portX;
    const dy = worldY - portY;
    return dx * dx + dy * dy <= hitRadius * hitRadius;
  }
}

/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 2 — MURPHY NODE
 * ═══════════════════════════════════════════════════════════════════ */

const NODE_TYPE_COLORS = {
  trigger:     '#22C55E',
  action:      '#14B8A6',
  logic:       '#8B5CF6',
  gate:        '#F59E0B',
  integration: '#0EA5E9',
  module:      '#6366F1',
};

const NODE_TYPE_ICONS = {
  trigger:     '⚡',
  action:      '▶',
  logic:       '◆',
  gate:        '⊞',
  integration: '⇌',
  module:      '☰',
};

const HEALTH_COLORS = {
  healthy: '#22C55E',
  warning: '#F59E0B',
  error:   '#EF4444',
  idle:    '#6B7280',
};

class MurphyNode {
  /**
   * Creates a visual node for the canvas.
   * @param {Object} opts
   * @param {string} opts.id     — Unique node identifier
   * @param {number} opts.x      — World x position
   * @param {number} opts.y      — World y position
   * @param {'trigger'|'action'|'logic'|'gate'|'integration'|'module'} opts.type
   * @param {string} opts.label  — Display label
   * @param {string} [opts.icon] — Optional icon character override
   * @param {string} [opts.color]— Optional border color override
   * @param {'healthy'|'warning'|'error'|'idle'} [opts.health='idle']
   * @param {Object} [opts.data] — Arbitrary user data (e.g. domain, config)
   * @param {Array}  [opts.ports]— Array of port descriptors
   */
  constructor({ id, x = 0, y = 0, type = 'action', label = '', icon, color, health = 'idle', data = {}, ports = [] }) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.type = type;
    this.label = label;
    this.icon = icon || NODE_TYPE_ICONS[type] || '■';
    this.color = color || NODE_TYPE_COLORS[type] || '#4A90D9';
    this.health = health;
    this.data = data;
    this.width = 180;
    this.selected = false;
    this.running = false;
    this.error = false;
    this._pulsePhase = Math.random() * Math.PI * 2;
    this.ports = ports.map(p => {
      const port = new MurphyPort({ ...p, nodeId: this.id });
      port._color = this.color;
      return port;
    });
  }

  /** @returns {number} Calculated node height based on port count. */
  get height() {
    const inputPorts = this.ports.filter(p => p.type === 'input');
    const outputPorts = this.ports.filter(p => p.type === 'output');
    const maxSidePorts = Math.max(inputPorts.length, outputPorts.length, 1);
    return Math.max(60, 40 + maxSidePorts * 22);
  }

  /**
   * Renders the node on the canvas.
   * @param {CanvasRenderingContext2D} ctx — Canvas 2D context
   * @param {Object} transform — { offsetX, offsetY, scale }
   */
  draw(ctx, transform) {
    const sx = this.x * transform.scale + transform.offsetX;
    const sy = this.y * transform.scale + transform.offsetY;
    const sw = this.width * transform.scale;
    const sh = this.height * transform.scale;
    const r = 8 * transform.scale;
    const now = performance.now() / 1000;

    ctx.save();

    // Running: pulsing glow
    if (this.running) {
      const pulse = 0.5 + 0.5 * Math.sin(now * 4 + this._pulsePhase);
      ctx.shadowColor = this.color;
      ctx.shadowBlur = (10 + pulse * 12) * transform.scale;
    }

    // Error: red pulsing border
    if (this.error) {
      const pulse = 0.5 + 0.5 * Math.sin(now * 5 + this._pulsePhase);
      ctx.shadowColor = '#EF4444';
      ctx.shadowBlur = (8 + pulse * 14) * transform.scale;
    }

    // Selected: brighter border + glow
    if (this.selected) {
      ctx.shadowColor = this.color;
      ctx.shadowBlur = 16 * transform.scale;
    }

    // Body fill
    this._roundRect(ctx, sx, sy, sw, sh, r);
    ctx.fillStyle = '#151B26';
    ctx.fill();

    // Border
    const borderColor = this.error ? '#EF4444' : this.color;
    const borderAlpha = this.selected ? 'FF' : 'CC';
    ctx.strokeStyle = borderColor + borderAlpha;
    ctx.lineWidth = (this.selected ? 2.5 : 1.5) * transform.scale;
    ctx.stroke();

    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;

    // Icon
    ctx.font = `${14 * transform.scale}px sans-serif`;
    ctx.fillStyle = this.color;
    ctx.textBaseline = 'middle';
    ctx.fillText(this.icon, sx + 12 * transform.scale, sy + 20 * transform.scale);

    // Label
    ctx.font = `bold ${12 * transform.scale}px sans-serif`;
    ctx.fillStyle = '#E2E8F0';
    ctx.textBaseline = 'middle';
    const maxTextW = sw - 60 * transform.scale;
    let displayLabel = this.label;
    while (ctx.measureText(displayLabel).width > maxTextW && displayLabel.length > 1) {
      displayLabel = displayLabel.slice(0, -1);
    }
    if (displayLabel !== this.label) displayLabel += '…';
    ctx.fillText(displayLabel, sx + 32 * transform.scale, sy + 20 * transform.scale);

    // Health dot (top-right, 8px)
    const dotR = 4 * transform.scale;
    const dotX = sx + sw - 14 * transform.scale;
    const dotY = sy + 14 * transform.scale;
    ctx.beginPath();
    ctx.arc(dotX, dotY, dotR, 0, Math.PI * 2);
    ctx.fillStyle = HEALTH_COLORS[this.health] || HEALTH_COLORS.idle;
    ctx.fill();

    // Ports
    const inputPorts = this.ports.filter(p => p.side === 'left' || p.type === 'input');
    const outputPorts = this.ports.filter(p => p.side === 'right' || p.type === 'output');

    inputPorts.forEach((port, i) => {
      const pos = this._getPortScreenPos(port, i, inputPorts.length, transform);
      port.draw(ctx, pos.x, pos.y, transform);
    });

    outputPorts.forEach((port, i) => {
      const pos = this._getPortScreenPos(port, i, outputPorts.length, transform);
      port.draw(ctx, pos.x, pos.y, transform);
    });

    ctx.restore();
  }

  /**
   * Returns the screen-space position for a port within the node.
   * @private
   */
  _getPortScreenPos(port, index, total, transform) {
    const sx = this.x * transform.scale + transform.offsetX;
    const sy = this.y * transform.scale + transform.offsetY;
    const sw = this.width * transform.scale;
    const sh = this.height * transform.scale;
    const side = port.side || (port.type === 'input' ? 'left' : 'right');
    const spacing = sh / (total + 1);
    const offset = spacing * (index + 1);

    switch (side) {
      case 'left':   return { x: sx, y: sy + offset };
      case 'right':  return { x: sx + sw, y: sy + offset };
      case 'top':    return { x: sx + sw / (total + 1) * (index + 1), y: sy };
      case 'bottom': return { x: sx + sw / (total + 1) * (index + 1), y: sy + sh };
      default:       return { x: sx, y: sy + offset };
    }
  }

  /**
   * Tests whether a world-space point is inside this node's bounding box.
   * @param {number} worldX
   * @param {number} worldY
   * @returns {boolean}
   */
  hitTest(worldX, worldY) {
    return (
      worldX >= this.x &&
      worldX <= this.x + this.width &&
      worldY >= this.y &&
      worldY <= this.y + this.height
    );
  }

  /**
   * Returns the world-space center position of a port by id.
   * @param {string} portId
   * @returns {{x: number, y: number}}
   */
  getPortPosition(portId) {
    const sideInputPorts = this.ports.filter(p => p.side === 'left' || p.type === 'input');
    const sideOutputPorts = this.ports.filter(p => p.side === 'right' || p.type === 'output');
    let list, index;

    index = sideInputPorts.findIndex(p => p.id === portId);
    if (index !== -1) {
      list = sideInputPorts;
    } else {
      index = sideOutputPorts.findIndex(p => p.id === portId);
      list = sideOutputPorts;
    }

    if (index === -1) return { x: this.x, y: this.y };

    const port = list[index];
    const total = list.length;
    const side = port.side || (port.type === 'input' ? 'left' : 'right');
    const spacing = this.height / (total + 1);
    const offset = spacing * (index + 1);

    switch (side) {
      case 'left':   return { x: this.x, y: this.y + offset };
      case 'right':  return { x: this.x + this.width, y: this.y + offset };
      case 'top':    return { x: this.x + this.width / (total + 1) * (index + 1), y: this.y };
      case 'bottom': return { x: this.x + this.width / (total + 1) * (index + 1), y: this.y + this.height };
      default:       return { x: this.x, y: this.y + offset };
    }
  }

  /**
   * Returns the bounding box of this node in world coordinates.
   * @returns {{x: number, y: number, width: number, height: number}}
   */
  getBounds() {
    return { x: this.x, y: this.y, width: this.width, height: this.height };
  }

  /**
   * Sets the node's world position.
   * @param {number} x
   * @param {number} y
   */
  setPosition(x, y) {
    this.x = x;
    this.y = y;
  }

  /**
   * Updates the node's health status indicator.
   * @param {'healthy'|'warning'|'error'|'idle'} status
   */
  setHealth(status) {
    this.health = status;
  }

  /**
   * Sets whether the node is currently executing (animated border).
   * @param {boolean} val
   */
  setRunning(val) {
    this.running = !!val;
  }

  /**
   * Sets the node's selected state.
   * @param {boolean} val
   */
  setSelected(val) {
    this.selected = !!val;
  }

  /** Draws a rounded rectangle path. @private */
  _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }
}

/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 3 — MURPHY EDGE
 * ═══════════════════════════════════════════════════════════════════ */

const EDGE_HEALTH_COLORS = {
  healthy:  '#22C55E',
  slow:     '#F59E0B',
  error:    '#EF4444',
  inactive: '#6B7280',
};

class MurphyEdge {
  /**
   * Creates a connection (edge) between two node ports.
   * @param {Object} opts
   * @param {string} opts.id             — Unique edge identifier
   * @param {string} opts.sourceNodeId   — Source node id
   * @param {string} opts.sourcePortId   — Source port id
   * @param {string} opts.targetNodeId   — Target node id
   * @param {string} opts.targetPortId   — Target port id
   * @param {string} [opts.color='#2A3A4E'] — Edge color
   * @param {number} [opts.thickness=2]  — Line width in pixels
   * @param {boolean} [opts.animated=true] — Animated dash flow
   * @param {'healthy'|'slow'|'error'|'inactive'} [opts.health='healthy']
   */
  constructor({ id, sourceNodeId, sourcePortId, targetNodeId, targetPortId, color = '#2A3A4E', thickness = 2, animated = true, health = 'healthy' }) {
    this.id = id;
    this.sourceNodeId = sourceNodeId;
    this.sourcePortId = sourcePortId;
    this.targetNodeId = targetNodeId;
    this.targetPortId = targetPortId;
    this.color = color;
    this.thickness = thickness;
    this.animated = animated;
    this.health = health;
    this._dashOffset = 0;
  }

  /**
   * Renders the edge as a Bezier curve with optional animation and arrow.
   * @param {CanvasRenderingContext2D} ctx — Canvas 2D context
   * @param {{x: number, y: number}} sourcePos — Source port world position
   * @param {{x: number, y: number}} targetPos — Target port world position
   * @param {Object} transform — { offsetX, offsetY, scale }
   */
  draw(ctx, sourcePos, targetPos, transform) {
    const sx = sourcePos.x * transform.scale + transform.offsetX;
    const sy = sourcePos.y * transform.scale + transform.offsetY;
    const tx = targetPos.x * transform.scale + transform.offsetX;
    const ty = targetPos.y * transform.scale + transform.offsetY;

    const dx = Math.abs(tx - sx);
    const cpOffset = Math.max(60, dx * 0.4) * transform.scale;
    const cp1x = sx + cpOffset;
    const cp1y = sy;
    const cp2x = tx - cpOffset;
    const cp2y = ty;

    const edgeColor = EDGE_HEALTH_COLORS[this.health] || this.color;
    const lineW = Math.max(1, Math.min(5, this.thickness)) * transform.scale;

    ctx.save();

    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, tx, ty);
    ctx.strokeStyle = edgeColor;
    ctx.lineWidth = lineW;

    if (this.animated) {
      this._dashOffset -= 0.5;
      ctx.setLineDash([8 * transform.scale, 6 * transform.scale]);
      ctx.lineDashOffset = this._dashOffset;
    }

    ctx.stroke();
    ctx.setLineDash([]);

    // Arrow at target end
    const arrowLen = 10 * transform.scale;
    const angle = Math.atan2(ty - cp2y, tx - cp2x);
    ctx.beginPath();
    ctx.moveTo(tx, ty);
    ctx.lineTo(tx - arrowLen * Math.cos(angle - 0.35), ty - arrowLen * Math.sin(angle - 0.35));
    ctx.lineTo(tx - arrowLen * Math.cos(angle + 0.35), ty - arrowLen * Math.sin(angle + 0.35));
    ctx.closePath();
    ctx.fillStyle = edgeColor;
    ctx.fill();

    ctx.restore();
  }

  /**
   * Tests whether a world-space point is near this edge's Bezier curve.
   * @param {number} worldX
   * @param {number} worldY
   * @param {{x: number, y: number}} sourcePos — Source port world position
   * @param {{x: number, y: number}} targetPos — Target port world position
   * @returns {boolean}
   */
  hitTest(worldX, worldY, sourcePos, targetPos) {
    const steps = 30;
    const threshold = 8;
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      const dx = Math.abs(targetPos.x - sourcePos.x);
      const cpOff = Math.max(60, dx * 0.4);
      const cp1x = sourcePos.x + cpOff;
      const cp1y = sourcePos.y;
      const cp2x = targetPos.x - cpOff;
      const cp2y = targetPos.y;
      const ti = 1 - t;
      const px = ti * ti * ti * sourcePos.x + 3 * ti * ti * t * cp1x + 3 * ti * t * t * cp2x + t * t * t * targetPos.x;
      const py = ti * ti * ti * sourcePos.y + 3 * ti * ti * t * cp1y + 3 * ti * t * t * cp2y + t * t * t * targetPos.y;
      const ddx = worldX - px;
      const ddy = worldY - py;
      if (ddx * ddx + ddy * ddy <= threshold * threshold) return true;
    }
    return false;
  }

  /**
   * Updates the edge's health status, changing its render color.
   * @param {'healthy'|'slow'|'error'|'inactive'} status
   */
  setHealth(status) {
    this.health = status;
  }

  /**
   * Sets the edge's throughput (line thickness). Value is normalized to 1–5 range.
   * @param {number} value — Raw throughput value (0–100+)
   */
  setThroughput(value) {
    this.thickness = Math.max(1, Math.min(5, value));
  }
}

/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 4 — MURPHY CANVAS (CORE ENGINE)
 * ═══════════════════════════════════════════════════════════════════ */

class MurphyCanvas {
  /**
   * Core canvas rendering engine. Creates an HTML5 Canvas inside the
   * given container element and manages all nodes, edges, and viewport.
   * @param {HTMLElement} containerEl — Parent div for the canvas
   * @param {Object} [options={}]
   * @param {number}  [options.width]            — Canvas width (defaults to container width)
   * @param {number}  [options.height]           — Canvas height (defaults to container height)
   * @param {number}  [options.gridSize=20]      — Grid spacing in world units
   * @param {string}  [options.gridColor='#1E2A3A'] — Grid dot color
   * @param {boolean} [options.showGrid=true]    — Whether to draw the grid
   * @param {boolean} [options.showMinimap=true]  — Whether to draw the minimap
   * @param {string}  [options.backgroundColor='#0C1017'] — Canvas background color
   */
  constructor(containerEl, options = {}) {
    this.container = containerEl;
    this.options = Object.assign({
      width: containerEl.clientWidth || 800,
      height: containerEl.clientHeight || 600,
      gridSize: 20,
      gridColor: '#1E2A3A',
      showGrid: true,
      showMinimap: true,
      backgroundColor: '#0C1017',
    }, options);

    this.canvas = document.createElement('canvas');
    this.canvas.width = this.options.width;
    this.canvas.height = this.options.height;
    this.canvas.style.display = 'block';
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');

    this.transform = { offsetX: 0, offsetY: 0, scale: 1.0 };
    this._nodes = new Map();
    this._edges = new Map();
    this._animFrameId = null;
    this._destroyed = false;
    this.interaction = null;

    this._handleResize = this._onResize.bind(this);
    window.addEventListener('resize', this._handleResize);
    this._onResize();

    this.render();
  }

  /** @private — Handles container/window resize. */
  _onResize() {
    const w = this.container.clientWidth || this.options.width;
    const h = this.container.clientHeight || this.options.height;
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this._canvasWidth = w;
    this._canvasHeight = h;
  }

  /**
   * Main render loop. Continuously redraws the canvas using requestAnimationFrame.
   */
  render() {
    if (this._destroyed) return;
    this._draw();
    this._animFrameId = requestAnimationFrame(() => this.render());
  }

  /** @private — Full redraw pass. */
  _draw() {
    const ctx = this.ctx;
    const w = this._canvasWidth;
    const h = this._canvasHeight;

    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = this.options.backgroundColor;
    ctx.fillRect(0, 0, w, h);

    // Grid
    if (this.options.showGrid) this._drawGrid(ctx, w, h);

    // Edges
    for (const edge of this._edges.values()) {
      const srcNode = this._nodes.get(edge.sourceNodeId);
      const tgtNode = this._nodes.get(edge.targetNodeId);
      if (!srcNode || !tgtNode) continue;
      const srcPos = srcNode.getPortPosition(edge.sourcePortId);
      const tgtPos = tgtNode.getPortPosition(edge.targetPortId);
      edge.draw(ctx, srcPos, tgtPos, this.transform);
    }

    // Nodes
    for (const node of this._nodes.values()) {
      node.draw(ctx, this.transform);
    }

    // Interaction overlays (connecting line, rubber-band)
    if (this.interaction) {
      const overlayFn = this.interaction.getOverlayDrawFn();
      if (overlayFn) overlayFn(ctx, this.transform);
    }

    // Minimap
    if (this.options.showMinimap) this._drawMinimap(ctx, w, h);
  }

  /** @private — Draws the dot grid. */
  _drawGrid(ctx, w, h) {
    const gs = this.options.gridSize * this.transform.scale;
    if (gs < 4) return; // too small to be useful

    const ox = this.transform.offsetX % gs;
    const oy = this.transform.offsetY % gs;
    const dotSize = Math.max(1, this.transform.scale);

    ctx.fillStyle = this.options.gridColor;
    for (let x = ox; x < w; x += gs) {
      for (let y = oy; y < h; y += gs) {
        ctx.fillRect(x - dotSize * 0.5, y - dotSize * 0.5, dotSize, dotSize);
      }
    }
  }

  /** @private — Draws the minimap in the bottom-right corner. */
  _drawMinimap(ctx, canvasW, canvasH) {
    const mmW = 150;
    const mmH = 100;
    const mmX = canvasW - mmW - 12;
    const mmY = canvasH - mmH - 12;

    ctx.save();

    // Background
    ctx.fillStyle = 'rgba(12, 16, 23, 0.85)';
    ctx.strokeStyle = '#2A3A4E';
    ctx.lineWidth = 1;
    ctx.fillRect(mmX, mmY, mmW, mmH);
    ctx.strokeRect(mmX, mmY, mmW, mmH);

    if (this._nodes.size === 0) {
      ctx.restore();
      return;
    }

    // Compute world bounds
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of this._nodes.values()) {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + n.width);
      maxY = Math.max(maxY, n.y + n.height);
    }
    const pad = 50;
    minX -= pad; minY -= pad; maxX += pad; maxY += pad;
    const worldW = maxX - minX || 1;
    const worldH = maxY - minY || 1;
    const mmScale = Math.min(mmW / worldW, mmH / worldH);

    const toMmX = (wx) => mmX + (wx - minX) * mmScale;
    const toMmY = (wy) => mmY + (wy - minY) * mmScale;

    // Draw nodes as small rectangles
    for (const n of this._nodes.values()) {
      ctx.fillStyle = n.color;
      ctx.fillRect(toMmX(n.x), toMmY(n.y), Math.max(2, n.width * mmScale), Math.max(2, n.height * mmScale));
    }

    // Draw edges as thin lines
    ctx.strokeStyle = '#4A90D9';
    ctx.lineWidth = 0.5;
    for (const e of this._edges.values()) {
      const src = this._nodes.get(e.sourceNodeId);
      const tgt = this._nodes.get(e.targetNodeId);
      if (!src || !tgt) continue;
      ctx.beginPath();
      ctx.moveTo(toMmX(src.x + src.width / 2), toMmY(src.y + src.height / 2));
      ctx.lineTo(toMmX(tgt.x + tgt.width / 2), toMmY(tgt.y + tgt.height / 2));
      ctx.stroke();
    }

    // Viewport indicator
    const vpLeft = -this.transform.offsetX / this.transform.scale;
    const vpTop = -this.transform.offsetY / this.transform.scale;
    const vpW = canvasW / this.transform.scale;
    const vpH = canvasH / this.transform.scale;
    ctx.strokeStyle = '#E2E8F0';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(toMmX(vpLeft), toMmY(vpTop), vpW * mmScale, vpH * mmScale);

    ctx.restore();
  }

  /**
   * Adds a MurphyNode to the canvas.
   * @param {MurphyNode} node
   */
  addNode(node) {
    this._nodes.set(node.id, node);
  }

  /**
   * Removes a node by id.
   * @param {string} id
   */
  removeNode(id) {
    this._nodes.delete(id);
    // Remove connected edges
    for (const [eId, edge] of this._edges) {
      if (edge.sourceNodeId === id || edge.targetNodeId === id) {
        this._edges.delete(eId);
      }
    }
  }

  /**
   * Adds a MurphyEdge to the canvas.
   * @param {MurphyEdge} edge
   */
  addEdge(edge) {
    this._edges.set(edge.id, edge);
  }

  /**
   * Removes an edge by id.
   * @param {string} id
   */
  removeEdge(id) {
    this._edges.delete(id);
  }

  /**
   * Returns all nodes as an array.
   * @returns {MurphyNode[]}
   */
  getNodes() {
    return Array.from(this._nodes.values());
  }

  /**
   * Returns all edges as an array.
   * @returns {MurphyEdge[]}
   */
  getEdges() {
    return Array.from(this._edges.values());
  }

  /**
   * Removes all nodes and edges from the canvas.
   */
  clear() {
    this._nodes.clear();
    this._edges.clear();
  }

  /**
   * Serializes the canvas state (nodes, edges, transform) to a JSON-compatible object.
   * @returns {Object}
   */
  toJSON() {
    return {
      transform: { ...this.transform },
      nodes: this.getNodes().map(n => ({
        id: n.id, x: n.x, y: n.y, type: n.type, label: n.label,
        icon: n.icon, color: n.color, health: n.health, data: n.data,
        ports: n.ports.map(p => ({ id: p.id, type: p.type, label: p.label, side: p.side })),
      })),
      edges: this.getEdges().map(e => ({
        id: e.id, sourceNodeId: e.sourceNodeId, sourcePortId: e.sourcePortId,
        targetNodeId: e.targetNodeId, targetPortId: e.targetPortId,
        color: e.color, thickness: e.thickness, animated: e.animated, health: e.health,
      })),
    };
  }

  /**
   * Restores canvas state from a previously serialized JSON object.
   * @param {Object} data — Object from toJSON()
   */
  fromJSON(data) {
    this.clear();
    if (data.transform) {
      this.transform.offsetX = data.transform.offsetX || 0;
      this.transform.offsetY = data.transform.offsetY || 0;
      this.transform.scale = data.transform.scale || 1;
    }
    if (data.nodes) {
      data.nodes.forEach(nd => this.addNode(new MurphyNode(nd)));
    }
    if (data.edges) {
      data.edges.forEach(ed => this.addEdge(new MurphyEdge(ed)));
    }
  }

  /**
   * Converts screen (pixel) coordinates to world coordinates.
   * @param {number} x — Screen x
   * @param {number} y — Screen y
   * @returns {{x: number, y: number}}
   */
  screenToWorld(x, y) {
    return {
      x: (x - this.transform.offsetX) / this.transform.scale,
      y: (y - this.transform.offsetY) / this.transform.scale,
    };
  }

  /**
   * Converts world coordinates to screen (pixel) coordinates.
   * @param {number} x — World x
   * @param {number} y — World y
   * @returns {{x: number, y: number}}
   */
  worldToScreen(x, y) {
    return {
      x: x * this.transform.scale + this.transform.offsetX,
      y: y * this.transform.scale + this.transform.offsetY,
    };
  }

  /**
   * Auto-adjusts zoom and pan to fit all nodes in the viewport with padding.
   */
  fitView() {
    if (this._nodes.size === 0) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of this._nodes.values()) {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + n.width);
      maxY = Math.max(maxY, n.y + n.height);
    }
    const pad = 60;
    const worldW = (maxX - minX) + pad * 2;
    const worldH = (maxY - minY) + pad * 2;
    const scale = Math.min(this._canvasWidth / worldW, this._canvasHeight / worldH);
    this.transform.scale = Math.max(0.25, Math.min(3.0, scale));
    this.transform.offsetX = (this._canvasWidth - worldW * this.transform.scale) / 2 - (minX - pad) * this.transform.scale;
    this.transform.offsetY = (this._canvasHeight - worldH * this.transform.scale) / 2 - (minY - pad) * this.transform.scale;
  }

  /**
   * Destroys the canvas: stops the render loop, removes listeners, and clears the DOM element.
   */
  destroy() {
    this._destroyed = true;
    if (this._animFrameId !== null) {
      cancelAnimationFrame(this._animFrameId);
      this._animFrameId = null;
    }
    window.removeEventListener('resize', this._handleResize);
    this.clear();
    if (this.canvas && this.canvas.parentNode) {
      this.canvas.parentNode.removeChild(this.canvas);
    }
  }
}

/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 5 — MURPHY CANVAS INTERACTION
 * ═══════════════════════════════════════════════════════════════════ */

class MurphyCanvasInteraction {
  /**
   * Handles all user interaction (mouse, keyboard, touch) on a MurphyCanvas.
   * @param {MurphyCanvas} canvas — The MurphyCanvas instance to attach to
   */
  constructor(canvas) {
    this.canvas = canvas;
    canvas.interaction = this;
    this._selectedNodes = new Set();
    this._dragging = false;
    this._panning = false;
    this._connecting = false;
    this._rubberBand = null;
    this._dragStart = null;
    this._dragNodeOffsets = new Map();
    this._connectSource = null;
    this._connectTempTarget = null;
    this._lastMouse = { x: 0, y: 0 };
    this._undoStack = [];
    this._redoStack = [];
    this._clipboard = [];
    this._pasteCounter = 0;

    // Callbacks
    this._onNodeSelect = null;
    this._onNodeMove = null;
    this._onEdgeCreate = null;
    this._onEdgeDelete = null;

    // Touch state
    this._touches = [];
    this._touchPanStart = null;
    this._touchPinchDist = null;
    this._touchPinchScale = null;
    this._longPressTimer = null;
    this._longPressTriggered = false;

    // Bind handlers
    this._onMouseDown = this._handleMouseDown.bind(this);
    this._onMouseMove = this._handleMouseMove.bind(this);
    this._onMouseUp = this._handleMouseUp.bind(this);
    this._onWheel = this._handleWheel.bind(this);
    this._onKeyDown = this._handleKeyDown.bind(this);
    this._onTouchStart = this._handleTouchStart.bind(this);
    this._onTouchMove = this._handleTouchMove.bind(this);
    this._onTouchEnd = this._handleTouchEnd.bind(this);
    this._onContextMenu = (e) => e.preventDefault();

    const el = canvas.canvas;
    el.addEventListener('mousedown', this._onMouseDown);
    el.addEventListener('mousemove', this._onMouseMove);
    el.addEventListener('mouseup', this._onMouseUp);
    el.addEventListener('wheel', this._onWheel, { passive: false });
    el.addEventListener('contextmenu', this._onContextMenu);
    el.addEventListener('touchstart', this._onTouchStart, { passive: false });
    el.addEventListener('touchmove', this._onTouchMove, { passive: false });
    el.addEventListener('touchend', this._onTouchEnd);
    window.addEventListener('keydown', this._onKeyDown);
  }

  /** @private */
  _canvasXY(e) {
    const rect = this.canvas.canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  /** @private — Finds the topmost node at a screen position. */
  _nodeAtScreen(sx, sy) {
    const world = this.canvas.screenToWorld(sx, sy);
    const nodes = this.canvas.getNodes();
    for (let i = nodes.length - 1; i >= 0; i--) {
      if (nodes[i].hitTest(world.x, world.y)) return nodes[i];
    }
    return null;
  }

  /** @private — Finds a port at a screen position. */
  _portAtScreen(sx, sy) {
    const world = this.canvas.screenToWorld(sx, sy);
    for (const node of this.canvas.getNodes()) {
      for (const port of node.ports) {
        const pos = node.getPortPosition(port.id);
        if (port.hitTest(world.x, world.y, pos.x, pos.y)) {
          return { node, port, pos };
        }
      }
    }
    return null;
  }

  /** @private — Finds an edge at a screen position. */
  _edgeAtScreen(sx, sy) {
    const world = this.canvas.screenToWorld(sx, sy);
    for (const edge of this.canvas.getEdges()) {
      const srcNode = this.canvas._nodes.get(edge.sourceNodeId);
      const tgtNode = this.canvas._nodes.get(edge.targetNodeId);
      if (!srcNode || !tgtNode) continue;
      const srcPos = srcNode.getPortPosition(edge.sourcePortId);
      const tgtPos = tgtNode.getPortPosition(edge.targetPortId);
      if (edge.hitTest(world.x, world.y, srcPos, tgtPos)) return edge;
    }
    return null;
  }

  /** @private */
  _pushUndo(action) {
    this._undoStack.push(action);
    if (this._undoStack.length > 200) this._undoStack.shift();
    this._redoStack.length = 0;
  }

  /** @private */
  _selectNode(node, additive) {
    if (!additive) {
      for (const n of this._selectedNodes) n.setSelected(false);
      this._selectedNodes.clear();
    }
    if (node) {
      node.setSelected(true);
      this._selectedNodes.add(node);
    }
    if (this._onNodeSelect) this._onNodeSelect(Array.from(this._selectedNodes));
  }

  /** @private */
  _deselectAll() {
    for (const n of this._selectedNodes) n.setSelected(false);
    this._selectedNodes.clear();
    if (this._onNodeSelect) this._onNodeSelect([]);
  }

  /** @private */
  _handleMouseDown(e) {
    const pos = this._canvasXY(e);
    this._lastMouse = pos;

    // Middle mouse button panning
    if (e.button === 1) {
      this._panning = true;
      this._dragStart = pos;
      e.preventDefault();
      return;
    }

    if (e.button !== 0) return;

    // Check for port click → start connecting
    const portHit = this._portAtScreen(pos.x, pos.y);
    if (portHit && portHit.port.type === 'output') {
      this._connecting = true;
      this._connectSource = portHit;
      this._connectTempTarget = this.canvas.screenToWorld(pos.x, pos.y);
      return;
    }

    // Check for node click
    const node = this._nodeAtScreen(pos.x, pos.y);
    if (node) {
      const additive = e.shiftKey;
      if (!additive && !this._selectedNodes.has(node)) {
        this._selectNode(node, false);
      } else if (additive) {
        if (this._selectedNodes.has(node)) {
          node.setSelected(false);
          this._selectedNodes.delete(node);
        } else {
          this._selectNode(node, true);
        }
        return;
      }

      // Start drag
      this._dragging = true;
      this._dragStart = this.canvas.screenToWorld(pos.x, pos.y);
      this._dragNodeOffsets.clear();
      for (const n of this._selectedNodes) {
        this._dragNodeOffsets.set(n.id, { dx: n.x - this._dragStart.x, dy: n.y - this._dragStart.y });
      }
      return;
    }

    // Empty space: start pan or rubber-band
    if (e.shiftKey) {
      // Rubber-band selection
      this._rubberBand = { sx: pos.x, sy: pos.y, ex: pos.x, ey: pos.y };
    } else {
      this._deselectAll();
      this._panning = true;
      this._dragStart = pos;
    }
  }

  /** @private */
  _handleMouseMove(e) {
    const pos = this._canvasXY(e);

    // Update port hover states
    for (const node of this.canvas.getNodes()) {
      for (const port of node.ports) {
        const ppos = node.getPortPosition(port.id);
        const world = this.canvas.screenToWorld(pos.x, pos.y);
        port.hovered = port.hitTest(world.x, world.y, ppos.x, ppos.y);
      }
    }

    if (this._panning && this._dragStart) {
      const dx = pos.x - this._dragStart.x;
      const dy = pos.y - this._dragStart.y;
      this.canvas.transform.offsetX += dx;
      this.canvas.transform.offsetY += dy;
      this._dragStart = pos;
      return;
    }

    if (this._dragging && this._dragStart) {
      const world = this.canvas.screenToWorld(pos.x, pos.y);
      const gs = this.canvas.options.gridSize;
      for (const n of this._selectedNodes) {
        const off = this._dragNodeOffsets.get(n.id);
        if (!off) continue;
        let nx = world.x + off.dx;
        let ny = world.y + off.dy;
        if (gs > 0) {
          nx = Math.round(nx / gs) * gs;
          ny = Math.round(ny / gs) * gs;
        }
        n.setPosition(nx, ny);
      }
      return;
    }

    if (this._connecting) {
      this._connectTempTarget = this.canvas.screenToWorld(pos.x, pos.y);
      return;
    }

    if (this._rubberBand) {
      this._rubberBand.ex = pos.x;
      this._rubberBand.ey = pos.y;
      return;
    }

    this._lastMouse = pos;
  }

  /** @private */
  _handleMouseUp(e) {
    const pos = this._canvasXY(e);

    if (this._dragging) {
      // Record undo for move
      const moves = [];
      for (const n of this._selectedNodes) {
        moves.push({ id: n.id, x: n.x, y: n.y });
      }
      const prev = Array.from(this._dragNodeOffsets.entries()).map(([id, off]) => ({
        id,
        x: this._dragStart.x + off.dx,
        y: this._dragStart.y + off.dy,
      }));
      this._pushUndo({ type: 'move', nodes: moves, prev });
      if (this._onNodeMove) this._onNodeMove(Array.from(this._selectedNodes));
    }

    if (this._connecting && this._connectSource) {
      const portHit = this._portAtScreen(pos.x, pos.y);
      if (portHit && portHit.port.type === 'input' && portHit.node.id !== this._connectSource.node.id) {
        const edgeId = 'edge_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7);
        const edge = new MurphyEdge({
          id: edgeId,
          sourceNodeId: this._connectSource.node.id,
          sourcePortId: this._connectSource.port.id,
          targetNodeId: portHit.node.id,
          targetPortId: portHit.port.id,
        });
        this.canvas.addEdge(edge);
        this._connectSource.port.connected = true;
        portHit.port.connected = true;
        this._pushUndo({ type: 'addEdge', edge: edge });
        if (this._onEdgeCreate) this._onEdgeCreate(edge);
      }
    }

    if (this._rubberBand) {
      const rb = this._rubberBand;
      const minSx = Math.min(rb.sx, rb.ex);
      const minSy = Math.min(rb.sy, rb.ey);
      const maxSx = Math.max(rb.sx, rb.ex);
      const maxSy = Math.max(rb.sy, rb.ey);
      const worldMin = this.canvas.screenToWorld(minSx, minSy);
      const worldMax = this.canvas.screenToWorld(maxSx, maxSy);

      this._deselectAll();
      for (const node of this.canvas.getNodes()) {
        const b = node.getBounds();
        if (b.x + b.width >= worldMin.x && b.x <= worldMax.x && b.y + b.height >= worldMin.y && b.y <= worldMax.y) {
          node.setSelected(true);
          this._selectedNodes.add(node);
        }
      }
      if (this._onNodeSelect) this._onNodeSelect(Array.from(this._selectedNodes));
    }

    this._dragging = false;
    this._panning = false;
    this._connecting = false;
    this._connectSource = null;
    this._connectTempTarget = null;
    this._rubberBand = null;
    this._dragStart = null;
    this._dragNodeOffsets.clear();
  }

  /** @private */
  _handleWheel(e) {
    e.preventDefault();
    const pos = this._canvasXY(e);
    const delta = e.deltaY > 0 ? 0.92 : 1.08;
    const newScale = Math.max(0.25, Math.min(3.0, this.canvas.transform.scale * delta));
    const ratio = newScale / this.canvas.transform.scale;
    this.canvas.transform.offsetX = pos.x - (pos.x - this.canvas.transform.offsetX) * ratio;
    this.canvas.transform.offsetY = pos.y - (pos.y - this.canvas.transform.offsetY) * ratio;
    this.canvas.transform.scale = newScale;
  }

  /** @private */
  _handleKeyDown(e) {
    // Delete/Backspace — remove selected nodes and their edges
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (this._selectedNodes.size === 0) return;
      if (document.activeElement && document.activeElement.tagName === 'INPUT') return;
      e.preventDefault();
      const removed = { nodes: [], edges: [] };
      for (const node of this._selectedNodes) {
        // Collect connected edges
        for (const edge of this.canvas.getEdges()) {
          if (edge.sourceNodeId === node.id || edge.targetNodeId === node.id) {
            removed.edges.push(edge);
          }
        }
        removed.nodes.push(node);
      }
      removed.edges.forEach(ed => {
        this.canvas.removeEdge(ed.id);
        if (this._onEdgeDelete) this._onEdgeDelete(ed);
      });
      removed.nodes.forEach(nd => this.canvas.removeNode(nd.id));
      this._pushUndo({ type: 'delete', nodes: removed.nodes, edges: removed.edges });
      this._selectedNodes.clear();
      if (this._onNodeSelect) this._onNodeSelect([]);
      return;
    }

    // Ctrl+Z — Undo
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'z') {
      e.preventDefault();
      this._performUndo();
      return;
    }

    // Ctrl+Shift+Z — Redo
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
      e.preventDefault();
      this._performRedo();
      return;
    }

    // Ctrl+C — Copy
    if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
      if (this._selectedNodes.size === 0) return;
      this._clipboard = Array.from(this._selectedNodes).map(n => ({
        id: n.id, x: n.x, y: n.y, type: n.type, label: n.label,
        icon: n.icon, color: n.color, health: n.health, data: { ...n.data },
        ports: n.ports.map(p => ({ id: p.id, type: p.type, label: p.label, side: p.side })),
      }));
      this._pasteCounter = 0;
      return;
    }

    // Ctrl+V — Paste
    if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
      if (this._clipboard.length === 0) return;
      e.preventDefault();
      this._pasteCounter++;
      const offset = this._pasteCounter * 30;
      this._deselectAll();
      const idMap = new Map();
      this._clipboard.forEach(nd => {
        const newId = nd.id + '_copy_' + Date.now() + '_' + Math.random().toString(36).slice(2, 5);
        idMap.set(nd.id, newId);
        const newPorts = nd.ports.map(p => ({
          id: p.id + '_' + newId,
          type: p.type,
          label: p.label,
          side: p.side,
        }));
        const node = new MurphyNode({
          ...nd,
          id: newId,
          x: nd.x + offset,
          y: nd.y + offset,
          ports: newPorts,
        });
        this.canvas.addNode(node);
        node.setSelected(true);
        this._selectedNodes.add(node);
        this._pushUndo({ type: 'addNode', node });
      });
      if (this._onNodeSelect) this._onNodeSelect(Array.from(this._selectedNodes));
      return;
    }
  }

  /** @private */
  _performUndo() {
    if (this._undoStack.length === 0) return;
    const action = this._undoStack.pop();
    this._redoStack.push(action);

    switch (action.type) {
      case 'addNode':
        this.canvas.removeNode(action.node.id);
        break;
      case 'addEdge':
        this.canvas.removeEdge(action.edge.id);
        break;
      case 'delete':
        action.nodes.forEach(n => this.canvas.addNode(n));
        action.edges.forEach(e => this.canvas.addEdge(e));
        break;
      case 'move':
        if (action.prev) {
          action.prev.forEach(p => {
            const n = this.canvas._nodes.get(p.id);
            if (n) n.setPosition(p.x, p.y);
          });
        }
        break;
    }
  }

  /** @private */
  _performRedo() {
    if (this._redoStack.length === 0) return;
    const action = this._redoStack.pop();
    this._undoStack.push(action);

    switch (action.type) {
      case 'addNode':
        this.canvas.addNode(action.node);
        break;
      case 'addEdge':
        this.canvas.addEdge(action.edge);
        break;
      case 'delete':
        action.edges.forEach(e => this.canvas.removeEdge(e.id));
        action.nodes.forEach(n => this.canvas.removeNode(n.id));
        break;
      case 'move':
        if (action.nodes) {
          action.nodes.forEach(p => {
            const n = this.canvas._nodes.get(p.id);
            if (n) n.setPosition(p.x, p.y);
          });
        }
        break;
    }
  }

  /* ─── Touch event handlers ─────────────────────────────────────── */

  /** @private */
  _handleTouchStart(e) {
    e.preventDefault();
    this._touches = Array.from(e.touches);

    if (this._touches.length === 1) {
      const t = this._touches[0];
      const pos = this._touchXY(t);
      this._lastMouse = pos;
      this._longPressTriggered = false;

      // Start long-press timer for drag-to-move
      this._longPressTimer = setTimeout(() => {
        this._longPressTriggered = true;
        const node = this._nodeAtScreen(pos.x, pos.y);
        if (node) {
          this._selectNode(node, false);
          this._dragging = true;
          this._dragStart = this.canvas.screenToWorld(pos.x, pos.y);
          this._dragNodeOffsets.clear();
          for (const n of this._selectedNodes) {
            this._dragNodeOffsets.set(n.id, { dx: n.x - this._dragStart.x, dy: n.y - this._dragStart.y });
          }
        }
      }, 400);

      // Check tap on node for select
      const node = this._nodeAtScreen(pos.x, pos.y);
      if (node) {
        this._selectNode(node, false);
      }
    }

    if (this._touches.length === 2) {
      clearTimeout(this._longPressTimer);
      this._dragging = false;
      const t0 = this._touchXY(this._touches[0]);
      const t1 = this._touchXY(this._touches[1]);
      this._touchPanStart = { x: (t0.x + t1.x) / 2, y: (t0.y + t1.y) / 2 };
      this._touchPinchDist = Math.hypot(t1.x - t0.x, t1.y - t0.y);
      this._touchPinchScale = this.canvas.transform.scale;
    }
  }

  /** @private */
  _handleTouchMove(e) {
    e.preventDefault();
    this._touches = Array.from(e.touches);

    if (this._touches.length === 1 && this._dragging) {
      const pos = this._touchXY(this._touches[0]);
      const world = this.canvas.screenToWorld(pos.x, pos.y);
      const gs = this.canvas.options.gridSize;
      for (const n of this._selectedNodes) {
        const off = this._dragNodeOffsets.get(n.id);
        if (!off) continue;
        let nx = world.x + off.dx;
        let ny = world.y + off.dy;
        if (gs > 0) {
          nx = Math.round(nx / gs) * gs;
          ny = Math.round(ny / gs) * gs;
        }
        n.setPosition(nx, ny);
      }
      return;
    }

    if (this._touches.length === 1 && !this._longPressTriggered) {
      clearTimeout(this._longPressTimer);
      // Single-finger pan (if no node selected for drag)
      const pos = this._touchXY(this._touches[0]);
      const dx = pos.x - this._lastMouse.x;
      const dy = pos.y - this._lastMouse.y;
      this.canvas.transform.offsetX += dx;
      this.canvas.transform.offsetY += dy;
      this._lastMouse = pos;
      return;
    }

    if (this._touches.length === 2 && this._touchPanStart) {
      const t0 = this._touchXY(this._touches[0]);
      const t1 = this._touchXY(this._touches[1]);
      const mid = { x: (t0.x + t1.x) / 2, y: (t0.y + t1.y) / 2 };

      // Two-finger pan
      const dx = mid.x - this._touchPanStart.x;
      const dy = mid.y - this._touchPanStart.y;
      this.canvas.transform.offsetX += dx;
      this.canvas.transform.offsetY += dy;
      this._touchPanStart = mid;

      // Pinch zoom
      const dist = Math.hypot(t1.x - t0.x, t1.y - t0.y);
      if (this._touchPinchDist > 0) {
        const ratio = dist / this._touchPinchDist;
        const newScale = Math.max(0.25, Math.min(3.0, this._touchPinchScale * ratio));
        const scaleRatio = newScale / this.canvas.transform.scale;
        this.canvas.transform.offsetX = mid.x - (mid.x - this.canvas.transform.offsetX) * scaleRatio;
        this.canvas.transform.offsetY = mid.y - (mid.y - this.canvas.transform.offsetY) * scaleRatio;
        this.canvas.transform.scale = newScale;
      }
    }
  }

  /** @private */
  _handleTouchEnd(e) {
    clearTimeout(this._longPressTimer);

    if (this._dragging && this._selectedNodes.size > 0) {
      if (this._onNodeMove) this._onNodeMove(Array.from(this._selectedNodes));
    }

    this._dragging = false;
    this._longPressTriggered = false;
    this._touchPanStart = null;
    this._touchPinchDist = null;
    this._touchPinchScale = null;
    this._touches = Array.from(e.touches);

    if (this._touches.length === 0) {
      // Tap to select/deselect (only if it was a quick tap)
      // Handled in touchStart already
    }
  }

  /** @private */
  _touchXY(touch) {
    const rect = this.canvas.canvas.getBoundingClientRect();
    return { x: touch.clientX - rect.left, y: touch.clientY - rect.top };
  }

  /* ─── Custom rendering for interaction overlays ────────────────── */

  /**
   * Returns a draw function for the interaction layer (connecting line, rubber band).
   * Called internally by MurphyCanvas during render when interaction overlays exist.
   * @returns {Function|null}
   */
  getOverlayDrawFn() {
    const self = this;
    return function drawOverlay(ctx, transform) {
      // Draw temporary connection line
      if (self._connecting && self._connectSource && self._connectTempTarget) {
        const srcPos = self._connectSource.node.getPortPosition(self._connectSource.port.id);
        const sx = srcPos.x * transform.scale + transform.offsetX;
        const sy = srcPos.y * transform.scale + transform.offsetY;
        const tx = self._connectTempTarget.x * transform.scale + transform.offsetX;
        const ty = self._connectTempTarget.y * transform.scale + transform.offsetY;
        const cpOff = Math.max(40, Math.abs(tx - sx) * 0.4) * 1;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.bezierCurveTo(sx + cpOff, sy, tx - cpOff, ty, tx, ty);
        ctx.strokeStyle = '#4A90D9';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
      }

      // Draw rubber-band selection rectangle
      if (self._rubberBand) {
        const rb = self._rubberBand;
        ctx.save();
        ctx.strokeStyle = '#4A90D9';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        ctx.fillStyle = 'rgba(74, 144, 217, 0.08)';
        const x = Math.min(rb.sx, rb.ex);
        const y = Math.min(rb.sy, rb.ey);
        const w = Math.abs(rb.ex - rb.sx);
        const h = Math.abs(rb.ey - rb.sy);
        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);
        ctx.setLineDash([]);
        ctx.restore();
      }
    };
  }

  /**
   * Registers a callback fired when node selection changes.
   * @param {Function} callback — Receives array of selected MurphyNode instances
   */
  onNodeSelect(callback) {
    this._onNodeSelect = callback;
  }

  /**
   * Registers a callback fired when a node finishes being moved.
   * @param {Function} callback — Receives array of moved MurphyNode instances
   */
  onNodeMove(callback) {
    this._onNodeMove = callback;
  }

  /**
   * Registers a callback fired when a new edge is created via drag-connect.
   * @param {Function} callback — Receives the new MurphyEdge instance
   */
  onEdgeCreate(callback) {
    this._onEdgeCreate = callback;
  }

  /**
   * Registers a callback fired when an edge is deleted.
   * @param {Function} callback — Receives the deleted MurphyEdge instance
   */
  onEdgeDelete(callback) {
    this._onEdgeDelete = callback;
  }

  /**
   * Removes all event listeners and cleans up interaction state.
   */
  destroy() {
    const el = this.canvas.canvas;
    el.removeEventListener('mousedown', this._onMouseDown);
    el.removeEventListener('mousemove', this._onMouseMove);
    el.removeEventListener('mouseup', this._onMouseUp);
    el.removeEventListener('wheel', this._onWheel);
    el.removeEventListener('contextmenu', this._onContextMenu);
    el.removeEventListener('touchstart', this._onTouchStart);
    el.removeEventListener('touchmove', this._onTouchMove);
    el.removeEventListener('touchend', this._onTouchEnd);
    window.removeEventListener('keydown', this._onKeyDown);
    clearTimeout(this._longPressTimer);
    this._selectedNodes.clear();
    this._undoStack.length = 0;
    this._redoStack.length = 0;
    this._clipboard.length = 0;
    if (this.canvas) this.canvas.interaction = null;
  }
}

/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 6 — MURPHY AUTO-LAYOUT
 * ═══════════════════════════════════════════════════════════════════ */

class MurphyAutoLayout {
  /**
   * Provides automatic layout algorithms for a MurphyCanvas.
   * @param {MurphyCanvas} canvas — The MurphyCanvas instance to lay out
   */
  constructor(canvas) {
    this.canvas = canvas;
  }

  /**
   * Force-directed layout for system topology visualization.
   * Nodes repel each other, edges attract connected nodes, gravity pulls toward center.
   * Groups nodes by data.domain for clustering.
   * @param {Object} [options={}]
   * @param {number} [options.iterations=300]  — Simulation iterations
   * @param {number} [options.repulsion=500]   — Repulsion force strength
   * @param {number} [options.attraction=0.01] — Edge attraction strength
   * @param {number} [options.gravity=0.05]    — Center gravity strength
   * @param {number} [options.damping=0.9]     — Velocity damping factor
   */
  forceDirected(options = {}) {
    const opts = Object.assign({ iterations: 300, repulsion: 500, attraction: 0.01, gravity: 0.05, damping: 0.9 }, options);
    const nodes = this.canvas.getNodes();
    const edges = this.canvas.getEdges();
    if (nodes.length === 0) return;

    // Initialize velocity and capture positions
    const state = new Map();
    nodes.forEach(n => {
      state.set(n.id, { x: n.x, y: n.y, vx: 0, vy: 0 });
    });

    // Compute domain cluster centers for grouping
    const domains = new Map();
    nodes.forEach(n => {
      const d = (n.data && n.data.domain) || '__default__';
      if (!domains.has(d)) domains.set(d, []);
      domains.get(d).push(n.id);
    });
    const domainCenters = new Map();
    let dIdx = 0;
    const dCount = domains.size;
    for (const [domain, ids] of domains) {
      const angle = (2 * Math.PI * dIdx) / Math.max(dCount, 1);
      const clusterRadius = Math.max(200, nodes.length * 15);
      domainCenters.set(domain, {
        x: Math.cos(angle) * clusterRadius,
        y: Math.sin(angle) * clusterRadius,
      });
      dIdx++;
    }

    // Build adjacency for attraction
    const adjSet = new Set();
    edges.forEach(e => adjSet.add(e.sourceNodeId + ':' + e.targetNodeId));

    const finalPositions = new Map();

    for (let iter = 0; iter < opts.iterations; iter++) {
      // Repulsion between all node pairs
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = state.get(nodes[i].id);
          const b = state.get(nodes[j].id);
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = opts.repulsion / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          a.vx += fx;
          a.vy += fy;
          b.vx -= fx;
          b.vy -= fy;
        }
      }

      // Attraction along edges
      edges.forEach(e => {
        const a = state.get(e.sourceNodeId);
        const b = state.get(e.targetNodeId);
        if (!a || !b) return;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = opts.attraction * dist;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      });

      // Gravity toward center and domain clustering
      nodes.forEach(n => {
        const s = state.get(n.id);
        const domain = (n.data && n.data.domain) || '__default__';
        const center = domainCenters.get(domain) || { x: 0, y: 0 };
        s.vx += (center.x - s.x) * opts.gravity;
        s.vy += (center.y - s.y) * opts.gravity;
        // General center gravity
        s.vx -= s.x * opts.gravity * 0.3;
        s.vy -= s.y * opts.gravity * 0.3;
      });

      // Apply velocity with damping
      nodes.forEach(n => {
        const s = state.get(n.id);
        s.vx *= opts.damping;
        s.vy *= opts.damping;
        s.x += s.vx;
        s.y += s.vy;
      });
    }

    // Animate nodes to final positions over ~1 second
    nodes.forEach(n => finalPositions.set(n.id, { x: state.get(n.id).x, y: state.get(n.id).y }));
    this._animateToPositions(finalPositions, 1000);
  }

  /**
   * Directed acyclic graph (DAG) layout for workflow canvases.
   * Arranges nodes in layers using topological sort with edge-crossing minimization.
   * @param {Object} [options={}]
   * @param {'LR'|'TB'} [options.direction='LR'] — Layout direction
   * @param {number}    [options.layerSpacing=250] — Spacing between layers
   * @param {number}    [options.nodeSpacing=100]  — Spacing between nodes in a layer
   */
  dagLayout(options = {}) {
    const opts = Object.assign({ direction: 'LR', layerSpacing: 250, nodeSpacing: 100 }, options);
    const nodes = this.canvas.getNodes();
    const edges = this.canvas.getEdges();
    if (nodes.length === 0) return;

    const nodeMap = new Map();
    nodes.forEach(n => nodeMap.set(n.id, n));

    // Build adjacency lists
    const outgoing = new Map();
    const incoming = new Map();
    nodes.forEach(n => {
      outgoing.set(n.id, []);
      incoming.set(n.id, []);
    });
    edges.forEach(e => {
      if (outgoing.has(e.sourceNodeId) && incoming.has(e.targetNodeId)) {
        outgoing.get(e.sourceNodeId).push(e.targetNodeId);
        incoming.get(e.targetNodeId).push(e.sourceNodeId);
      }
    });

    // Topological sort (Kahn's algorithm) to assign layers
    const inDegree = new Map();
    nodes.forEach(n => inDegree.set(n.id, incoming.get(n.id).length));
    const queue = [];
    for (const [id, deg] of inDegree) {
      if (deg === 0) queue.push(id);
    }

    const layerAssignment = new Map();
    while (queue.length > 0) {
      const id = queue.shift();
      const parentLayers = incoming.get(id).map(pid => layerAssignment.get(pid) || 0);
      const layer = parentLayers.length > 0 ? Math.max(...parentLayers) + 1 : 0;
      layerAssignment.set(id, layer);
      for (const child of outgoing.get(id)) {
        inDegree.set(child, inDegree.get(child) - 1);
        if (inDegree.get(child) === 0) queue.push(child);
      }
    }

    // Handle nodes not reached (cycles or disconnected) — assign to layer 0
    nodes.forEach(n => {
      if (!layerAssignment.has(n.id)) layerAssignment.set(n.id, 0);
    });

    // Group nodes by layer
    const layers = new Map();
    for (const [id, layer] of layerAssignment) {
      if (!layers.has(layer)) layers.set(layer, []);
      layers.get(layer).push(id);
    }

    // Minimize edge crossings: order nodes within each layer by barycenter of connected nodes
    const sortedLayerKeys = Array.from(layers.keys()).sort((a, b) => a - b);
    for (let li = 1; li < sortedLayerKeys.length; li++) {
      const layerKey = sortedLayerKeys[li];
      const prevLayerKey = sortedLayerKeys[li - 1];
      const prevOrder = new Map();
      layers.get(prevLayerKey).forEach((id, idx) => prevOrder.set(id, idx));

      layers.get(layerKey).sort((aId, bId) => {
        const aParents = incoming.get(aId).filter(p => prevOrder.has(p));
        const bParents = incoming.get(bId).filter(p => prevOrder.has(p));
        const aCenter = aParents.length > 0 ? aParents.reduce((s, p) => s + prevOrder.get(p), 0) / aParents.length : 0;
        const bCenter = bParents.length > 0 ? bParents.reduce((s, p) => s + prevOrder.get(p), 0) / bParents.length : 0;
        return aCenter - bCenter;
      });
    }

    // Compute final positions
    const finalPositions = new Map();
    for (const [layerIdx, nodeIds] of layers) {
      nodeIds.forEach((id, posInLayer) => {
        const node = nodeMap.get(id);
        if (!node) return;
        if (opts.direction === 'LR') {
          finalPositions.set(id, {
            x: layerIdx * opts.layerSpacing,
            y: posInLayer * opts.nodeSpacing - (nodeIds.length - 1) * opts.nodeSpacing / 2,
          });
        } else {
          finalPositions.set(id, {
            x: posInLayer * opts.nodeSpacing - (nodeIds.length - 1) * opts.nodeSpacing / 2,
            y: layerIdx * opts.layerSpacing,
          });
        }
      });
    }

    this._animateToPositions(finalPositions, 800);
  }

  /**
   * Places all nodes in a circle. Useful as a quick fallback layout.
   */
  arrangeCircular() {
    const nodes = this.canvas.getNodes();
    if (nodes.length === 0) return;
    const radius = Math.max(150, nodes.length * 40);
    const finalPositions = new Map();
    nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      finalPositions.set(n.id, {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      });
    });
    this._animateToPositions(finalPositions, 600);
  }

  /**
   * Smoothly animates nodes from current positions to target positions.
   * @private
   * @param {Map<string, {x: number, y: number}>} targetPositions
   * @param {number} durationMs — Animation duration in milliseconds
   */
  _animateToPositions(targetPositions, durationMs) {
    const nodes = this.canvas.getNodes();
    const startPositions = new Map();
    nodes.forEach(n => startPositions.set(n.id, { x: n.x, y: n.y }));
    const startTime = performance.now();

    const step = (now) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / durationMs);
      // Ease-out cubic
      const ease = 1 - Math.pow(1 - t, 3);

      for (const n of nodes) {
        const start = startPositions.get(n.id);
        const end = targetPositions.get(n.id);
        if (!start || !end) continue;
        n.setPosition(
          start.x + (end.x - start.x) * ease,
          start.y + (end.y - start.y) * ease
        );
      }

      if (t < 1) {
        requestAnimationFrame(step);
      }
    };

    requestAnimationFrame(step);
  }
}

/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 7 — EXPORTS
 * ═══════════════════════════════════════════════════════════════════ */

/* ES module export — only when loaded as type="module" */
try {
  if (typeof globalThis !== 'undefined' && typeof globalThis[Symbol.for('murphy-canvas-exported')] === 'undefined') {
    globalThis[Symbol.for('murphy-canvas-exported')] = true;
  }
} catch (_) { /* non-module context */ }

window.MurphyCanvas = MurphyCanvas;
window.MurphyNode = MurphyNode;
window.MurphyEdge = MurphyEdge;
window.MurphyPort = MurphyPort;
window.MurphyCanvasInteraction = MurphyCanvasInteraction;
window.MurphyAutoLayout = MurphyAutoLayout;
