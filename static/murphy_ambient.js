/**
 * Murphy System — Ambient Intelligence Engine
 * © 2020 Inoni Limited Liability Company by Corey Post
 * License: BSL 1.1
 *
 * "6th Sense Technology" — silently works around a moving target to form
 * what is expected before it is requested, then delivers it directly.
 *
 * Architecture:
 *   ContextCollector  — polls calendar, tasks, meetings, workspace for signals
 *   SynthesisEngine   — cross-references signals to form proactive packages
 *   DeliveryPipeline  — routes synthesised outputs to UI, email, notifications
 *   RoyaltyTracker    — logs which shadow agents contributed to each delivery
 */

(function (global) {
  'use strict';

  /* ─────────────────────────────────────────────────────────────────────────
   *  CONSTANTS
   * ───────────────────────────────────────────────────────────────────────── */
  var VERSION = '1.0.0';
  var POLL_INTERVAL_MS   = 60000;    // context poll: every 60 s
  var API_REFRESH_EVERY  = 5;        // force fresh API fetch every Nth poll (~5 min)
  var SYNTH_INTERVAL_MS  = 90000;    // synthesis run: every 90 s
  var DELIVERY_DELAY_MS  = 5000;     // min delay between deliveries
  var MAX_QUEUE          = 50;       // max pending deliveries

  var BASE_URL = (global.location && global.location.origin) || '';

  /* ─────────────────────────────────────────────────────────────────────────
   *  STATE
   * ───────────────────────────────────────────────────────────────────────── */
  var state = {
    running:       false,
    paused:        false,
    context:       {},               // accumulated context signals
    insights:      [],               // synthesised insights waiting for delivery
    delivered:     [],               // delivery history
    actioned:      0,
    insightsCount: 0,               // total insights emitted to UI
    deliveredCount:0,               // total email deliveries sent
    confidenceSum: 0,               // running sum for avg confidence calculation
    settings: {
      contextEnabled:   true,
      emailEnabled:     true,
      meetingLink:      true,
      frequency:        'daily',
      confidenceMin:    65,
      shadowMode:       false
    },
    timers: {
      poll:    null,
      synth:   null,
      deliver: null,
      server:  null
    }
  };

  /* ─────────────────────────────────────────────────────────────────────────
   *  SETTINGS LOADER
   * ───────────────────────────────────────────────────────────────────────── */
  function loadSettings() {
    try {
      var saved = localStorage.getItem('murphy_ambient_settings');
      if (saved) {
        var parsed = JSON.parse(saved);
        Object.keys(parsed).forEach(function (k) {
          if (k in state.settings) state.settings[k] = parsed[k];
        });
      }
    } catch (_) {}
  }

  /* ─────────────────────────────────────────────────────────────────────────
   *  CONTEXT COLLECTOR
   *  Silently gathers signals from all available data sources.
   *  Each _*Signals() method tries the real Murphy API first, falls back to
   *  localStorage if the API is unavailable or returns an error.
   * ───────────────────────────────────────────────────────────────────────── */
  var ContextCollector = {
    _meetingsFetching: false,
    _tasksFetching:    false,

    collect: function () {
      if (!state.settings.contextEnabled) return;

      state.pollCount++;
      var forceRefresh = (state.pollCount % API_REFRESH_EVERY === 0);

      var signals = [];

      /* 1 — Calendar proximity */
      signals = signals.concat(ContextCollector._calendarSignals(forceRefresh));

      /* 2 — Meeting intelligence data */
      if (state.settings.meetingLink) {
        signals = signals.concat(ContextCollector._meetingSignals(forceRefresh));
      }

      /* 3 — Task overdue / unassigned */
      signals = signals.concat(ContextCollector._taskSignals(forceRefresh));

        if (signals.length) {
          self._pushToAPI(signals);
        }
        if (DEV && signals.length) {
          console.debug('[MurphyAmbient] collected ' + signals.length + ' signal(s)');
        }
      }).catch(function () {});
    },

    /* Fetch with a hard timeout. Returns a Promise that rejects on timeout. */
    _fetchWithTimeout: function (url) {
      return new Promise(function (resolve, reject) {
        var done = false;
        var timer = setTimeout(function () {
          if (!done) { done = true; reject(new Error('timeout')); }
        }, ContextCollector._TIMEOUT_MS);
        fetch(url)
          .then(function (res) {
            clearTimeout(timer);
            if (!done) { done = true; resolve(res); }
          })
          .catch(function (err) {
            clearTimeout(timer);
            if (!done) { done = true; reject(err); }
          });
      });
    },

    /* Record a success for a source (reset failure counter). */
    _onSuccess: function (source) {
      ContextCollector._failures[source] = 0;
      ContextCollector._retryAfter[source] = 0;
    },

    /* Record a failure for a source (exponential backoff after _MAX_FAILURES). */
    _onFailure: function (source) {
      var f = ++ContextCollector._failures[source];
      if (f >= ContextCollector._MAX_FAILURES) {
        /* Backoff: 30 s × 2^(f - MAX) capped at 10 min (600 000 ms) */
        var backoffMs = Math.min(30000 * Math.pow(2, f - ContextCollector._MAX_FAILURES), 600000);
        ContextCollector._retryAfter[source] = Date.now() + backoffMs;
      }
    },

    /* Returns true when the source is in backoff. */
    _isBackedOff: function (source) {
      return Date.now() < ContextCollector._retryAfter[source];
    },

    _calendarSignals: function () {
      var self = ContextCollector;
      var source = 'calendar';

      /* Parse events array into calendar signals */
      function parseEvents(events) {
        var signals = [];
        var now = Date.now();
        events.forEach(function (ev) {
          var start = new Date(ev.start || ev.scheduled_start || ev.date).getTime();
          if (isNaN(start)) return;
          var diff = start - now;
          if (diff > 0 && diff < 3600000) {
            signals.push({ source: source, type: 'upcoming_meeting', data: ev, priority: 'high', confidence: 88, label: 'Meeting in ' + Math.round(diff / 60000) + ' min: ' + (ev.title || ev.name || 'Untitled') });
          }
          var end = ev.end ? new Date(ev.end).getTime() : start + 3600000;
          if (now > end && now - end < 900000) {
            signals.push({ source: source, type: 'post_meeting', data: ev, priority: 'medium', confidence: 75, label: 'Post-meeting brief: ' + (ev.title || ev.name || 'Untitled') });
          }
        });
        return signals;
      }

      /* localStorage fallback */
      function fromLocalStorage() {
        try {
          var events = JSON.parse(localStorage.getItem('murphy_calendar_events') || '[]');
          return parseEvents(events);
        } catch (_) { return []; }
      }

      if (self._isBackedOff(source)) {
        return Promise.resolve(fromLocalStorage());
      }

      return self._fetchWithTimeout(BASE_URL + '/api/time-tracking')
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          var items = data.entries || data.sessions || data.events || data.items || [];
          if (!Array.isArray(items)) items = [];
          /* Cache for offline use */
          try { localStorage.setItem('murphy_calendar_events', JSON.stringify(items)); } catch (_) {}
          self._onSuccess(source);
          return parseEvents(items);
        })
        .catch(function () {
          self._onFailure(source);
          return fromLocalStorage();
        });
    },

    _meetingSignals: function () {
      var self = ContextCollector;
      var source = 'meeting';

      function parseSessions(sessions) {
        var signals = [];
        sessions.forEach(function (session) {
          if (session.drafts) {
            var draftKeys = Object.keys(session.drafts);
            var unvoted = draftKeys.filter(function (k) { return !(session.votes && session.votes[k]); });
            if (unvoted.length) {
              signals.push({ source: source, type: 'pending_votes', data: { count: unvoted.length, session: session.id }, priority: 'medium', confidence: 82, label: unvoted.length + ' draft(s) pending vote in last meeting' });
            }
          }
        });
        var orgSessions = sessions.length;
        if (orgSessions > 0 && orgSessions % 5 === 0) {
          signals.push({ source: source, type: 'org_milestone', data: { sessions: orgSessions }, priority: 'low', confidence: 95, label: 'Org milestone: ' + orgSessions + ' sessions completed' });
        }
        return signals;
      }

      function fromLocalStorage() {
        var signals = [];
        try {
          var session = JSON.parse(localStorage.getItem('murphy_last_meeting') || 'null');
          if (session && session.drafts) {
            var draftKeys = Object.keys(session.drafts);
            var unvoted = draftKeys.filter(function (k) { return !(session.votes && session.votes[k]); });
            if (unvoted.length) {
              signals.push({ source: source, type: 'pending_votes', data: { count: unvoted.length, session: session.id }, priority: 'medium', confidence: 82, label: unvoted.length + ' draft(s) pending vote in last meeting' });
            }
          }
          var orgSessions = parseInt(localStorage.getItem('murphy_org_sessions') || '0', 10);
          if (orgSessions > 0 && orgSessions % 5 === 0) {
            signals.push({ source: source, type: 'org_milestone', data: { sessions: orgSessions }, priority: 'low', confidence: 95, label: 'Org milestone: ' + orgSessions + ' sessions completed' });
          }
        } catch (_) {}
        return signals;
      }

      if (self._isBackedOff(source)) {
        return Promise.resolve(fromLocalStorage());
      }

      return self._fetchWithTimeout(BASE_URL + '/api/meeting-intelligence/sessions')
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          var sessions = data.sessions || data.items || data.data || [];
          if (!Array.isArray(sessions)) sessions = [];
          try { localStorage.setItem('murphy_mi_data', JSON.stringify(sessions)); } catch (_) {}
          self._onSuccess(source);
          return parseSessions(sessions);
        })
        .catch(function () {
          self._onFailure(source);
          return fromLocalStorage();
        });
    },

    _fetchMeetingsFromAPI: function () {
      if (ContextCollector._meetingsFetching) return;
      ContextCollector._meetingsFetching = true;
      fetch(BASE_URL + '/api/meeting-intelligence/sessions', { credentials: 'same-origin' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          ContextCollector._meetingsFetching = false;
          if (!data) return;
          var sessions = Array.isArray(data) ? data : (data.sessions || []);
          if (sessions.length) {
            try {
              localStorage.setItem('murphy_last_meeting', JSON.stringify(sessions[0]));
              localStorage.setItem('murphy_org_sessions', String(sessions.length));
            } catch (_) {}
          }
        })
        .catch(function () { ContextCollector._meetingsFetching = false; });
    },

    _taskSignals: function () {
      var self = ContextCollector;
      var source = 'tasks';

      function parseTasks(tasks) {
        var signals = [];
        var now = Date.now();
        /* Fallback: if localStorage is empty, fetch from the real API and cache for next cycle */
        if (!tasks.length) {
          ContextCollector._fetchTasksFromAPI();
          return signals;
        }
        var overdue = tasks.filter(function (t) { return t.due && new Date(t.due).getTime() < now && t.status !== 'done'; });
        var unassigned = tasks.filter(function (t) { return !t.assignee && t.status !== 'done'; });
        if (overdue.length) signals.push({ source: source, type: 'overdue', data: { count: overdue.length }, priority: 'high', confidence: 97, label: overdue.length + ' overdue task(s) need attention' });
        if (unassigned.length) signals.push({ source: source, type: 'unassigned', data: { count: unassigned.length }, priority: 'medium', confidence: 88, label: unassigned.length + ' task(s) have no assigned owner' });
        return signals;
      }

      function fromLocalStorage() {
        try {
          var tasks = JSON.parse(localStorage.getItem('murphy_tasks') || '[]');
          return parseTasks(tasks);
        } catch (_) { return []; }
      }

      if (self._isBackedOff(source)) {
        return Promise.resolve(fromLocalStorage());
      }

      return self._fetchWithTimeout(BASE_URL + '/api/boards')
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          var boards = data.boards || data.items || data.data || [];
          if (!Array.isArray(boards)) boards = [];
          /* Flatten all items across boards into a task list */
          var tasks = [];
          boards.forEach(function (board) {
            var items = board.items || board.tasks || board.cards || [];
            tasks = tasks.concat(items);
          });
          try { localStorage.setItem('murphy_tasks', JSON.stringify(tasks)); } catch (_) {}
          self._onSuccess(source);
          return parseTasks(tasks);
        })
        .catch(function () {
          self._onFailure(source);
          return fromLocalStorage();
        });
    },

    _fetchTasksFromAPI: function () {
      if (ContextCollector._tasksFetching) return;
      ContextCollector._tasksFetching = true;
      fetch(BASE_URL + '/api/boards', { credentials: 'same-origin' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          ContextCollector._tasksFetching = false;
          if (!data) return;
          var tasks = [];
          var boards = Array.isArray(data) ? data : (data.boards || []);
          boards.forEach(function (board) {
            (board.cards || board.tasks || []).forEach(function (card) {
              tasks.push({
                title:    card.title    || card.name        || '',
                due:      card.due      || card.due_date    || null,
                assignee: card.assignee || card.assigned_to || null,
                status:   card.status   || card.state       || 'open'
              });
            });
          });
          if (tasks.length) {
            try { localStorage.setItem('murphy_tasks', JSON.stringify(tasks)); } catch (_) {}
          }
        })
        .catch(function () { ContextCollector._tasksFetching = false; });
    },

    _workspaceSignals: function () {
      var self = ContextCollector;
      var source = 'workspace';

      function parseActivity(data) {
        var signals = [];
        var unread = data.unread_count || data.unread || 0;
        if (typeof unread !== 'number') unread = parseInt(unread, 10) || 0;
        if (unread > 20) {
          signals.push({ source: source, type: 'high_unread', data: { count: unread }, priority: 'low', confidence: 70, label: unread + ' unread workspace messages' });
        }
        return signals;
      }

      function fromLocalStorage() {
        try {
          var unread = parseInt(localStorage.getItem('murphy_ws_unread') || '0', 10);
          if (unread > 20) return [{ source: source, type: 'high_unread', data: { count: unread }, priority: 'low', confidence: 70, label: unread + ' unread workspace messages' }];
        } catch (_) {}
        return [];
      }

      if (self._isBackedOff(source)) {
        return Promise.resolve(fromLocalStorage());
      }

      return self._fetchWithTimeout(BASE_URL + '/api/collaboration')
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          try { localStorage.setItem('murphy_ws_unread', String(data.unread_count || data.unread || 0)); } catch (_) {}
          self._onSuccess(source);
          return parseActivity(data);
        })
        .catch(function () {
          self._onFailure(source);
          return fromLocalStorage();
        });
    },

    _murphySystemSignals: function () {
      var signals = [];
      /* Fire-and-forget fetches to /api/health and /api/status — parse on arrival */
      fetch(BASE_URL + '/api/health', { method: 'GET' })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
          if (!data) return;
          var degraded = [];
          if (data.modules) {
            Object.keys(data.modules).forEach(function (mod) {
              var m = data.modules[mod];
              if (m && (m.status === 'degraded' || m.status === 'error' || m.status === 'down')) {
                degraded.push(mod);
              }
            });
          }
          if (degraded.length) {
            var sig = {
              source: 'murphy_system', type: 'modules_degraded',
              data: { modules: degraded, count: degraded.length },
              priority: degraded.length > 2 ? 'high' : 'medium',
              confidence: 99,
              label: degraded.length + ' module(s) degraded: ' + degraded.slice(0, 3).join(', ')
            };
            state.context['murphy_system:modules_degraded'] = sig;
          }
          /* Redis / rate-limiter mode signals */
          if (data.redis && data.redis.status !== 'connected') {
            state.context['murphy_system:redis_disconnected'] = { source: 'murphy_system', type: 'redis_disconnected', data: { status: data.redis.status }, priority: 'medium', confidence: 99, label: 'Redis not connected — running in memory mode' };
          }
          if (data.rate_limiter && data.rate_limiter.mode === 'memory') {
            state.context['murphy_system:rate_limiter_memory'] = { source: 'murphy_system', type: 'rate_limiter_memory', data: {}, priority: 'low', confidence: 90, label: 'Rate limiter in memory mode' };
          }
        })
        .catch(function () {});

      fetch(BASE_URL + '/api/status', { method: 'GET' })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
          if (!data) return;
          if (data.integration_bus && data.integration_bus.llm_integration_layer === false) {
            state.context['murphy_system:llm_integration_off'] = { source: 'murphy_system', type: 'llm_integration_off', data: {}, priority: 'medium', confidence: 99, label: 'LLM integration layer not loaded' };
          }
        })
        .catch(function () {});

      /* Return any system signals already accumulated from prior async fetches */
      return Object.values(state.context).filter(function (s) { return s.source === 'murphy_system'; });
    },

    _pushToAPI: function (signals) {
      fetch(BASE_URL + '/api/ambient/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signals: signals, ts: new Date().toISOString() })
      }).catch(function () {});
    }
  };

  /* ─────────────────────────────────────────────────────────────────────────
   *  SYNTHESIS ENGINE
   *  Cross-references signals to form proactive insight packages.
   * ───────────────────────────────────────────────────────────────────────── */
  var SynthesisEngine = {
    run: function () {
      var signals = Object.values(state.context);
      if (!signals.length) return;

      var insights = [];

      /* Pre-meeting brief */
      var upcomingMeeting = signals.find(function (s) { return s.type === 'upcoming_meeting'; });
      if (upcomingMeeting) {
        var pendingVotes = signals.find(function (s) { return s.type === 'pending_votes'; });
        var overdueCount = (signals.find(function (s) { return s.type === 'overdue'; }) || {}).data;
        insights.push({
          id: 'pre-meeting-' + Date.now(),
          type: 'preparation',
          title: 'Pre-Meeting Brief: ' + (upcomingMeeting.data.title || 'Upcoming Meeting'),
          body: 'Murphy has prepared a brief for your meeting' +
            (overdueCount ? ' including ' + overdueCount.count + ' overdue action item(s)' : '') +
            (pendingVotes ? ' and ' + pendingVotes.data.count + ' draft(s) pending your vote' : '') + '.',
          confidence: Math.min(99, Math.round((upcomingMeeting.confidence + 70) / 2)),
          priority: 'high',
          trigger: upcomingMeeting.label,
          deliverVia: ['ui', 'email'],
          agents: ['Murphy-Ambient', 'Shadow-Calendar'],
          source: 'client'
        });
      }

      /* Risk alert — unassigned + overdue together */
      var unassigned = signals.find(function (s) { return s.type === 'unassigned'; });
      var overdue    = signals.find(function (s) { return s.type === 'overdue'; });
      if (unassigned && overdue) {
        insights.push({
          id: 'risk-alert-' + Date.now(),
          type: 'alert',
          title: 'Risk Alert: Unassigned + Overdue Tasks',
          body: overdue.data.count + ' overdue and ' + unassigned.data.count + ' unassigned tasks detected. Murphy has drafted a responsibility matrix.',
          confidence: 91,
          priority: 'high',
          trigger: 'Task board analysis',
          deliverVia: ['ui', 'email'],
          agents: ['Murphy-Ambient'],
          source: 'client'
        });
      }

      /* Org milestone */
      var milestone = signals.find(function (s) { return s.type === 'org_milestone'; });
      if (milestone) {
        insights.push({
          id: 'org-milestone-' + Date.now(),
          type: 'synthesis',
          title: 'Org Intelligence Milestone: ' + milestone.data.sessions + ' Sessions',
          body: 'Your organisation has completed ' + milestone.data.sessions + ' Shadow AI sessions. A capability report has been generated.',
          confidence: 95,
          priority: 'low',
          trigger: milestone.label,
          deliverVia: ['ui'],
          agents: ['Murphy-OrgIntel'],
          source: 'client'
        });
      }

      /* Filter by confidence threshold */
      var minConf = state.settings.confidenceMin !== undefined ? state.settings.confidenceMin : 65;
      insights = insights.filter(function (i) { return i.confidence >= minConf; });

      /* Deduplicate against already delivered */
      var deliveredIds = state.delivered.map(function (d) { return d.baseId; });
      insights = insights.filter(function (i) {
        var baseId = i.type + '-' + i.title.slice(0, 20);
        return !deliveredIds.includes(baseId);
      });

      if (insights.length) {
        state.insights = state.insights.concat(insights).slice(0, MAX_QUEUE);
        SynthesisEngine._pushToAPI(insights);
      }
    },

    _pushToAPI: function (insights) {
      fetch(BASE_URL + '/api/ambient/insights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ insights: insights, synthesize: true, ts: new Date().toISOString() })
      })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data && Array.isArray(data.server_insights) && data.server_insights.length) {
          SynthesisEngine._mergeServerInsights(data.server_insights);
        }
      })
      .catch(function () {});
    },

    _pollServerInsights: function () {
      fetch(BASE_URL + '/api/ambient/insights?pending=true', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data && Array.isArray(data.server_insights) && data.server_insights.length) {
          SynthesisEngine._mergeServerInsights(data.server_insights);
        }
      })
      .catch(function () {});
    },

    _mergeServerInsights: function (serverInsights) {
      var minConf = state.settings.confidenceMin !== undefined ? state.settings.confidenceMin : 65;
      var deliveredIds = state.delivered.map(function (d) { return d.baseId; });
      var newInsights = serverInsights.filter(function (i) {
        if ((i.confidence || 0) < minConf) return false;
        var baseId = i.type + '-' + (i.title || '').slice(0, 20);
        return !deliveredIds.includes(baseId);
      }).map(function (i) {
        return Object.assign({}, i, { source: 'server' });
      });
      if (newInsights.length) {
        state.insights = state.insights.concat(newInsights).slice(0, MAX_QUEUE);
      }
    }
  };

  /* ─────────────────────────────────────────────────────────────────────────
   *  DELIVERY PIPELINE
   *  Routes synthesised insights to appropriate delivery channels.
   * ───────────────────────────────────────────────────────────────────────── */
  var DeliveryPipeline = {
    _lastDelivery: 0,

    run: function () {
      var now = Date.now();
      if (now - DeliveryPipeline._lastDelivery < DELIVERY_DELAY_MS) return;
      if (!state.insights.length) return;

      var insight = state.insights.shift();
      DeliveryPipeline._deliver(insight);
      DeliveryPipeline._lastDelivery = now;
    },

    _deliver: function (insight) {
      var channels = insight.deliverVia || ['ui'];

      /* UI stream */
      if (channels.includes('ui')) {
        DeliveryPipeline._emitToUIStream(insight);
      }

      /* Email */
      if (channels.includes('email') && state.settings.emailEnabled) {
        DeliveryPipeline._sendEmail(insight);
      }

      /* Log */
      var record = {
        id: insight.id,
        baseId: insight.type + '-' + (insight.title || '').slice(0, 20),
        title: insight.title,
        ts: new Date().toISOString(),
        channels: channels
      };
      state.delivered.unshift(record);
      if (state.delivered.length > 200) state.delivered.pop();
      try { localStorage.setItem('murphy_ambient_delivered', JSON.stringify(state.delivered.slice(0, 100))); } catch (_) {}

      /* Royalty tracking */
      RoyaltyTracker.record(insight);
    },

    _emitToUIStream: function (insight) {
      /* Dispatch custom event for the ambient_intelligence page to pick up */
      try {
        document.dispatchEvent(new CustomEvent('murphy:ambient:insight', { detail: insight }));
      } catch (_) {}

      /* Also push to the stream list if we're on the ambient page */
      var streamList = document.getElementById('stream-list');
      if (!streamList) return;

      if (streamList.querySelector('.amb-empty')) streamList.innerHTML = '';

      var TYPE_ICONS = { preparation: '📋', prediction: '🔮', synthesis: '🧠', alert: '⚠️', briefing: '📰' };
      var icon = TYPE_ICONS[insight.type] || '💡';

      var el = document.createElement('div');
      el.className = 'amb-stream-item';
      var sourceBadge = insight.source === 'server' ? '<span class="amb-source-badge ai" aria-label="AI generated">🤖 AI</span>' : (insight.source === 'client' ? '<span class="amb-source-badge pattern" aria-label="Pattern matched">📊 Pattern</span>' : '');
      el.innerHTML =
        '<div class="amb-stream-icon" aria-hidden="true">' + _esc(icon) + '</div>' +
        '<div class="amb-stream-body">' +
          '<div class="amb-stream-header">' +
            '<span class="amb-stream-type ' + _esc(insight.type) + '">' + _esc(insight.type) + '</span>' +
            '<span class="amb-stream-confidence">' + (insight.confidence || 0) + '%' + sourceBadge + '</span>' +
            '<span class="amb-stream-time">Just now</span>' +
          '</div>' +
          '<div class="amb-stream-text">' + _esc(insight.body || '') + '</div>' +
          '<div class="amb-stream-actions">' +
            '<button class="amb-stream-btn primary">View</button>' +
            '<button class="amb-stream-btn">Dismiss</button>' +
          '</div>' +
        '</div>';

      el.querySelectorAll('.amb-stream-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
          el.classList.add('actioned');
          btn.disabled = true;
          state.actioned++;
          var el2 = document.getElementById('stat-actioned');
          if (el2) el2.textContent = state.actioned;
        });
      });

      streamList.insertBefore(el, streamList.firstChild);

      /* Update counters */
      var countEl = document.getElementById('stream-count');
      if (countEl) countEl.textContent = streamList.querySelectorAll('.amb-stream-item').length;
      var badgeEl = document.getElementById('badge-stream');
      if (badgeEl) badgeEl.textContent = streamList.querySelectorAll('.amb-stream-item').length;
      var insightsEl = document.getElementById('stat-insights');
      if (insightsEl) insightsEl.textContent = parseInt(insightsEl.textContent || '0', 10) + 1;

      /* Update average confidence */
      if (insight.confidence) {
        state.confidenceSum += insight.confidence;
        state.insightsCount++;
        var confEl = document.getElementById('stat-confidence');
        if (confEl) confEl.textContent = Math.round(state.confidenceSum / state.insightsCount) + '%';
      }
    },

    _sendEmail: function (insight) {
      fetch(BASE_URL + '/api/ambient/deliver', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel: 'email',
          insight_id: insight.id,
          title: insight.title,
          body: insight.body,
          priority: insight.priority,
          agents: insight.agents || []
        })
      })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data) {
          /* If backend reports mock mode, show the settings panel warning banner */
          if (data.mock) {
            var banner = document.getElementById('mock-email-banner');
            if (banner) banner.classList.add('visible');
          }
          if (data.email_id) {
            DeliveryPipeline._logEmail(insight, data.email_id, data.mock ? 'pending' : 'sent');
          }
        }
      })
      .catch(function () { DeliveryPipeline._logEmail(insight, null, 'pending'); });
    },

    _logEmail: function (insight, emailId, status) {
      var tbody = document.getElementById('email-log-tbody');
      if (!tbody) return;

      /* Clear placeholder */
      var placeholder = tbody.querySelector('td[colspan]');
      if (placeholder) tbody.innerHTML = '';

      var now = new Date();
      var timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td style="white-space:nowrap;color:var(--text-muted)">' + _esc(timeStr) + '</td>' +
        '<td style="font-weight:600;color:var(--text-primary)">' + _esc(insight.title || '') + '</td>' +
        '<td style="color:var(--teal);font-size:12px">You</td>' +
        '<td>' + _esc(insight.trigger || insight.type) + '</td>' +
        '<td><span class="amb-email-status ' + _esc(status) + '">' + _esc(status) + '</span></td>';
      tbody.insertBefore(tr, tbody.firstChild);

      var countEl = document.getElementById('email-log-count');
      if (countEl) countEl.textContent = tbody.querySelectorAll('tr').length;
      var badgeEl = document.getElementById('badge-email');
      if (badgeEl) badgeEl.textContent = tbody.querySelectorAll('tr').length;
      var deliveredEl = document.getElementById('stat-delivered');
      if (deliveredEl) {
        state.deliveredCount++;
        deliveredEl.textContent = state.deliveredCount;
      }
    }
  };

  /* ─────────────────────────────────────────────────────────────────────────
   *  ROYALTY TRACKER
   *  Logs which shadow agents contributed to each delivery for BSL 1.1.
   * ───────────────────────────────────────────────────────────────────────── */
  var RoyaltyTracker = {
    record: function (insight) {
      var agents = insight.agents || ['Murphy-Ambient'];
      var entry = {
        ts: new Date().toISOString(),
        insightId: insight.id,
        title: insight.title,
        agents: agents,
        status: 'earned'
      };
      try {
        var existing = JSON.parse(localStorage.getItem('murphy_royalty_ledger') || '[]');
        existing.unshift(entry);
        localStorage.setItem('murphy_royalty_ledger', JSON.stringify(existing.slice(0, 100)));
      } catch (_) {}

      /* Push to API */
      fetch(BASE_URL + '/api/ambient/royalty', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry)
      }).catch(function () {});
    }
  };

  /* ─────────────────────────────────────────────────────────────────────────
   *  ENGINE LIFECYCLE
   * ───────────────────────────────────────────────────────────────────────── */
  var Engine = {
    start: function () {
      if (state.running) return;
      loadSettings();
      state.running = true;
      state.paused  = false;

      /* Run once immediately */
      setTimeout(function () { ContextCollector.collect(); }, 1000);
      setTimeout(function () { SynthesisEngine.run(); }, 3000);
      setTimeout(function () { DeliveryPipeline.run(); }, 5000);

      /* Then on intervals */
      state.timers.poll    = setInterval(function () { if (!state.paused) ContextCollector.collect(); }, POLL_INTERVAL_MS);
      state.timers.synth   = setInterval(function () { if (!state.paused) SynthesisEngine.run(); }, SYNTH_INTERVAL_MS);
      state.timers.deliver = setInterval(function () { if (!state.paused) DeliveryPipeline.run(); }, DELIVERY_DELAY_MS);
      state.timers.server  = setInterval(function () { if (!state.paused) SynthesisEngine._pollServerInsights(); }, SERVER_POLL_INTERVAL_MS);
    },

    pause: function () {
      state.paused = true;
    },

    resume: function () {
      state.paused = false;
    },

    stop: function () {
      state.running = false;
      state.paused  = false;
      Object.keys(state.timers).forEach(function (k) {
        if (state.timers[k]) { clearInterval(state.timers[k]); state.timers[k] = null; }
      });
    },

    getState: function () { return state; }
  };

  /* ─────────────────────────────────────────────────────────────────────────
   *  HELPERS
   * ───────────────────────────────────────────────────────────────────────── */
  function _esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  /* ─────────────────────────────────────────────────────────────────────────
   *  PUBLIC API
   * ───────────────────────────────────────────────────────────────────────── */
  var publicAPI = {
    version:  VERSION,
    start:    Engine.start.bind(Engine),
    pause:    Engine.pause.bind(Engine),
    resume:   Engine.resume.bind(Engine),
    stop:     Engine.stop.bind(Engine),
    getState: function () {
      return {
        running:        state.running,
        paused:         state.paused,
        insightsCount:  state.insightsCount,
        deliveredCount: state.deliveredCount,
        actionedCount:  state.actioned,
        avgConfidence:  state.insightsCount > 0 ? Math.round(state.confidenceSum / state.insightsCount) : 0
      };
    }
  };

  global.AmbientEngine  = publicAPI;
  global.MurphyAmbient  = publicAPI;   /* alias used by ambient_intelligence.html */

  /* Auto-start when DOM is ready */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { Engine.start(); });
  } else {
    Engine.start();
  }

}(window));
