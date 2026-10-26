// Busca e filtro por categoria na página inicial. Sem JS, todos os cards aparecem.
const root = document.querySelector<HTMLElement>('[data-explore]');

if (root) {
  const input = root.querySelector<HTMLInputElement>('input[type="search"]');
  const chips = Array.from(root.querySelectorAll<HTMLButtonElement>('[data-filter]'));
  const cards = Array.from(root.querySelectorAll<HTMLElement>('[data-card]'));
  const empty = root.querySelector<HTMLElement>('[data-empty]');
  const counter = root.querySelector<HTMLElement>('[data-count]');

  const norm = (s: string) =>
    s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

  const params = new URLSearchParams(location.search);
  let query = params.get('q') ?? '';
  let category = params.get('categoria') ?? 'todas';
  if (!chips.some((c) => c.dataset.filter === category)) category = 'todas';
  if (input) input.value = query;

  function apply(): void {
    const terms = norm(query).split(/\s+/).filter(Boolean);
    let visible = 0;
    for (const card of cards) {
      const okCat = category === 'todas' || card.dataset.category === category;
      const text = card.dataset.search ?? '';
      const ok = okCat && terms.every((t) => text.includes(t));
      card.hidden = !ok;
      if (ok) visible++;
    }
    for (const chip of chips) chip.setAttribute('aria-pressed', String(chip.dataset.filter === category));
    if (empty) empty.hidden = visible > 0;
    if (counter) counter.textContent = `${visible} ${visible === 1 ? 'conjunto de dados' : 'conjuntos de dados'}`;

    const url = new URL(location.href);
    query ? url.searchParams.set('q', query) : url.searchParams.delete('q');
    category !== 'todas' ? url.searchParams.set('categoria', category) : url.searchParams.delete('categoria');
    history.replaceState(null, '', url);
  }

  input?.addEventListener('input', () => {
    query = input.value;
    apply();
  });
  for (const chip of chips) {
    chip.addEventListener('click', () => {
      category = chip.dataset.filter ?? 'todas';
      apply();
    });
  }
  apply();
}

export {};
