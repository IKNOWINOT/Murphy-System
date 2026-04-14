/**
 * murphy-chat.js — Murphy Conversational AI Interface
 * ====================================================
 * Full-featured chat frontend with SSE streaming, markdown rendering,
 * artifact panel, tool-use visibility, and keyboard shortcuts.
 *
 * Label: MURPHY-CHAT-001
 * Copyright © 2020 Inoni LLC · BSL 1.1
 */
(function () {
  'use strict';

  /* ── State ──────────────────────────────────────────────────── */

  var _conversations = [];      // sidebar list
  var _activeConvId = null;     // current conversation id
  var _messages = [];            // current conversation messages
  var _artifacts = [];           // current conversation artifacts
  var _activeArtifactIdx = -1;
  var _mode = 'chat';            // "chat" | "forge" | "analyze"
  var _streaming = false;        // whether a response is in-flight
  var _abortCtrl = null;         // AbortController for in-flight SSE
  var _userId = 'anon';          // set from session

  /* ── DOM refs ───────────────────────────────────────────────── */

  var $sidebar, $convList, $chatMessages, $textarea, $btnSend;
  var $chatTitle, $artifactPanel, $artifactContent, $artifactTabs;
  var $scrollBtn, $emptyState;

  function _init() {
    $sidebar       = document.getElementById('chat-sidebar');
    $convList      = document.getElementById('conv-list');
    $chatMessages  = document.getElementById('chat-messages');
    $textarea      = document.getElementById('chat-input');
    $btnSend       = document.getElementById('btn-send');
    $chatTitle     = document.getElementById('chat-title');
    $artifactPanel = document.getElementById('artifact-panel');
    $artifactContent = document.getElementById('artifact-content');
    $artifactTabs  = document.getElementById('artifact-tabs');
    $scrollBtn     = document.getElementById('btn-scroll-bottom');
    $emptyState    = document.getElementById('chat-empty');

    // Event listeners
    $btnSend.addEventListener('click', _sendMessage);
    $textarea.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        _sendMessage();
      }
    });
    $textarea.addEventListener('input', _autoGrow);

    document.getElementById('btn-new-chat').addEventListener('click', _newConversation);
    document.getElementById('btn-toggle-sidebar').addEventListener('click', _toggleSidebar);
    document.getElementById('btn-toggle-artifacts').addEventListener('click', _toggleArtifacts);
    document.getElementById('btn-close-artifacts').addEventListener('click', function () {
      $artifactPanel.classList.add('collapsed');
    });
    document.getElementById('sidebar-search').addEventListener('input', _filterConversations);

    // Mode chips
    document.querySelectorAll('.mode-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        document.querySelectorAll('.mode-chip').forEach(function (c) { c.classList.remove('active'); });
        chip.classList.add('active');
        _mode = chip.dataset.mode;
      });
    });

    // Scroll detection
    $chatMessages.addEventListener('scroll', function () {
      var atBottom = $chatMessages.scrollHeight - $chatMessages.scrollTop - $chatMessages.clientHeight < 80;
      if ($scrollBtn) {
        $scrollBtn.classList.toggle('visible', !atBottom);
      }
    });
    if ($scrollBtn) {
      $scrollBtn.addEventListener('click', _scrollToBottom);
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', function (e) {
      if (e.ctrlKey && e.key === 'k') { e.preventDefault(); document.getElementById('sidebar-search').focus(); }
      if (e.ctrlKey && e.key === 'n') { e.preventDefault(); _newConversation(); }
      if (e.ctrlKey && e.shiftKey && e.key === 'A') { e.preventDefault(); _toggleArtifacts(); }
    });

    // Load conversations
    _loadConversations();
  }

  /* ── Conversations CRUD ─────────────────────────────────────── */

  function _loadConversations() {
    fetch('/api/chat/conversations', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.conversations) {
          _conversations = data.conversations;
          _renderSidebar();
          // Auto-select most recent, or show empty state
          if (_conversations.length > 0 && !_activeConvId) {
            _selectConversation(_conversations[0].id);
          } else if (_conversations.length === 0) {
            _showEmpty();
          }
        }
      })
      .catch(function () { _showEmpty(); });
  }

  function _newConversation() {
    fetch('/api/chat/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ mode: _mode }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.conversation) {
          _conversations.unshift(data.conversation);
          _renderSidebar();
          _selectConversation(data.conversation.id);
        }
      })
      .catch(function (err) { console.error('New conversation failed:', err); });
  }

  function _selectConversation(convId) {
    _activeConvId = convId;
    _messages = [];
    _artifacts = [];
    _activeArtifactIdx = -1;

    // Mark active in sidebar
    document.querySelectorAll('.conv-item').forEach(function (el) {
      el.classList.toggle('active', el.dataset.id === convId);
    });

    // Load messages
    fetch('/api/chat/conversations/' + convId, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.conversation) {
          $chatTitle.textContent = data.conversation.title || 'New conversation';
          _messages = data.conversation.messages || [];
          // Extract artifacts from messages
          _messages.forEach(function (msg) {
            if (msg.artifacts && msg.artifacts.length) {
              msg.artifacts.forEach(function (a) { _artifacts.push(a); });
            }
          });
          _renderMessages();
          _renderArtifactTabs();
          if ($emptyState) $emptyState.style.display = 'none';
        }
      })
      .catch(function () { _renderMessages(); });
  }

  function _deleteConversation(convId) {
    fetch('/api/chat/conversations/' + convId, {
      method: 'DELETE',
      credentials: 'same-origin',
    })
      .then(function () {
        _conversations = _conversations.filter(function (c) { return c.id !== convId; });
        _renderSidebar();
        if (_activeConvId === convId) {
          _activeConvId = null;
          _messages = [];
          if (_conversations.length > 0) {
            _selectConversation(_conversations[0].id);
          } else {
            _showEmpty();
          }
        }
      })
      .catch(function (err) { console.error('Delete failed:', err); });
  }

  /* ── Sidebar rendering ──────────────────────────────────────── */

  function _renderSidebar() {
    if (!$convList) return;
    $convList.innerHTML = '';
    _conversations.forEach(function (conv) {
      var el = document.createElement('div');
      el.className = 'conv-item' + (conv.id === _activeConvId ? ' active' : '');
      el.dataset.id = conv.id;
      el.textContent = conv.title || 'New conversation';
      el.addEventListener('click', function () { _selectConversation(conv.id); });

      var del = document.createElement('span');
      del.className = 'conv-delete';
      del.textContent = '×';
      del.title = 'Delete';
      del.addEventListener('click', function (e) {
        e.stopPropagation();
        _deleteConversation(conv.id);
      });
      el.appendChild(del);
      $convList.appendChild(el);
    });
  }

  function _filterConversations() {
    var q = (document.getElementById('sidebar-search').value || '').toLowerCase();
    document.querySelectorAll('.conv-item').forEach(function (el) {
      el.style.display = el.textContent.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
    });
  }

  /* ── Message rendering ──────────────────────────────────────── */

  function _renderMessages() {
    if (!$chatMessages) return;
    $chatMessages.innerHTML = '';
    if (_messages.length === 0) {
      if ($emptyState) $emptyState.style.display = '';
      return;
    }
    if ($emptyState) $emptyState.style.display = 'none';
    _messages.forEach(function (msg) {
      _appendMessageDOM(msg);
    });
    _scrollToBottom();
  }

  function _appendMessageDOM(msg) {
    var row = document.createElement('div');
    row.className = 'msg-row ' + (msg.role || 'assistant');
    row.dataset.id = msg.id || '';

    if (msg.role === 'assistant') {
      var avatar = document.createElement('div');
      avatar.className = 'msg-avatar';
      avatar.textContent = '✦';
      row.appendChild(avatar);
    }

    var bubble = document.createElement('div');
    bubble.className = 'msg-bubble';

    // Render content with markdown
    bubble.innerHTML = _renderMarkdown(msg.content || '');

    // Tool calls
    if (msg.tool_calls && msg.tool_calls.length) {
      msg.tool_calls.forEach(function (tc) {
        bubble.appendChild(_buildToolBlock(tc));
      });
    }

    // Inline artifact cards
    if (msg.artifacts && msg.artifacts.length) {
      msg.artifacts.forEach(function (artifact, idx) {
        bubble.appendChild(_buildArtifactCard(artifact, _artifacts.length - msg.artifacts.length + idx));
      });
    }

    // Copy button
    if (msg.role === 'assistant' && msg.content) {
      var actions = document.createElement('div');
      actions.className = 'msg-actions';
      var copyBtn = document.createElement('button');
      copyBtn.textContent = 'Copy';
      copyBtn.addEventListener('click', function () {
        navigator.clipboard.writeText(msg.content).then(function () {
          copyBtn.textContent = 'Copied ✓';
          setTimeout(function () { copyBtn.textContent = 'Copy'; }, 1500);
        });
      });
      actions.appendChild(copyBtn);
      bubble.appendChild(actions);
    }

    row.appendChild(bubble);
    $chatMessages.appendChild(row);
    return row;
  }

  function _buildToolBlock(tc) {
    var block = document.createElement('div');
    block.className = 'tool-block';

    var header = document.createElement('div');
    header.className = 'tool-header';
    var chevron = document.createElement('span');
    chevron.className = 'tool-chevron';
    chevron.textContent = '▶';
    header.appendChild(chevron);
    var label = document.createElement('span');
    label.textContent = (tc.tool || tc.name || 'tool') + (tc.status ? ' — ' + tc.status : '');
    header.appendChild(label);

    var body = document.createElement('div');
    body.className = 'tool-body';
    body.textContent = tc.result || tc.detail || JSON.stringify(tc, null, 2);

    header.addEventListener('click', function () {
      chevron.classList.toggle('open');
      body.classList.toggle('open');
    });

    block.appendChild(header);
    block.appendChild(body);
    return block;
  }

  function _buildArtifactCard(artifact, globalIdx) {
    var card = document.createElement('div');
    card.className = 'artifact-card';

    var icon = document.createElement('div');
    icon.className = 'artifact-icon';
    icon.textContent = artifact.type === 'code' ? '📄' : artifact.type === 'deliverable' ? '📦' : '📋';
    card.appendChild(icon);

    var info = document.createElement('div');
    info.className = 'artifact-info';
    var title = document.createElement('div');
    title.className = 'artifact-title';
    title.textContent = artifact.title || 'Artifact';
    info.appendChild(title);
    var meta = document.createElement('div');
    meta.className = 'artifact-meta';
    var words = (artifact.content || '').split(/\s+/).filter(Boolean).length;
    meta.textContent = (artifact.type || 'text') + ' · ' + words + ' words';
    info.appendChild(meta);
    card.appendChild(info);

    var btn = document.createElement('button');
    btn.className = 'btn-open-artifact';
    btn.textContent = 'Open →';
    btn.addEventListener('click', function () {
      _showArtifact(globalIdx);
    });
    card.appendChild(btn);

    return card;
  }

  /* ── Artifact panel ─────────────────────────────────────────── */

  function _showArtifact(idx) {
    if (idx < 0 || idx >= _artifacts.length) return;
    _activeArtifactIdx = idx;
    var a = _artifacts[idx];
    $artifactPanel.classList.remove('collapsed');
    $artifactContent.textContent = a.content || '';
    _renderArtifactTabs();
  }

  function _renderArtifactTabs() {
    if (!$artifactTabs) return;
    $artifactTabs.innerHTML = '';
    _artifacts.forEach(function (a, i) {
      var tab = document.createElement('button');
      tab.className = 'artifact-tab' + (i === _activeArtifactIdx ? ' active' : '');
      tab.textContent = a.title || 'Artifact ' + (i + 1);
      tab.addEventListener('click', function () { _showArtifact(i); });
      $artifactTabs.appendChild(tab);
    });
  }

  function _downloadArtifact() {
    if (_activeArtifactIdx < 0) return;
    var a = _artifacts[_activeArtifactIdx];
    var blob = new Blob([a.content || ''], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = (a.filename || a.title || 'murphy-artifact') + '.txt';
    link.click();
    URL.revokeObjectURL(url);
  }

  /* ── Sending messages ───────────────────────────────────────── */

  function _sendMessage() {
    if (_streaming) return;
    var text = ($textarea.value || '').trim();
    if (!text) return;

    // Ensure we have a conversation
    if (!_activeConvId) {
      // Create one first, then send
      fetch('/api/chat/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ mode: _mode }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.conversation) {
            _conversations.unshift(data.conversation);
            _activeConvId = data.conversation.id;
            _renderSidebar();
            _doSend(text);
          }
        });
      return;
    }

    _doSend(text);
  }

  function _doSend(text) {
    // Add user message to UI immediately
    var userMsg = { id: _tempId(), role: 'user', content: text, timestamp: Date.now() / 1000 };
    _messages.push(userMsg);
    _appendMessageDOM(userMsg);
    _scrollToBottom();

    // Clear input
    $textarea.value = '';
    $textarea.style.height = '24px';
    if ($emptyState) $emptyState.style.display = 'none';

    // Disable send
    _streaming = true;
    $btnSend.disabled = true;

    // Create assistant placeholder
    var assistantMsg = { id: _tempId(), role: 'assistant', content: '', tool_calls: [], artifacts: [], timestamp: Date.now() / 1000 };
    _messages.push(assistantMsg);
    var row = _appendMessageDOM(assistantMsg);
    var bubble = row.querySelector('.msg-bubble');
    var cursor = document.createElement('span');
    cursor.className = 'typing-cursor';
    bubble.appendChild(cursor);
    _scrollToBottom();

    // Stream response via SSE (using fetch + ReadableStream for POST)
    _abortCtrl = new AbortController();

    fetch('/api/chat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      signal: _abortCtrl.signal,
      body: JSON.stringify({
        conversation_id: _activeConvId,
        message: text,
        mode: _mode,
      }),
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('HTTP ' + response.status);
        }
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';

        function processChunk() {
          return reader.read().then(function (result) {
            if (result.done) {
              _finishStream(assistantMsg, row, bubble, cursor);
              return;
            }
            buffer += decoder.decode(result.value, { stream: true });

            // Process complete SSE lines
            var lines = buffer.split('\n');
            buffer = lines.pop() || ''; // keep incomplete line in buffer

            for (var i = 0; i < lines.length; i++) {
              var line = lines[i];
              if (line.indexOf('data: ') === 0) {
                var jsonStr = line.substring(6);
                try {
                  var event = JSON.parse(jsonStr);
                  _handleStreamEvent(event, assistantMsg, bubble, cursor);
                } catch (e) {
                  // Not JSON, treat as raw token
                }
              }
            }
            _scrollToBottom();
            return processChunk();
          });
        }

        return processChunk();
      })
      .catch(function (err) {
        if (err.name !== 'AbortError') {
          console.error('Chat stream error:', err);
          bubble.innerHTML = _renderMarkdown('*An error occurred. Please try again.*');
        }
        _finishStream(assistantMsg, row, bubble, cursor);
      });
  }

  function _handleStreamEvent(event, assistantMsg, bubble, cursor) {
    if (event.type === 'token' || event.token) {
      // Append text token
      var tokenText = event.token || event.content || '';
      assistantMsg.content += tokenText;
      // Re-render markdown (cursor stays at end)
      if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
      bubble.innerHTML = _renderMarkdown(assistantMsg.content);
      bubble.appendChild(cursor);
    } else if (event.type === 'tool_start') {
      var tc = { tool: event.tool || event.name, status: 'running...', detail: event.detail || '' };
      assistantMsg.tool_calls.push(tc);
      bubble.appendChild(_buildToolBlock(tc));
    } else if (event.type === 'tool_result') {
      // Update the last tool block
      var idx = (event.index !== undefined) ? event.index : assistantMsg.tool_calls.length - 1;
      if (assistantMsg.tool_calls[idx]) {
        assistantMsg.tool_calls[idx].status = 'done';
        assistantMsg.tool_calls[idx].result = event.result || event.detail || '';
      }
      // Re-render tool blocks
      var existingTools = bubble.querySelectorAll('.tool-block');
      if (existingTools[idx]) {
        var lbl = existingTools[idx].querySelector('.tool-header span:last-child');
        if (lbl) lbl.textContent = (assistantMsg.tool_calls[idx].tool || 'tool') + ' — done';
      }
    } else if (event.type === 'artifact') {
      var artifact = {
        title: event.title || 'Artifact',
        type: event.artifact_type || 'text',
        content: event.content || '',
        filename: event.filename || '',
      };
      assistantMsg.artifacts.push(artifact);
      _artifacts.push(artifact);
      bubble.appendChild(_buildArtifactCard(artifact, _artifacts.length - 1));
      _renderArtifactTabs();
    } else if (event.type === 'done' || event.phase === 'done') {
      // Final event with metadata
      if (event.content) {
        assistantMsg.content = event.content;
        if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
        bubble.innerHTML = _renderMarkdown(assistantMsg.content);
      }
      // Handle deliverable from forge pipeline
      if (event.deliverable && event.deliverable.content) {
        var art = {
          title: event.deliverable.title || 'Forge Deliverable',
          type: 'deliverable',
          content: event.deliverable.content,
          filename: event.deliverable.filename || 'murphy-deliverable.txt',
        };
        assistantMsg.artifacts.push(art);
        _artifacts.push(art);
        bubble.appendChild(_buildArtifactCard(art, _artifacts.length - 1));
        _renderArtifactTabs();
        _showArtifact(_artifacts.length - 1);
      }
      if (event.metadata) {
        assistantMsg.metadata = event.metadata;
      }
    } else if (event.type === 'error') {
      assistantMsg.content += '\n\n*Error: ' + (event.message || event.error || 'Unknown error') + '*';
      if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
      bubble.innerHTML = _renderMarkdown(assistantMsg.content);
    } else if (event.phase) {
      // Forge pipeline progress events
      var tc2 = { tool: 'Forge Pipeline', status: event.status || ('Phase ' + event.phase), detail: event.detail || '' };
      assistantMsg.tool_calls.push(tc2);
      bubble.appendChild(_buildToolBlock(tc2));
    }
  }

  function _finishStream(assistantMsg, row, bubble, cursor) {
    _streaming = false;
    $btnSend.disabled = false;
    if (cursor.parentNode) cursor.parentNode.removeChild(cursor);

    // Add copy button
    if (assistantMsg.content) {
      var actions = document.createElement('div');
      actions.className = 'msg-actions';
      var copyBtn = document.createElement('button');
      copyBtn.textContent = 'Copy';
      copyBtn.addEventListener('click', function () {
        navigator.clipboard.writeText(assistantMsg.content).then(function () {
          copyBtn.textContent = 'Copied ✓';
          setTimeout(function () { copyBtn.textContent = 'Copy'; }, 1500);
        });
      });
      actions.appendChild(copyBtn);
      bubble.appendChild(actions);
    }

    // Update sidebar title
    _updateSidebarTitle();
    $textarea.focus();
  }

  function _updateSidebarTitle() {
    // Refresh the active conversation's title in the sidebar
    if (!_activeConvId) return;
    fetch('/api/chat/conversations/' + _activeConvId, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.conversation) {
          $chatTitle.textContent = data.conversation.title;
          // Update sidebar item
          var existing = _conversations.find(function (c) { return c.id === _activeConvId; });
          if (existing) existing.title = data.conversation.title;
          _renderSidebar();
        }
      })
      .catch(function () {});
  }

  /* ── Markdown renderer (lightweight) ────────────────────────── */

  function _renderMarkdown(text) {
    if (!text) return '';
    var html = _escHtml(text);

    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (m, lang, code) {
      return '<pre><code class="lang-' + lang + '">' + code + '</code></pre>';
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Blockquotes
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

    // Horizontal rule
    html = html.replace(/^---$/gm, '<hr>');

    // Unordered lists
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
    // Fix nested ul tags
    html = html.replace(/<\/ul>\s*<ul>/g, '');

    // Tables (basic)
    html = html.replace(/\|(.+)\|\n\|[-| ]+\|\n((?:\|.+\|\n?)*)/g, function (m, header, rows) {
      var ths = header.split('|').filter(Boolean).map(function (h) { return '<th>' + h.trim() + '</th>'; }).join('');
      var trs = rows.trim().split('\n').map(function (r) {
        var tds = r.split('|').filter(Boolean).map(function (d) { return '<td>' + d.trim() + '</td>'; }).join('');
        return '<tr>' + tds + '</tr>';
      }).join('');
      return '<table><thead><tr>' + ths + '</tr></thead><tbody>' + trs + '</tbody></table>';
    });

    // Paragraphs (double newline)
    html = html.replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';
    // Clean up empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');
    // Don't wrap block elements in p
    html = html.replace(/<p>(<h[1-3]>)/g, '$1');
    html = html.replace(/(<\/h[1-3]>)<\/p>/g, '$1');
    html = html.replace(/<p>(<pre>)/g, '$1');
    html = html.replace(/(<\/pre>)<\/p>/g, '$1');
    html = html.replace(/<p>(<ul>)/g, '$1');
    html = html.replace(/(<\/ul>)<\/p>/g, '$1');
    html = html.replace(/<p>(<table>)/g, '$1');
    html = html.replace(/(<\/table>)<\/p>/g, '$1');
    html = html.replace(/<p>(<blockquote>)/g, '$1');
    html = html.replace(/(<\/blockquote>)<\/p>/g, '$1');
    html = html.replace(/<p>(<hr>)<\/p>/g, '$1');

    // Single newlines → <br>
    html = html.replace(/\n/g, '<br>');

    return html;
  }

  function _escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  /* ── Helpers ────────────────────────────────────────────────── */

  function _autoGrow() {
    $textarea.style.height = '24px';
    $textarea.style.height = Math.min($textarea.scrollHeight, 200) + 'px';
  }

  function _scrollToBottom() {
    if ($chatMessages) {
      $chatMessages.scrollTop = $chatMessages.scrollHeight;
    }
  }

  function _showEmpty() {
    if ($emptyState) $emptyState.style.display = '';
    if ($chatMessages) $chatMessages.innerHTML = '';
    $chatTitle.textContent = 'Murphy';
  }

  function _toggleSidebar() {
    $sidebar.classList.toggle('collapsed');
  }

  function _toggleArtifacts() {
    $artifactPanel.classList.toggle('collapsed');
  }

  function _tempId() {
    return 'tmp-' + Math.random().toString(36).substr(2, 9);
  }

  /* ── Boot ───────────────────────────────────────────────────── */

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

})();
