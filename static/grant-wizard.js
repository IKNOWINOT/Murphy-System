/* grant-wizard.js — Murphy System Grant & Financing Wizard
 * © 2020 Inoni Limited Liability Company by Corey Post
 * License: BSL 1.1
 */

(function () {
  'use strict';

  /* ─────────────────────────────────────────────────────────────
     STATE
  ───────────────────────────────────────────────────────────── */

  var currentStep = 1;   // 1=intake, 2=results, 3=apply
  var sessionId = getOrCreateSessionId();
  var selectedGrant = null;
  var eligibilityResults = null;
  var intakeData = null;

  /* ─────────────────────────────────────────────────────────────
     SESSION MANAGEMENT
  ───────────────────────────────────────────────────────────── */

  function getOrCreateSessionId() {
    var key = 'murphy_grant_session_id';
    var existing = localStorage.getItem(key);
    if (existing) return existing;
    var newId = generateUUID();
    localStorage.setItem(key, newId);
    return newId;
  }

  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /* ─────────────────────────────────────────────────────────────
     VALIDATION
  ───────────────────────────────────────────────────────────── */

  function validateZip(value) {
    return /^\d{5}$/.test(value.trim());
  }

  function validateIntakeForm() {
    var valid = true;

    var projectType = document.getElementById('project-type');
    var zipCode     = document.getElementById('zip-code');
    var bizType     = document.getElementById('biz-type');
    var taxStatus   = document.getElementById('tax-status');

    clearFieldError(projectType);
    clearFieldError(zipCode);
    clearFieldError(bizType);
    clearFieldError(taxStatus);

    if (!projectType || !projectType.value) {
      showFieldError(projectType, 'Please select a project type.');
      valid = false;
    }

    if (!zipCode || !validateZip(zipCode.value)) {
      showFieldError(zipCode, 'Please enter a valid 5-digit ZIP code.');
      valid = false;
    }

    if (!bizType || !bizType.value) {
      showFieldError(bizType, 'Please select a business type.');
      valid = false;
    }

    if (!taxStatus || !taxStatus.value) {
      showFieldError(taxStatus, 'Please select a tax status.');
      valid = false;
    }

    return valid;
  }

  function showFieldError(field, message) {
    if (!field) return;
    field.classList.add('error');
    var errEl = document.getElementById(field.id + '-error');
    if (errEl) {
      errEl.textContent = message;
      errEl.classList.add('visible');
    }
  }

  function clearFieldError(field) {
    if (!field) return;
    field.classList.remove('error');
    var errEl = document.getElementById(field.id + '-error');
    if (errEl) {
      errEl.textContent = '';
      errEl.classList.remove('visible');
    }
  }

  /* ─────────────────────────────────────────────────────────────
     FORMATTING
  ───────────────────────────────────────────────────────────── */

  function formatCurrency(value) {
    var n = parseInt(value, 10) || 0;
    return '$' + n.toLocaleString('en-US');
  }

  function formatDate(isoString) {
    if (!isoString) return 'Ongoing';
    var d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  /* ─────────────────────────────────────────────────────────────
     SLIDER INIT
  ───────────────────────────────────────────────────────────── */

  function initCostSlider() {
    var slider = document.getElementById('project-cost');
    var display = document.getElementById('cost-display');
    if (!slider || !display) return;

    function updateSlider() {
      var min = parseInt(slider.min, 10);
      var max = parseInt(slider.max, 10);
      var val = parseInt(slider.value, 10);
      var pct = ((val - min) / (max - min)) * 100;
      slider.style.setProperty('--slider-pct', pct + '%');
      display.textContent = formatCurrency(val);
    }

    slider.addEventListener('input', updateSlider);
    updateSlider();
  }

  /* ─────────────────────────────────────────────────────────────
     STEP NAVIGATION
  ───────────────────────────────────────────────────────────── */

  function setStep(stepNum) {
    currentStep = stepNum;

    var steps = document.querySelectorAll('.step-item');
    steps.forEach(function (el, i) {
      var n = i + 1;
      el.classList.remove('active', 'completed');
      if (n === stepNum) el.classList.add('active');
      else if (n < stepNum) el.classList.add('completed');
    });

    var connectors = document.querySelectorAll('.step-connector');
    connectors.forEach(function (el, i) {
      el.classList.toggle('completed', i + 1 < stepNum);
    });

    var panels = ['step-intake', 'step-results', 'step-apply'];
    panels.forEach(function (id, i) {
      var el = document.getElementById(id);
      if (el) el.style.display = (i + 1 === stepNum) ? 'block' : 'none';
    });

    var videoSection = document.getElementById('video-section');
    if (videoSection) {
      videoSection.style.display = (stepNum === 1) ? 'block' : 'none';
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ─────────────────────────────────────────────────────────────
     COLLECT INTAKE DATA
  ───────────────────────────────────────────────────────────── */

  function collectIntakeData() {
    return {
      project_type:  (document.getElementById('project-type') || {}).value || '',
      zip_code:      (document.getElementById('zip-code') || {}).value || '',
      project_cost:  parseInt((document.getElementById('project-cost') || {}).value || '0', 10),
      biz_type:      (document.getElementById('biz-type') || {}).value || '',
      building_type: (document.getElementById('building-type') || {}).value || '',
      sqft:          parseInt((document.getElementById('sqft') || {}).value || '0', 10) || 0,
      rural:         !!(document.getElementById('rural') || {}).checked,
      tax_status:    (document.getElementById('tax-status') || {}).value || '',
      session_id:    sessionId
    };
  }

  /* ─────────────────────────────────────────────────────────────
     API: FETCH ELIGIBILITY (Step 1 → Step 2)
  ───────────────────────────────────────────────────────────── */


  /* Basic ZIP → state lookup for grant matching (expanded as needed) */
  function inferStateFromZip(zip) {
    var n = parseInt(zip, 10);
    if (isNaN(n)) return 'CA';
    if (n >= 90000 && n <= 96699) return 'CA';
    if (n >= 97000 && n <= 97999) return 'OR';
    if (n >= 98000 && n <= 99499) return 'WA';
    if (n >= 10000 && n <= 14999) return 'NY';
    if (n >= 77000 && n <= 79999) return 'TX';
    if (n >= 60000 && n <= 62999) return 'IL';
    if (n >= 80000 && n <= 81999) return 'CO';
    if (n >= 30000 && n <= 31999) return 'GA';
    if (n >= 20000 && n <= 22999) return 'VA';
    if (n >= 33000 && n <= 34999) return 'FL';
    return 'CA';
  }

  // Project types that imply R&D activity
  var RD_PROJECT_TYPES = [
    'agentic', 'agentic_ai', 'ai_platform', 'software_rd', 'automation_rd',
    'industrial_iot', 'smart_manufacturing', 'manufacturing_automation',
    'grid_interactive', 'battery_storage', 'workflow_automation',
    'compliance_automation', 'crm_automation'
  ];

  function fetchEligibility(data) {
    var hasRd = RD_PROJECT_TYPES.indexOf(data.project_type) !== -1;
    // Infer state from ZIP (basic mapping — use OR as default for now)
    var stateFromZip = inferStateFromZip(data.zip_code);

    var params = new URLSearchParams({
      project_type:       data.project_type,
      zip_code:           data.zip_code,
      project_cost_usd:   data.project_cost,
      entity_type:        data.biz_type || 'small_business',  // biz_type now uses API entity-type values directly
      state:              stateFromZip,
      has_rd_activity:    hasRd ? 'true' : 'false',
      is_commercial:      (data.tax_status !== 'nonprofit') ? 'true' : 'false',
      existing_building:  data.building_type ? 'true' : 'false',
    });

    return fetch('/api/grants/eligibility?' + params.toString(), {
      method: 'GET',
      credentials: 'include'
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Server returned ' + res.status);
        return res.json();
      });
  }

  /* ─────────────────────────────────────────────────────────────
     API: START APPLICATION (Step 2 → Step 3 → redirect)
  ───────────────────────────────────────────────────────────── */

  function startApplication(grantId, description) {
    return fetch('/api/grants/sessions/' + encodeURIComponent(sessionId) + '/applications', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_id:    grantId,
        description: description,
        intake:      intakeData
      })
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Server returned ' + res.status);
        return res.json();
      });
  }

  /* ─────────────────────────────────────────────────────────────
     RENDER: GRANT CARDS
  ───────────────────────────────────────────────────────────── */

  function renderGrantCard(grant) {
    var eligPct = Math.round((grant.eligibility_score || 0) * 100);
    var typeClass = {
      'tax_credit': 'tax-credit',
      'grant':      'grant',
      'financing':  'financing',
      'utility':    'utility'
    }[grant.type] || 'grant';

    var typeLabelMap = {
      'tax_credit': 'Tax Credit',
      'grant':      'Grant',
      'financing':  'Financing',
      'utility':    'Utility Program'
    };
    var typeLabel = typeLabelMap[grant.type] || 'Program';

    var card = document.createElement('div');
    card.className = 'grant-card';
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', 'Select ' + grant.name);
    card.dataset.grantId = grant.id;

    card.innerHTML = [
      '<div class="grant-card-header">',
        '<div>',
          '<span class="grant-type-badge ' + typeClass + '">' + typeLabel + '</span>',
          '<h3>' + escapeHtml(grant.name) + '</h3>',
        '</div>',
        '<div class="grant-value">' + escapeHtml(formatValueRange(grant)) + '</div>',
      '</div>',
      '<div class="grant-card-meta">',
        '<span class="grant-meta-item"><span class="grant-meta-icon">📍</span>' + escapeHtml(grant.sponsor || 'Federal / State') + '</span>',
        '<span class="grant-meta-item"><span class="grant-meta-icon">📅</span>Deadline: ' + escapeHtml(formatDate(grant.deadline)) + '</span>',
      '</div>',
      '<div class="grant-eligibility-label">Eligibility match: ' + eligPct + '%</div>',
      '<div class="grant-eligibility-bar"><div class="grant-eligibility-fill" style="width:' + eligPct + '%"></div></div>',
      '<div class="grant-card-actions">',
        '<button class="murphy-btn murphy-btn-ghost murphy-btn-sm" data-action="details">Details</button>',
        '<button class="murphy-btn murphy-btn-primary murphy-btn-sm" data-action="apply">Apply →</button>',
      '</div>'
    ].join('');

    card.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-action]');
      if (btn && btn.dataset.action === 'apply') {
        selectGrantAndApply(grant);
      } else if (btn && btn.dataset.action === 'details') {
        showGrantDetails(grant);
      } else if (!btn) {
        selectGrantAndApply(grant);
      }
    });

    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        selectGrantAndApply(grant);
      }
    });

    return card;
  }

  function formatValueRange(grant) {
    if (grant.max_value && grant.min_value && grant.min_value !== grant.max_value) {
      return formatCurrency(grant.min_value) + ' – ' + formatCurrency(grant.max_value);
    }
    if (grant.max_value) return 'Up to ' + formatCurrency(grant.max_value);
    if (grant.percent_value) return 'Up to ' + grant.percent_value + '%';
    // grant.value holds value_description from API normalization
    if (grant.value && grant.value !== '') return grant.value;
    if (grant.estimated_value_usd) return 'Est. ' + formatCurrency(grant.estimated_value_usd);
    return 'Varies';
  }

  /* ─────────────────────────────────────────────────────────────
     RENDER: RESULTS PAGE
  ───────────────────────────────────────────────────────────── */


  /* ─────────────────────────────────────────────────────────────
     NORMALIZE API RESPONSE
     The API returns { matches: [{category, ...}, ...], total_matches, ... }
     renderResults expects { grants: [], tax_credits: [], financing: [], utility_programs: [] }
  ───────────────────────────────────────────────────────────── */

  function normalizeEligibilityResponse(data) {
    // If already in section format, pass through
    if (data.grants || data.tax_credits) return data;

    var matches = data.matches || [];
    var result = { grants: [], tax_credits: [], financing: [], utility_programs: [] };

    var grantCats = ['federal_grant', 'state_grant', 'usda_program', 'green_bank', 'espc'];
    var taxCats = ['federal_tax_credit', 'state_tax_credit', 'rd_tax_credit'];
    var financingCats = ['sba_financing', 'pace_financing', 'espc', 'green_bank'];
    var utilityCats = ['utility_program', 'state_incentive'];

    matches.forEach(function (m) {
      var cat = m.category || '';
      var card = {
        id: m.grant_id,
        name: m.grant_name,
        sponsor: m.agency || m.grant_id,
        description: (m.match_reasons || []).join('. '),
        value: m.value_description || '',
        estimated_value_usd: m.estimated_value_usd,
        deadline: m.deadline || null,
        url: m.program_url || '#',
        stacking: m.stacking_opportunities || [],
        match_score: m.match_score || 0,
        eligibility_score: m.match_score || 0,  // already 0-1; renderGrantCard multiplies by 100 for %
        category: cat
      };

      if (taxCats.indexOf(cat) !== -1) {
        result.tax_credits.push(card);
      } else if (utilityCats.indexOf(cat) !== -1) {
        result.utility_programs.push(card);
      } else if (financingCats.indexOf(cat) !== -1) {
        result.financing.push(card);
      } else {
        result.grants.push(card);
      }
    });

    // Sort each bucket by match_score desc
    ['grants','tax_credits','financing','utility_programs'].forEach(function (k) {
      result[k].sort(function (a, b) { return (b.match_score || 0) - (a.match_score || 0); });
    });

    return result;
  }

  function renderResults(results) {
    eligibilityResults = results;

    var sections = [
      { key: 'tax_credits',      label: 'Tax Credits',      icon: '💰', badgeClass: 'tax-credit'  },
      { key: 'grants',           label: 'Grants',            icon: '🏛️', badgeClass: 'grant'      },
      { key: 'financing',        label: 'Financing Options', icon: '🏦', badgeClass: 'financing'  },
      { key: 'utility_programs', label: 'Utility Programs',  icon: '⚡', badgeClass: 'utility'    }
    ];

    var container = document.getElementById('results-content');
    if (!container) return;
    container.innerHTML = '';

    var totalFound = 0;

    sections.forEach(function (section) {
      var items = (results[section.key] || []);
      totalFound += items.length;

      var sectionEl = document.createElement('div');
      sectionEl.className = 'grant-results-section';

      var header = document.createElement('div');
      header.className = 'grant-section-header';
      header.setAttribute('role', 'heading');
      header.setAttribute('aria-level', '2');
      header.innerHTML = [
        '<span class="grant-section-icon" aria-hidden="true">' + section.icon + '</span>',
        '<h2>' + section.label + '</h2>',
        '<span class="grant-section-count">' + items.length + '</span>'
      ].join('');
      sectionEl.appendChild(header);

      if (items.length === 0) {
        var noItems = document.createElement('p');
        noItems.style.cssText = 'color:var(--text-muted);font-size:13px;padding:8px 0;';
        noItems.textContent = 'No ' + section.label.toLowerCase() + ' found for your profile.';
        sectionEl.appendChild(noItems);
      } else {
        items.forEach(function (grant) {
          grant.type = grant.type || sectionKeyToType(section.key);
          sectionEl.appendChild(renderGrantCard(grant));
        });
      }

      container.appendChild(sectionEl);
    });

    var summary = document.getElementById('results-summary');
    if (summary) {
      summary.textContent = totalFound > 0
        ? 'Found ' + totalFound + ' programs you may qualify for'
        : 'No matching programs found for your current profile';
    }
  }

  function sectionKeyToType(key) {
    var map = {
      'tax_credits':      'tax_credit',
      'grants':           'grant',
      'financing':        'financing',
      'utility_programs': 'utility'
    };
    return map[key] || 'grant';
  }

  /* ─────────────────────────────────────────────────────────────
     GRANT SELECTION → STEP 3
  ───────────────────────────────────────────────────────────── */

  function selectGrantAndApply(grant) {
    selectedGrant = grant;

    var nameEl = document.getElementById('apply-grant-name');
    var valueEl = document.getElementById('apply-grant-value');
    var deadlineEl = document.getElementById('apply-grant-deadline');

    if (nameEl) nameEl.textContent = grant.name;
    if (valueEl) valueEl.textContent = formatValueRange(grant);
    if (deadlineEl) deadlineEl.textContent = formatDate(grant.deadline);

    setStep(3);
  }

  function showGrantDetails(grant) {
    // Remove any existing modal
    var existing = document.getElementById('grant-detail-modal');
    if (existing) existing.remove();

    var stacking = (grant.stacking || []).join(', ') || 'None identified';
    var eligPct = Math.round((grant.eligibility_score || 0) * 100);

    var modal = document.createElement('div');
    modal.id = 'grant-detail-modal';
    modal.style.cssText = [
      'position:fixed;inset:0;z-index:9999;display:flex;align-items:flex-end;justify-content:center;',
      'background:rgba(0,0,0,0.65);backdrop-filter:blur(4px);',
    ].join('');

    modal.innerHTML = [
      '<div style="',
        'background:var(--bg-card,#16191f);border-top:2px solid var(--accent,#00e5a0);',
        'border-radius:16px 16px 0 0;width:100%;max-width:640px;max-height:80vh;',
        'overflow-y:auto;padding:32px 28px 40px;font-family:var(--font-ui,Inter,sans-serif);',
        'animation:slideUp 0.25s ease;',
      '">',
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;">',
          '<div>',
            '<span style="font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;',
              'color:var(--accent,#00e5a0);margin-bottom:6px;display:block;">Program Details</span>',
            '<h2 style="font-size:18px;font-weight:700;color:var(--text-primary,#fff);margin:0;">',
              escapeHtml(grant.name),
            '</h2>',
          '</div>',
          '<button id="grant-modal-close" style="',
            'background:none;border:none;cursor:pointer;font-size:22px;color:var(--text-muted,#666);',
            'line-height:1;padding:4px 8px;',
          '" aria-label="Close">✕</button>',
        '</div>',

        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px;">',
          _detailCell('💰 Value', formatValueRange(grant)),
          _detailCell('📍 Sponsor', grant.sponsor || 'Federal / State'),
          _detailCell('📅 Deadline', formatDate(grant.deadline)),
          _detailCell('🎯 Match', eligPct + '%'),
        '</div>',

        '<div style="margin-bottom:16px;">',
          '<div style="font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;',
            'color:var(--text-muted,#888);margin-bottom:8px;">Description</div>',
          '<p style="font-size:14px;line-height:1.6;color:var(--text-secondary,#bbb);margin:0;">',
            escapeHtml(grant.description || 'No description available.'),
          '</p>',
        '</div>',

        (stacking !== 'None identified' ? [
          '<div style="margin-bottom:20px;">',
            '<div style="font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;',
              'color:var(--text-muted,#888);margin-bottom:8px;">Stackable With</div>',
            '<p style="font-size:13px;color:var(--text-secondary,#bbb);margin:0;">',
              escapeHtml(stacking),
            '</p>',
          '</div>',
        ].join('') : ''),

        '<div style="display:flex;gap:12px;margin-top:24px;">',
          '<button id="grant-modal-apply" class="murphy-btn murphy-btn-primary" style="flex:1;">',
            'Apply for This Grant →',
          '</button>',
          (grant.url && grant.url !== '#' ? [
            '<a href="' + escapeHtml(grant.url) + '" target="_blank" rel="noopener"',
              ' class="murphy-btn murphy-btn-ghost" style="flex:0 0 auto;">',
              'Program Site ↗',
            '</a>',
          ].join('') : ''),
        '</div>',
      '</div>',
    ].join('');

    document.body.appendChild(modal);

    // Close handlers
    document.getElementById('grant-modal-close').onclick = function () { modal.remove(); };
    modal.addEventListener('click', function (e) { if (e.target === modal) modal.remove(); });
    document.getElementById('grant-modal-apply').onclick = function () {
      modal.remove();
      selectGrantAndApply(grant);
    };
  }

  function _detailCell(label, value) {
    return [
      '<div style="background:var(--bg-card-inner,rgba(255,255,255,.04));border-radius:8px;padding:12px 14px;">',
        '<div style="font-size:11px;color:var(--text-muted,#888);margin-bottom:4px;">' + escapeHtml(label) + '</div>',
        '<div style="font-size:14px;font-weight:600;color:var(--text-primary,#fff);">' + escapeHtml(String(value)) + '</div>',
      '</div>',
    ].join('');
  }

  /* ─────────────────────────────────────────────────────────────
     UI HELPERS
  ───────────────────────────────────────────────────────────── */

  function showSpinner(containerId) {
    var el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = [
      '<div class="loading-spinner" role="status" aria-live="polite">',
        '<div class="spinner-ring" aria-hidden="true"></div>',
        '<p class="spinner-text">Searching programs…</p>',
      '</div>'
    ].join('');
  }

  function showInlineError(containerId, message) {
    var el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = [
      '<div style="text-align:center;padding:48px 24px;color:var(--danger);font-family:var(--font-ui,Inter,sans-serif);">',
        '<div style="font-size:32px;margin-bottom:12px;">⚠️</div>',
        '<p style="margin:0;font-size:14px;">' + escapeHtml(message) + '</p>',
        '<button class="murphy-btn murphy-btn-ghost murphy-btn-sm" style="margin-top:16px;" onclick="location.reload()">Try Again</button>',
      '</div>'
    ].join('');
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setButtonLoading(btn, loading, originalText) {
    if (!btn) return;
    btn.disabled = loading;
    if (loading) {
      btn.dataset.originalText = btn.textContent;
      btn.textContent = '…';
      btn.setAttribute('aria-busy', 'true');
    } else {
      btn.textContent = originalText || btn.dataset.originalText || btn.textContent;
      btn.removeAttribute('aria-busy');
    }
  }

  /* ─────────────────────────────────────────────────────────────
     VIDEO SETUP
  ───────────────────────────────────────────────────────────── */

  /* Inject modal animation keyframe once */
  (function () {
    if (!document.getElementById('gw-modal-styles')) {
      var s = document.createElement('style');
      s.id = 'gw-modal-styles';
      s.textContent = '@keyframes slideUp{from{transform:translateY(60px);opacity:0}to{transform:translateY(0);opacity:1}}';
      document.head.appendChild(s);
    }
  })();

  function initVideo() {
    var body = document.body;
    var videoUrl = (body && body.dataset.videoUrl) ? body.dataset.videoUrl.trim() : '';
    var videoEl = document.getElementById('wizard-video');
    var placeholderEl = document.getElementById('video-placeholder');

    if (!videoEl) return;

    if (videoUrl) {
      var sourceEl = document.createElement('source');
      sourceEl.src = videoUrl;
      sourceEl.type = 'video/mp4';
      videoEl.appendChild(sourceEl);
      videoEl.style.display = 'block';
      if (placeholderEl) placeholderEl.style.display = 'none';
    } else {
      videoEl.style.display = 'none';
      if (placeholderEl) placeholderEl.style.display = 'flex';
    }
  }

  /* ─────────────────────────────────────────────────────────────
     EVENT WIRING
  ───────────────────────────────────────────────────────────── */

  function initWizard() {
    initCostSlider();
    initVideo();
    setStep(1);

    // Step 1 → 2: Find My Options
    var findBtn = document.getElementById('btn-find-options');
    if (findBtn) {
      findBtn.addEventListener('click', function () {
        if (!validateIntakeForm()) return;

        intakeData = collectIntakeData();
        setStep(2);
        showSpinner('results-content');

        fetchEligibility(intakeData)
          .then(function (data) {
            renderResults(normalizeEligibilityResponse(data));
          })
          .catch(function (err) {
            showInlineError('results-content', 'Unable to load results. Please check your connection and try again.');
            console.error('[Grant Wizard] Eligibility fetch failed:', err);
          });
      });
    }

    // Step 2 → 1: Back
    var backBtn = document.getElementById('btn-back-to-intake');
    if (backBtn) {
      backBtn.addEventListener('click', function () {
        setStep(1);
      });
    }

    // Step 3: Start Application
    var applyBtn = document.getElementById('btn-start-application');
    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        if (!selectedGrant) return;

        var descEl = document.getElementById('project-description');
        var description = descEl ? descEl.value.trim() : '';

        setButtonLoading(applyBtn, true);

        startApplication(selectedGrant.id, description)
          .then(function (data) {
            var appId = data.app_id || data.application_id || data.id || '';
            var redirectUrl = '/ui/grant-application?app_id=' + encodeURIComponent(appId) +
              '&session_id=' + encodeURIComponent(sessionId);
            window.location.href = redirectUrl;
          })
          .catch(function (err) {
            setButtonLoading(applyBtn, false);
            var errEl = document.getElementById('apply-error');
            if (errEl) {
              errEl.textContent = 'Failed to start application. Please try again.';
              errEl.classList.add('visible');
            }
            console.error('[Grant Wizard] Application start failed:', err);
          });
      });
    }

    // Step 3: Cancel
    var cancelLink = document.getElementById('link-cancel-apply');
    if (cancelLink) {
      cancelLink.addEventListener('click', function (e) {
        e.preventDefault();
        setStep(2);
      });
    }

    // ZIP code: live format validation
    var zipInput = document.getElementById('zip-code');
    if (zipInput) {
      zipInput.addEventListener('input', function () {
        this.value = this.value.replace(/\D/g, '').slice(0, 5);
      });
      zipInput.addEventListener('blur', function () {
        if (this.value && !validateZip(this.value)) {
          showFieldError(this, 'Please enter a valid 5-digit ZIP code.');
        } else {
          clearFieldError(this);
        }
      });
    }
  }

  /* ─────────────────────────────────────────────────────────────
     BOOT
  ───────────────────────────────────────────────────────────── */

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWizard);
  } else {
    initWizard();
  }

  // Expose session ID globally for other scripts
  window.murphyGrantSessionId = sessionId;

}());
