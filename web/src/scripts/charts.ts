// Interatividade dos gráficos: redesenha na largura real do contêiner, anima a entrada
// quando o gráfico aparece na tela e adiciona tooltip, crosshair, toque, teclado,
// troca de período e destaques ligados ao texto. Sem dependências.
import { render, sliceYears, type Focus, type Rendered } from '../lib/charts';
import type { SingleChart } from '../lib/types';

const SVGNS = 'http://www.w3.org/2000/svg';
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text; // rótulos vêm de dados: nunca innerHTML
  return node;
}

function readJson<T>(root: HTMLElement, selector: string): T | null {
  const node = root.querySelector<HTMLScriptElement>(selector);
  if (!node) return null;
  try {
    return JSON.parse(node.textContent || '') as T;
  } catch {
    return null;
  }
}

/** Barras entram em cascata: atraso por posição (via CSSOM, permitido pela CSP). */
function stagger(svg: SVGSVGElement): void {
  const bars = svg.querySelectorAll<SVGElement>('.bar');
  const step = Math.min(40, 700 / Math.max(1, bars.length));
  bars.forEach((b, i) => (b.style.animationDelay = `${Math.round(i * step)}ms`));
}

function setup(fig: HTMLElement): void {
  const spec = readJson<SingleChart>(fig, 'script[data-spec]');
  const canvas = fig.querySelector<HTMLElement>('.viz-canvas');
  if (!spec || !canvas) return;
  const highlights = readJson<Focus[]>(fig, 'script[data-highlights]') ?? [];
  // Painel de pequenos múltiplos vira gráfico completo quando é o único visível.
  const isCompact = () => fig.dataset.compact === '1' && !fig.closest('.is-single');

  const tip = el('div', 'viz-tip');
  tip.hidden = true;
  tip.setAttribute('aria-hidden', 'true');
  fig.appendChild(tip);
  const live = el('div', 'sr-only');
  live.setAttribute('aria-live', 'polite');
  fig.appendChild(live);

  let rendered: Rendered | null = null;
  let svg: SVGSVGElement | null = null;
  let overlay: SVGGElement | null = null;
  let lastW = 0;
  let active = -1;
  let years: number | null = null;
  let focusIdx = highlights.length ? 0 : -1;
  let animateNext = false;
  // Até entrar na tela, fica o SVG do build; a primeira renderização no navegador já é animada.
  let pending = !reduceMotion && 'IntersectionObserver' in window;

  const count = () => {
    const it = rendered?.interaction;
    if (!it) return 0;
    return it.kind === 'x' ? it.xs.length : it.bands.length;
  };

  function draw(force = false): void {
    if (pending) return;
    const w = Math.round(canvas!.clientWidth);
    if (!w || (!force && Math.abs(w - lastW) < 2)) return;
    lastW = w;
    const animate = animateNext && !reduceMotion;
    animateNext = false;
    rendered = render(sliceYears(spec!, years), w, { compact: isCompact(), animate, focus: focusIdx >= 0 ? highlights[focusIdx] : null });
    canvas!.innerHTML = rendered.svg; // SVG gerado por nós, com textos escapados
    svg = canvas!.querySelector('svg');
    overlay = null;
    if (animate && svg) stagger(svg);
    if (active >= 0 && active < count()) show(active, false);
    else hide();
  }

  // Períodos (1A, 5A, 10A, Máx)
  const rangeBtns = Array.from(fig.querySelectorAll<HTMLButtonElement>('[data-range]'));
  const yearsOf = (b: HTMLButtonElement) => (b.dataset.range === 'all' ? null : Number(b.dataset.range));
  function setRange(y: number | null): void {
    years = y;
    rangeBtns.forEach((b) => b.setAttribute('aria-pressed', String(yearsOf(b) === y)));
  }
  rangeBtns.forEach((b) =>
    b.addEventListener('click', () => {
      setRange(yearsOf(b));
      active = -1;
      animateNext = true;
      draw(true);
    }),
  );

  // Destaques: escolher um texto marca no gráfico o trecho de onde ele vem.
  const hlBtns = Array.from(fig.querySelectorAll<HTMLButtonElement>('[data-hl]'));
  function pick(i: number): void {
    if (i === focusIdx) return;
    focusIdx = i;
    hlBtns.forEach((b, j) => b.setAttribute('aria-pressed', String(j === i)));
    if (years !== null) {
      const shown = sliceYears(spec!, years);
      const first = Math.min(...(shown.type === 'line' ? shown.series.flatMap((s) => s.points.map(([d]) => Date.parse(d))) : [0]));
      if (Date.parse(highlights[i].start) < first) setRange(null);
    }
    draw(true);
  }
  hlBtns.forEach((b, i) => {
    b.addEventListener('click', () => pick(i));
    b.addEventListener('mouseenter', () => pick(i));
    b.addEventListener('focus', () => pick(i));
  });

  function toLocal(e: PointerEvent): { x: number; y: number } | null {
    if (!svg) return null;
    const r = svg.getBoundingClientRect();
    const k = lastW / r.width;
    return { x: (e.clientX - r.left) * k, y: (e.clientY - r.top) * k };
  }

  function nearest(p: { x: number; y: number }): number {
    const it = rendered?.interaction;
    if (!it) return -1;
    if (it.kind === 'x') {
      if (p.x < it.plot.left - 24 || p.x > it.plot.right + 24) return -1;
      let lo = 0;
      let hi = it.xs.length - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (it.xs[mid] < p.x) lo = mid;
        else hi = mid;
      }
      return Math.abs(it.xs[lo] - p.x) <= Math.abs(it.xs[hi] - p.x) ? lo : hi;
    }
    const v = it.orientation === 'horizontal' ? p.y : p.x;
    return it.bands.findIndex((b) => v >= b.from && v < b.to);
  }

  function ensureOverlay(): SVGGElement {
    if (overlay && svg?.contains(overlay)) return overlay;
    overlay = document.createElementNS(SVGNS, 'g');
    overlay.setAttribute('class', 'hover');
    svg!.appendChild(overlay);
    return overlay;
  }

  function show(i: number, announce: boolean): void {
    const it = rendered?.interaction;
    if (!it || !svg) return;
    active = i;
    let ax: number;
    let ay: number;
    if (it.kind === 'x') {
      const g = ensureOverlay();
      g.replaceChildren();
      g.removeAttribute('visibility');
      const x = it.xs[i];
      const line = document.createElementNS(SVGNS, 'line');
      line.setAttribute('class', 'crosshair');
      line.setAttribute('x1', String(x));
      line.setAttribute('x2', String(x));
      line.setAttribute('y1', String(it.plot.top));
      line.setAttribute('y2', String(it.plot.bottom));
      g.appendChild(line);
      const dots = it.dots(i);
      for (const d of dots) {
        const c = document.createElementNS(SVGNS, 'circle');
        c.setAttribute('class', `hover-dot ${d.color}`);
        c.setAttribute('cx', String(x));
        c.setAttribute('cy', String(d.y));
        c.setAttribute('r', '5');
        g.appendChild(c);
      }
      ax = x;
      ay = dots.length ? Math.min(...dots.map((d) => d.y)) : it.plot.top;
    } else {
      svg.querySelectorAll('.bar.is-active').forEach((b) => b.classList.remove('is-active'));
      svg.querySelector(`.bar[data-i="${i}"]`)?.classList.add('is-active');
      ax = it.bands[i].anchorX;
      ay = it.bands[i].anchorY;
    }

    const title = it.title(i);
    const rows = it.rows(i);
    const list = el('ul');
    for (const r of rows) {
      const li = el('li');
      const key = el('span', `key key-line ${r.color}${r.dashed ? ' dashed' : ''}`);
      li.append(key, el('strong', undefined, r.value));
      if (r.name) li.append(el('span', 'name', r.name));
      list.appendChild(li);
    }
    tip.replaceChildren(el('div', 'viz-tip-title', title), list);
    tip.hidden = false;

    const sr = svg.getBoundingClientRect();
    const fr = fig.getBoundingClientRect();
    const k = sr.width / lastW;
    const px = sr.left - fr.left + ax * k;
    const py = sr.top - fr.top + ay * k;
    const tw = tip.offsetWidth;
    const th = tip.offsetHeight;
    let left = px + 14;
    if (left + tw > fr.width) left = px - 14 - tw;
    if (left < 0) left = Math.max(0, Math.min(fr.width - tw, px - tw / 2));
    let top = py - th - 12;
    if (top < 0) top = py + 16;
    tip.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;

    if (announce) live.textContent = `${title}: ${rows.map((r) => `${r.name ? r.name + ' ' : ''}${r.value}`).join('; ')}`;
  }

  function hide(): void {
    active = -1;
    tip.hidden = true;
    overlay?.setAttribute('visibility', 'hidden');
    svg?.querySelectorAll('.bar.is-active').forEach((b) => b.classList.remove('is-active'));
  }

  const onPointer = (e: PointerEvent) => {
    const p = toLocal(e);
    const i = p ? nearest(p) : -1;
    if (i >= 0) show(i, false);
    else hide();
  };
  canvas.addEventListener('pointermove', onPointer);
  canvas.addEventListener('pointerdown', onPointer);
  canvas.addEventListener('pointerleave', (e) => {
    if (e.pointerType === 'mouse') hide();
  });
  document.addEventListener('pointerdown', (e) => {
    if (active >= 0 && !fig.contains(e.target as Node)) hide();
  });
  canvas.addEventListener('focus', () => {
    if (active < 0 && count()) show(count() - 1, true);
  });
  canvas.addEventListener('blur', hide);
  canvas.addEventListener('keydown', (e) => {
    const n = count();
    if (!n) return;
    const it = rendered!.interaction;
    const fwd = it.kind === 'band' && it.orientation === 'horizontal' ? 'ArrowDown' : 'ArrowRight';
    const back = it.kind === 'band' && it.orientation === 'horizontal' ? 'ArrowUp' : 'ArrowLeft';
    let next = active < 0 ? n - 1 : active;
    if (e.key === fwd) next = Math.min(n - 1, next + 1);
    else if (e.key === back) next = Math.max(0, next - 1);
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = n - 1;
    else if (e.key === 'Escape') {
      hide();
      return;
    } else return;
    e.preventDefault();
    show(next, true);
  });

  if (pending) {
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        pending = false;
        animateNext = true;
        draw(true);
      },
      { threshold: 0.2 },
    );
    io.observe(canvas);
  }
  new ResizeObserver(() => draw()).observe(canvas);
  draw();
}

// Pequenos múltiplos: escolher uma entidade (ex.: uma capital) mostra só o painel dela, maior.
function setupGridFilter(root: HTMLElement): void {
  const grid = root.querySelector<HTMLElement>('.viz-grid');
  const buttons = Array.from(root.querySelectorAll<HTMLButtonElement>('[data-panel-filter]'));
  if (!grid || !buttons.length) return;
  buttons.forEach((b) =>
    b.addEventListener('click', () => {
      const id = b.dataset.panelFilter!;
      buttons.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      grid.classList.toggle('is-single', id !== 'todas');
      grid.querySelectorAll<HTMLElement>('[data-panel]').forEach((p) => (p.hidden = id !== 'todas' && p.dataset.panel !== id));
    }),
  );
}

document.querySelectorAll<HTMLElement>('figure[data-chart]').forEach(setup);
document.querySelectorAll<HTMLElement>('[data-grid]').forEach(setupGridFilter);
