// Motion da página: entrada de blocos ao rolar, contagem até o valor dos indicadores,
// rotação dos destaques e "reproduzir" animações. Com "reduzir movimento" ativo no
// sistema, nada anima: tudo já está no estado final no HTML.
import { formatValue } from '../lib/format';
import type { Fmt } from '../lib/types';

const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const hasIO = 'IntersectionObserver' in window;

function onVisible(nodes: Iterable<Element>, cb: (el: HTMLElement) => void, threshold = 0.15): void {
  const list = Array.from(nodes) as HTMLElement[];
  if (!list.length) return;
  if (!hasIO) {
    list.forEach(cb);
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        io.unobserve(e.target);
        cb(e.target as HTMLElement);
      }
    },
    { threshold, rootMargin: '0px 0px -5% 0px' },
  );
  list.forEach((n) => io.observe(n));
}

// Atrasos/durações por elemento vêm de data-atributos (estilo inline é bloqueado pela CSP).
document.querySelectorAll<HTMLElement | SVGElement>('[data-anim-delay], [data-anim-dur]').forEach((el) => {
  if (el.dataset.animDelay) el.style.animationDelay = el.dataset.animDelay;
  if (el.dataset.animDur) el.style.animationDuration = el.dataset.animDur;
});

// Blocos entram ao aparecer (o CSS só esconde quando há JS e movimento permitido).
if (!reduce) {
  onVisible(document.querySelectorAll('.reveal'), (el) => el.classList.add('is-in'));
} else {
  document.querySelectorAll('.reveal').forEach((el) => el.classList.add('is-in'));
}

// Contagem até o valor (900 ms, desaceleração cúbica); termina no texto exato do build.
function countUp(el: HTMLElement): void {
  const final = el.textContent ?? '';
  let data: { v: number; f: Fmt };
  try {
    data = JSON.parse(el.dataset.countup ?? '');
  } catch {
    return;
  }
  const start = performance.now();
  const step = (now: number) => {
    const p = Math.min(1, (now - start) / 900);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = p < 1 ? formatValue(data.v * eased, data.f, { unit: false }) : final;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
if (!reduce) onVisible(document.querySelectorAll('[data-countup]'), countUp, 0.6);

// Faixa de destaques: um por vez, troca a cada 4,5 s; pausa com o mouse em cima ou com foco.
document.querySelectorAll<HTMLElement>('[data-ticker]').forEach((box) => {
  const items = Array.from(box.querySelectorAll<HTMLElement>('[data-ticker-item]'));
  if (items.length < 2 || reduce) return;
  let i = 0;
  let paused = false;
  box.addEventListener('mouseenter', () => (paused = true));
  box.addEventListener('mouseleave', () => (paused = false));
  box.addEventListener('focusin', () => (paused = true));
  box.addEventListener('focusout', () => (paused = false));
  window.setInterval(() => {
    if (paused || document.hidden) return;
    items[i].classList.remove('is-on');
    i = (i + 1) % items.length;
    items[i].classList.add('is-on');
  }, 4500);
});

// "Reproduzir": reinicia as animações de um bloco (ex.: linha do tempo da execução).
document.querySelectorAll<HTMLButtonElement>('[data-replay]').forEach((btn) => {
  const target = document.getElementById(btn.dataset.replay ?? '');
  if (!target) return;
  btn.addEventListener('click', () => {
    target.classList.remove('play');
    void target.getBoundingClientRect(); // força o recálculo para a animação recomeçar
    target.classList.add('play');
  });
});
