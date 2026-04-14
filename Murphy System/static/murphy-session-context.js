/**
 * murphy-session-context.js — Cross-Flow Session Context Manager
 * Murphy System — COMM-CTX-001
 *
 * Stores NL inputs, form data, HITL decisions, and workflow state in
 * sessionStorage so information entered in one flow automatically
 * pre-fills related fields in other flows.
 *
 * Usage:
 *   <script src="/static/murphy-session-context.js"></script>
 *
 *   // Store data from any flow
 *   MurphyContext.set('company_name', 'Acme Corp');
 *   MurphyContext.setMany({ industry: 'SaaS', team_size: '12' });
 *
 *   // Retrieve in another flow
 *   var name = MurphyContext.get('company_name');
 *
 *   // Auto-fill forms on page load
 *   MurphyContext.autoFill();
 *
 *   // Record NL query for cross-flow reuse
 *   MurphyContext.recordNLQuery('Build me a compliance automation system');
 *
 *   // Record HITL decision so originating flow sees the outcome
 *   MurphyContext.recordHITLDecision({ id: 'h-42', action: 'approved' });
 *
 * Copyright 2020 Inoni Limited Liability Company
 * Creator: Corey Post
 * License: BSL 1.1
 */

/* global window, document, sessionStorage, console */
/* eslint-disable no-console */

