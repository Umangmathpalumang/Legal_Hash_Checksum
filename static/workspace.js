'use strict';

const workspaceSidebar = document.querySelector('#sidebar');
const workspaceTrigger = document.querySelector('.hamburger');
if (workspaceSidebar && workspaceTrigger) {
  const narrow = matchMedia('(max-width: 768px)');
  const closeMenu = workspaceSidebar.querySelector('.workspace-close');
  const workspaceContent = document.querySelector('.main-content');
  const bottomNav = document.querySelector('.bnav');
  let wasOpen = false;
  function updateNavigation() {
    const open = narrow.matches && workspaceSidebar.classList.contains('open');
    workspaceTrigger.setAttribute('aria-expanded', String(open));
    workspaceSidebar.inert = narrow.matches && !open;
    if (workspaceContent) workspaceContent.inert = open;
    if (bottomNav) bottomNav.inert = open;
    if (open && !wasOpen) closeMenu?.focus();
    if (!open && wasOpen && narrow.matches) workspaceTrigger.focus();
    wasOpen = open;
  }
  closeMenu?.addEventListener('click', () => window.closeSidebar());
  narrow.addEventListener('change', () => {
    if (!narrow.matches && workspaceSidebar.classList.contains('open')) window.closeSidebar();
    updateNavigation();
  });
  new MutationObserver(updateNavigation).observe(workspaceSidebar, {attributes: true, attributeFilter: ['class']});
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && wasOpen) window.closeSidebar();
  });
  updateNavigation();
}

const caseSearch = document.querySelector('#workspace-case-search');
caseSearch?.addEventListener('submit', event => {
  event.preventDefault();
  try {
    sessionStorage.setItem('lhc-case-search-once', caseSearch.querySelector('input').value.trim());
  } catch { /* The case list remains available when storage is blocked. */ }
  location.assign('/cases');
});

if (document.body.classList.contains('lhc-cases')) {
  let pending;
  try {
    pending = sessionStorage.getItem('lhc-case-search-once');
    sessionStorage.removeItem('lhc-case-search-once');
  } catch { /* Search can still run directly from the case list. */ }
  if (pending) {
    document.querySelector('#gSearch').value = pending;
    window.globalSearch(pending);
  }
  if (location.hash === '#new') {
    history.replaceState(null, '', location.pathname + location.search);
    window.openModal();
    document.querySelector('#f_cn')?.focus();
  }
}
