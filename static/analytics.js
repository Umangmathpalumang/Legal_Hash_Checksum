/* Shared, production-only GA4 bootstrap. Never send case or file contents. */
(function () {
  'use strict';
  if (window.LHCAnalytics) return;

  const productionHost = location.protocol === 'https:' &&
    ['legalhashchecksum.com', 'www.legalhashchecksum.com'].includes(location.hostname);
  const tools = {
    '/': 'home', '/tools': 'tools', '/hash': 'hash_checksum', '/verify': 'verify',
    '/court-fee': 'court_fee_calculator', '/limitation-calculator': 'limitation_calculator',
    '/vakalatnama': 'vakalatnama', '/bail-bond': 'bail_bond',
    '/memo-appearance': 'memo_appearance', '/legal-notice': 'legal_notice',
    '/legal-notice-custom': 'legal_notice_custom', '/stamp-generator': 'stamp_generator',
    '/stamp-maker': 'stamp_maker', '/judgments': 'judgments',
    '/bns-lookup': 'bns_lookup', '/law-converter': 'law_converter',
    '/legal-dictionary': 'legal_dictionary', '/women-children-law': 'women_children_law',
    '/dashboard': 'dashboard', '/cases': 'cases', '/billing': 'billing',
    '/pricing': 'pricing', '/contact': 'contact', '/download': 'download',
    '/privacy-policy':'privacy_policy', '/alerts':'alerts', '/profile':'profile', '/legal-qa':'legal_qa',
  };
  const tool = tools[location.pathname] || 'other';
  const production=productionHost && tool!=='other';
  const events = new Set([
    'file_selected', 'file_loaded', 'hash_completed', 'hash_failed', 'hash_verified',
    'certificate_prepared', 'print_requested', 'invoice_prepared', 'calculate',
    'tool_open', 'filter_category', 'tool_search', 'feedback_sent', 'theme_toggle',
    'j_filter', 'j_click', 'select_law', 'filter_chapter', 'expand_section',
    'open_helplines', 'helpline_click', 'external_link', 'download_png',
  ]);
  const choices = {
    part: ['A', 'B'],
    format: ['general', 'ahc', 'form45', 'bailbond', 'surety'],
    result: ['complete', 'partial', 'match', 'mismatch'],
    type: ['Bug / Error', 'Improvement', 'New Feature', 'General'],
    theme: ['light', 'dark'],
    category: ['all', 'documents', 'evidence', 'research', 'calculators', 'community',
      'criminal', 'civil', 'constitutional', 'procedural', 'latin', 'general'],
    area: ['all', 'criminal', 'civil', 'family', 'tax', 'constitutional', 'labour', 'ipr', 'general'],
    law: ['ipc', 'bns', 'crpc', 'bnss', 'iea', 'bsa'],
    state: ['up', 'delhi', 'mh', 'rj', 'mp', 'gj', 'hr', 'pb', 'uk', 'ka'],
    destination: Object.values(tools),
  };
  const counts = new Set(['file_count', 'algorithm_count', 'result_count']);
  const flags = new Set(['has_email', 'has_query', 'has_court', 'has_hash_report']);

  let certificatePart;
  function track(name, input) {
    if (!production || !events.has(name)) return false;
    const params = {tool};
    Object.entries(input || {}).forEach(([key, value]) => {
      if (choices[key]?.includes(value)) params[key] = value;
      else if (counts.has(key) && Number.isInteger(value) && value >= 0 && value <= 100000) params[key] = value;
      else if (flags.has(key) && typeof value === 'boolean') params[key] = value;
      else if (key === 'days' && [0, 1, 7, 30, 90, 365].includes(value)) params[key] = value;
      else if (key === 'year' && Number.isInteger(value) && value >= 2024 && value <= 2100) params[key] = value;
    });
    if(name==='certificate_prepared')certificatePart=params.part;
    window.gtag('event', name, params);
    return true;
  }

  let printPending = false;
  function format() {
    if (location.pathname === '/vakalatnama') return document.querySelector('#fmtAHC.active') ? 'ahc' : 'general';
    if (location.pathname === '/bail-bond') {
      const active = document.querySelector('.fmt-btn.active');
      const index = [...document.querySelectorAll('.fmt-btn')].indexOf(active);
      return ['form45', 'bailbond', 'surety'][index];
    }
  }
  window.LHCAnalytics = Object.freeze({track, enabled: production});
  window.gaEvent = track;
  if (!production) return;
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };

  window.addEventListener('beforeprint', () => {
    if (!printPending) track('print_requested', {format: format(), part: certificatePart});
    printPending = true;
  });
  window.addEventListener('afterprint', () => { printPending = false; });

  function start() {
    // Retain campaign attribution, but drop search strings and all other parameters.
    const page = new URL(location.origin + location.pathname);
    const incoming = new URLSearchParams(location.search);
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'].forEach(key => {
      const value = incoming.get(key);
      if (value && /^[a-zA-Z0-9._-]{1,80}$/.test(value)) page.searchParams.set(key, value);
    });
    let referrer = '';
    try {
      const previous = new URL(document.referrer);
      if (previous.protocol === 'https:' && previous.hostname !== 'localhost' && !previous.hostname.endsWith('.localhost')) {
        referrer = previous.origin;
      }
    } catch (_) { /* No external referrer. */ }
    window.gtag('js', new Date());
    window.gtag('config', 'G-D8RVNQPKBQ', {
      page_title: document.title, page_location: page.href, page_referrer: referrer,
      send_page_view: true, allow_google_signals: false, allow_ad_personalization_signals: false,
    });
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=G-D8RVNQPKBQ';
    document.head.appendChild(script);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