var MurphyContext = (function () {
  'use strict';

  var STORE_KEY = 'murphy_session_context';
  var NL_KEY = 'murphy_nl_queries';
  var HITL_KEY = 'murphy_hitl_decisions';
  var LOG_PREFIX = '[MurphyContext]';

  // ── Storage helpers ─────────────────────────────────────────────

  function _read(key) {
    try {
      var raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      console.warn(LOG_PREFIX, 'Read failed for', key, ':', e && e.message);
      return null;
    }
  }

  function _write(key, value) {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      console.warn(LOG_PREFIX, 'Write failed for', key, ':', e && e.message);
    }
  }

  function _getStore() { return _read(STORE_KEY) || {}; }
  function _putStore(store) { _write(STORE_KEY, store); }

  // ── Core getters/setters ────────────────────────────────────────

  function get(key) {
    var store = _getStore();
    return store[key] !== undefined ? store[key] : null;
  }

  function set(key, value) {
    var store = _getStore();
    store[key] = value;
    store._updated_at = new Date().toISOString();
    _putStore(store);
  }

  function setMany(obj) {
    if (!obj || typeof obj !== 'object') return;
    var store = _getStore();
    var keys = Object.keys(obj);
    for (var i = 0; i < keys.length; i++) {
      if (obj[keys[i]] !== undefined && obj[keys[i]] !== null && obj[keys[i]] !== '') {
        store[keys[i]] = obj[keys[i]];
      }
    }
    store._updated_at = new Date().toISOString();
    _putStore(store);
  }

  function getAll() { return _getStore(); }

  function clear() {
    _write(STORE_KEY, {});
    _write(NL_KEY, []);
    _write(HITL_KEY, []);
  }

  // ── NL Query Recording ──────────────────────────────────────────

  function recordNLQuery(query, source) {
    if (!query || typeof query !== 'string') return;
    var queries = _read(NL_KEY) || [];
    queries.push({
      query: query,
      source: source || window.location.pathname,
      timestamp: new Date().toISOString()
    });
    if (queries.length > 20) queries = queries.slice(-20);
    _write(NL_KEY, queries);
    _extractAndStore(query);
  }

  function getNLQueries() { return _read(NL_KEY) || []; }

  function getLastNLQuery() {
    var queries = getNLQueries();
    return queries.length > 0 ? queries[queries.length - 1] : null;
  }

  // ── HITL Decision Recording ─────────────────────────────────────

  function recordHITLDecision(decision) {
    if (!decision || !decision.id) {
      console.warn(LOG_PREFIX, 'HITL decision missing id — not recorded');
      return;
    }
    decision.timestamp = decision.timestamp || new Date().toISOString();
    decision.source = decision.source || window.location.pathname;

    var decisions = _read(HITL_KEY) || [];
    decisions.push(decision);
    if (decisions.length > 50) decisions = decisions.slice(-50);
    _write(HITL_KEY, decisions);
    console.info(LOG_PREFIX, 'HITL decision recorded:', decision.id, decision.action);
  }

  function getHITLDecisions() { return _read(HITL_KEY) || []; }

  function getHITLDecision(itemId) {
    var decisions = getHITLDecisions();
    for (var i = decisions.length - 1; i >= 0; i--) {
      if (decisions[i].id === itemId) return decisions[i];
    }
    return null;
  }

  // ── Auto-Fill ───────────────────────────────────────────────────

  var _fieldMappings = {
    company_name:  ['company_name', 'company', 'org_name', 'organization', 'orgName'],
    industry:      ['industry', 'sector', 'vertical'],
    team_size:     ['team_size', 'teamSize', 'employees', 'team_count'],
    user_name:     ['user_name', 'name', 'full_name', 'fullName', 'contact_name'],
    email:         ['email', 'user_email', 'contact_email'],
    phone:         ['phone', 'telephone', 'mobile'],
    role:          ['role', 'job_title', 'position', 'title'],
    use_case:      ['use_case', 'useCase', 'use-case', 'description', 'project_description'],
    project_name:  ['project_name', 'projectName', 'project'],
    budget:        ['budget', 'monthly_budget'],
    timeline:      ['timeline', 'deadline', 'target_date'],
    pain_points:   ['pain_points', 'challenges', 'problems'],
    goals:         ['goals', 'objectives', 'desired_outcome']
  };

  function autoFill() {
    var store = _getStore();
    var filled = 0;
    var contextKeys = Object.keys(_fieldMappings);
    for (var k = 0; k < contextKeys.length; k++) {
      var ctxKey = contextKeys[k];
      var value = store[ctxKey];
      if (!value) continue;
      var patterns = _fieldMappings[ctxKey];
      for (var p = 0; p < patterns.length; p++) {
        var els = _findFields(patterns[p]);
        for (var e = 0; e < els.length; e++) {
          var el = els[e];
          if (!el.value || el.value.trim() === '') {
            el.value = value;
            filled++;
            try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch (ev) { /* old browser */ }
          }
        }
      }
    }
    if (filled > 0) {
      console.info(LOG_PREFIX, 'Auto-filled', filled, 'field(s) from session context');
    }
  }

  function _findFields(nameOrId) {
    var results = [];
    var byId = document.getElementById(nameOrId);
    if (byId) results.push(byId);
    var byName = document.querySelectorAll('[name="' + nameOrId + '"]');
    for (var i = 0; i < byName.length; i++) {
      if (results.indexOf(byName[i]) === -1) results.push(byName[i]);
    }
    return results;
  }

  // ── Entity Extraction from NL ──────────────────────────────────

  function _extractAndStore(query) {
    var lower = query.toLowerCase();
    var store = _getStore();

    var industries = {
      'healthcare': 'Healthcare', 'medical': 'Healthcare', 'hospital': 'Healthcare',
      'finance': 'Finance', 'banking': 'Finance', 'fintech': 'Finance',
      'retail': 'Retail', 'ecommerce': 'Retail', 'e-commerce': 'Retail',
      'manufacturing': 'Manufacturing', 'factory': 'Manufacturing',
      'saas': 'SaaS', 'software': 'SaaS/Software',
      'education': 'Education', 'edtech': 'Education',
      'real estate': 'Real Estate', 'property': 'Real Estate',
      'logistics': 'Logistics', 'shipping': 'Logistics', 'supply chain': 'Logistics',
      'legal': 'Legal', 'law firm': 'Legal',
      'insurance': 'Insurance',
      'energy': 'Energy', 'renewable': 'Energy',
      'agriculture': 'Agriculture', 'farming': 'Agriculture',
      'gaming': 'Gaming', 'game': 'Gaming',
      'media': 'Media', 'publishing': 'Media',
      'construction': 'Construction',
      'automotive': 'Automotive',
      'aerospace': 'Aerospace', 'defense': 'Aerospace/Defense',
      'telecom': 'Telecommunications'
    };

    var industryKeys = Object.keys(industries);
    for (var i = 0; i < industryKeys.length; i++) {
      if (lower.indexOf(industryKeys[i]) !== -1 && !store.industry) {
        store.industry = industries[industryKeys[i]];
        break;
      }
    }

    if (!store.use_case && query.length > 10) {
      store.use_case = query;
    }

    var teamMatch = query.match(/(\d+)\s*(people|employees|team\s*members|staff|person)/i);
    if (teamMatch && !store.team_size) {
      store.team_size = teamMatch[1];
    }

    var budgetMatch = query.match(/\$\s*([\d,]+\.?\d*)\s*([kK])?/);
    if (budgetMatch && !store.budget) {
      var amount = parseFloat(budgetMatch[1].replace(/,/g, ''));
      if (budgetMatch[2]) amount *= 1000;
      store.budget = '$' + amount.toLocaleString();
    }

    store._updated_at = new Date().toISOString();
    _putStore(store);
  }

  // ── Capture form data on submit ────────────────────────────────

  function captureFormOnSubmit(formOrSelector) {
    var form = typeof formOrSelector === 'string'
      ? document.querySelector(formOrSelector)
      : formOrSelector;
    if (!form || form.tagName !== 'FORM') return;

    form.addEventListener('submit', function () {
      var formData = new FormData(form);
      var obj = {};
      formData.forEach(function (value, key) {
        if (value && typeof value === 'string' && value.trim()) {
          obj[key] = value.trim();
        }
      });
      setMany(obj);
      console.info(LOG_PREFIX, 'Captured', Object.keys(obj).length, 'field(s) from form submit');
    }, true);
  }

  // ── Init ───────────────────────────────────────────────────────

  function _init() { autoFill(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

  return {
    get: get,
    set: set,
    setMany: setMany,
    getAll: getAll,
    clear: clear,
    recordNLQuery: recordNLQuery,
    getNLQueries: getNLQueries,
    getLastNLQuery: getLastNLQuery,
    recordHITLDecision: recordHITLDecision,
    getHITLDecisions: getHITLDecisions,
    getHITLDecision: getHITLDecision,
    autoFill: autoFill,
    captureFormOnSubmit: captureFormOnSubmit
  };
})();
