'use strict';

const directorySearch = document.querySelector('#directory-search');
const query = document.querySelector('#tool-query');
const clear = document.querySelector('#clear-query');
const filters = document.querySelector('.directory-filters');
const buttons = [...filters.querySelectorAll('[data-filter]')];
const cards = [...document.querySelectorAll('.directory-card')].map(card => ({
  card,
  terms: (card.textContent + ' ' + card.dataset.keywords).toLowerCase(),
}));
const empty = document.querySelector('#directory-empty');
const dialog = document.querySelector('#feedback-dialog');
let category = 'all';

function readFilters() {
  const params = new URLSearchParams(location.search);
  const initial = params.get('category');
  category = buttons.some(button => button.dataset.filter === initial) ? initial : 'all';
  query.value = (params.get('q') || '').slice(0, 120);
}

function renderFilters(sync = true) {
  const search = query.value.trim().toLowerCase();
  const terms = search.split(/\s+/).filter(Boolean);
  let count = 0;
  cards.forEach(({card, terms: searchable}) => {
    const show = (category === 'all' || card.dataset.category === category) && terms.every(term => searchable.includes(term));
    card.hidden = !show;
    if (show) count++;
  });
  buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === category)));
  const active = buttons.find(button => button.dataset.filter === category);
  document.querySelector('#results-heading').textContent = search ? 'Search results' : active.textContent;
  document.querySelector('#result-count').textContent = count + (count === 1 ? ' tool' : ' tools');
  clear.hidden = query.value.length === 0;
  empty.hidden = count !== 0;
  if (sync) {
    const next = new URL(location.href);
    if (category === 'all') next.searchParams.delete('category');
    else next.searchParams.set('category', category);
    if (search) next.searchParams.set('q', query.value.trim());
    else next.searchParams.delete('q');
    if (next.href !== location.href) history.replaceState(null, '', next);
  }
}

query.maxLength = 120;
directorySearch.hidden = false;
filters.hidden = false;
readFilters();
renderFilters(false);
query.addEventListener('input', () => renderFilters());
clear.addEventListener('click', () => { query.value = ''; renderFilters(); query.focus(); });
buttons.forEach(button => {
  button.addEventListener('click', () => { category = button.dataset.filter; renderFilters(); });
});
document.querySelector('#reset-tools').addEventListener('click', () => {
  category = 'all';
  query.value = '';
  renderFilters();
  query.focus();
});
window.addEventListener('popstate', () => { readFilters(); renderFilters(false); });
document.addEventListener('keydown', event => {
  if (event.defaultPrevented || dialog.open) return;
  const inField = event.target.closest?.('input,textarea,select,[contenteditable]');
  if ((event.key === '/' && !inField && !event.metaKey && !event.ctrlKey && !event.altKey)
      || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k')) {
    event.preventDefault();
    query.focus();
    query.select();
  }
});

const feedbackOpen = document.querySelector('#feedback-open');
if (typeof dialog.showModal === 'function') {
  feedbackOpen.hidden = false;
  feedbackOpen.addEventListener('click', () => dialog.showModal());
  document.querySelector('#feedback-close').addEventListener('click', () => dialog.close());
  const form = document.querySelector('#feedback-form');
  const submit = form.querySelector('button[type="submit"]');
  const status = document.querySelector('#feedback-status');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const data = new FormData(form);
    const message = data.get('message').trim();
    if (!message) {
      status.textContent = 'Please enter a message.';
      return;
    }
    submit.disabled = true;
    status.textContent = 'Sending…';
    try {
      const response = await fetch('/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          type: data.get('type'), page: 'Tools', message,
          email: data.get('email').trim(), url: location.origin + location.pathname,
        }),
      });
      if (!response.ok || !(await response.json()).ok) throw new Error();
      form.reset();
      status.textContent = 'Thanks. Your feedback was sent.';
    } catch {
      status.textContent = 'Could not send feedback. Please try again or contact support.';
    } finally {
      submit.disabled = false;
    }
  });
}
