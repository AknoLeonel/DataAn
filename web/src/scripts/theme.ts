// Alterna tema claro/escuro e lembra a escolha (preferência local, não é rastreamento).
const KEY = 'dataan-theme';
const root = document.documentElement;

// O escuro é o padrão do site; o claro é uma escolha explícita.
function current(): 'light' | 'dark' {
  return root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

for (const btn of document.querySelectorAll<HTMLButtonElement>('[data-theme-toggle]')) {
  btn.addEventListener('click', () => {
    const next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* armazenamento indisponível: vale só para esta visita */
    }
    document.dispatchEvent(new CustomEvent('dataan:theme'));
  });
}

// Fecha o menu móvel ao clicar fora ou pressionar Esc.
const menu = document.querySelector<HTMLDetailsElement>('details.menu');
if (menu) {
  document.addEventListener('click', (e) => {
    if (menu.open && !menu.contains(e.target as Node)) menu.open = false;
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && menu.open) {
      menu.open = false;
      menu.querySelector('summary')?.focus();
    }
  });
}

export {};
