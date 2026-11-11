'use strict';

document.querySelectorAll('.site-menu').forEach(menu => {
  menu.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu.open) {
      menu.open = false;
      menu.querySelector('summary').focus();
    }
  });
  menu.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => { menu.open = false; });
  });
  document.addEventListener('click', event => {
    if (menu.open && !menu.contains(event.target)) menu.open = false;
  });
});

document.querySelectorAll('.preview-tabs').forEach(group => {
  const tabs = [...group.querySelectorAll('[role="tab"]')];
  function select(index, moveFocus = false) {
    tabs.forEach((tab, position) => {
      const selected = position === index;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
    });
    if (moveFocus) tabs[index].focus();
  }
  tabs.forEach((tab, position) => {
    tab.addEventListener('click', () => select(position));
    tab.addEventListener('keydown', event => {
      const direction = {ArrowLeft: -1, ArrowRight: 1}[event.key];
      if (direction) {
        event.preventDefault();
        select((position + direction + tabs.length) % tabs.length, true);
      } else if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault();
        select(event.key === 'Home' ? 0 : tabs.length - 1, true);
      }
    });
  });
});

const runSample = document.querySelector('#sample-run');
if (runSample) {
  runSample.addEventListener('click', async () => {
    const status = document.querySelector('#sample-status');
    const fingerprint = document.querySelector('#sample-hash');
    runSample.disabled = true;
    status.textContent = 'Computing SHA-256…';
    try {
      const bytes = new TextEncoder().encode('Legal Hash Checksum sample evidence\n');
      const digest = await window.crypto.subtle.digest('SHA-256', bytes);
      fingerprint.textContent = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
      status.textContent = 'Sample hashed locally';
    } catch {
      status.textContent = 'Sample requires HTTPS or localhost';
    } finally {
      runSample.disabled = false;
    }
  });
}
