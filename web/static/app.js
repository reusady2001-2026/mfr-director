/* MFR Director — Frontend Logic */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────

var state = {
  email: null,
  selectedFiles: [],
  analysisId: null,
  nickname: null,
};

// ── Auth ──────────────────────────────────────────────────────────────────────

function requestCode() {
  var email = document.getElementById('loginEmail').value.trim();
  if (!email || !email.includes('@')) {
    setError('emailError', 'Please enter a valid email address.');
    return;
  }

  var btn = document.getElementById('sendCodeBtn');
  btn.disabled = true;
  btn.textContent = 'Sending…';
  setError('emailError', '');

  fetch('/auth/request-code', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'email=' + encodeURIComponent(email),
  })
    .then(function(r) { return r.json(); })
    .then(function() {
      state.email = email;
      document.getElementById('stepEmail').classList.add('hidden');
      document.getElementById('stepCode').classList.remove('hidden');
      document.getElementById('loginCode').focus();
    })
    .catch(function(e) {
      setError('emailError', 'Network error. Please try again.');
    })
    .finally(function() {
      btn.disabled = false;
      btn.textContent = 'Send Login Code';
    });
}

function verifyCode() {
  var code = document.getElementById('loginCode').value.trim();
  if (code.length !== 8) {
    setError('codeError', 'Please enter the full 8-character code.');
    return;
  }

  var btn = document.getElementById('verifyBtn');
  btn.disabled = true;
  btn.textContent = 'Verifying…';
  setError('codeError', '');

  fetch('/auth/verify-code', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'email=' + encodeURIComponent(state.email) + '&code=' + encodeURIComponent(code),
  })
    .then(function(r) {
      if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Invalid code.'); });
      return r.json();
    })
    .then(function(data) {
      state.email = data.email;
      document.getElementById('headerEmail').textContent = data.email;
      document.getElementById('loginView').classList.add('hidden');
      document.getElementById('appView').classList.remove('hidden');
    })
    .catch(function(e) {
      setError('codeError', e.message || 'Verification failed.');
    })
    .finally(function() {
      btn.disabled = false;
      btn.textContent = 'Access Dashboard';
    });
}

function backToEmail() {
  document.getElementById('stepCode').classList.add('hidden');
  document.getElementById('stepEmail').classList.remove('hidden');
  document.getElementById('loginCode').value = '';
  setError('codeError', '');
}

function logout() {
  fetch('/auth/logout', {method: 'POST'}).finally(function() {
    window.location.reload();
  });
}

// ── File Upload ───────────────────────────────────────────────────────────────

var dropZone = document.getElementById('dropZone');
var fileInput = document.getElementById('fileInput');

if (dropZone) {
  dropZone.addEventListener('dragover', function(e) { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', function() { dropZone.classList.remove('drag-over'); });
  dropZone.addEventListener('drop', function(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    addFiles(Array.from(e.dataTransfer.files));
  });
  dropZone.addEventListener('click', function(e) {
    if (e.target !== fileInput && e.target.tagName !== 'LABEL') fileInput.click();
  });
}

if (fileInput) {
  fileInput.addEventListener('change', function() { addFiles(Array.from(fileInput.files)); });
}

function addFiles(files) {
  files.forEach(function(f) {
    if (!state.selectedFiles.find(function(x) { return x.name === f.name; })) {
      state.selectedFiles.push(f);
    }
  });
  renderFileList();
}

function removeFile(name) {
  state.selectedFiles = state.selectedFiles.filter(function(f) { return f.name !== name; });
  renderFileList();
}

function renderFileList() {
  var el = document.getElementById('fileList');
  if (!el) return;
  el.innerHTML = state.selectedFiles.map(function(f) {
    return '<div class="file-item">' +
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4A9EFF" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>' +
      '<span class="file-item-name">' + esc(f.name) + '</span>' +
      '<span class="file-item-size">' + (f.size / 1024).toFixed(0) + ' KB</span>' +
      '<button class="file-item-remove" onclick="removeFile(\'' + esc(f.name).replace(/'/g, "\\'") + '\')">✕</button>' +
      '</div>';
  }).join('');
}

// ── Analysis ──────────────────────────────────────────────────────────────────

var uploadForm = document.getElementById('uploadForm');
if (uploadForm) {
  uploadForm.addEventListener('submit', function(e) {
    e.preventDefault();
    startAnalysis();
  });
}

var loadingInterval = null;
var loadingStep = 0;
var STEPS = ['ls1', 'ls2', 'ls3', 'ls4'];
var MESSAGES = ['Parsing report files…', 'Fetching market data…', 'Building dashboard…', 'Generating exports…'];

function startAnalysis() {
  var city = document.getElementById('city').value.trim();
  var nickname = document.getElementById('nickname').value.trim();

  if (!city) { alert('Please enter a city / submarket.'); return; }
  if (!nickname) { alert('Please enter a property nickname.'); return; }
  if (!state.selectedFiles.length) { alert('Please upload at least one MFR report file.'); return; }

  state.nickname = nickname;

  // Build form data
  var fd = new FormData();
  fd.append('city', city);
  fd.append('nickname', nickname);
  state.selectedFiles.forEach(function(f) { fd.append('files', f); });

  // Show loading
  showPanel('loadingPanel');
  startLoadingAnim();

  fetch('/analyze-and-cache', {method: 'POST', body: fd})
    .then(function(r) {
      if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Analysis failed.'); });
      return r.json();
    })
    .then(function(data) {
      stopLoadingAnim();
      state.analysisId = data.analysis_id;

      // Render results
      document.getElementById('resultsTitle').textContent = nickname + ' — Analysis Complete';
      document.getElementById('resultsMeta').textContent =
        city + '  ·  ' + new Date().toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric'});

      // Show export buttons
      if (data.has_excel) {
        document.getElementById('excelBtn').style.display = 'inline-flex';
      }
      if (data.has_sheets_data) {
        document.getElementById('sheetsBtn').style.display = 'inline-flex';
        // Pre-fill Google Sheets email with login email
        if (state.email) document.getElementById('sheetsEmail').value = state.email;
      }

      // Render dashboard HTML in iframe
      var frame = document.getElementById('dashboardFrame');
      if (data.html_dashboard) {
        var doc = frame.contentDocument || frame.contentWindow.document;
        doc.open();
        doc.write(data.html_dashboard);
        doc.close();

        // Auto-resize
        setTimeout(function() {
          try {
            var h = frame.contentDocument.body.scrollHeight;
            if (h > 400) frame.style.height = h + 'px';
          } catch(e) {}
        }, 800);
      } else if (data.raw_response) {
        var doc = frame.contentDocument || frame.contentWindow.document;
        doc.open();
        doc.write('<html><body style="font-family:monospace;font-size:12px;padding:20px;white-space:pre-wrap">' + esc(data.raw_response) + '</body></html>');
        doc.close();
      }

      showPanel('resultsPanel');
    })
    .catch(function(e) {
      stopLoadingAnim();
      showPanel('uploadPanel');
      alert('Error: ' + (e.message || String(e)));
    });
}

function startLoadingAnim() {
  loadingStep = 0;
  STEPS.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.className = 'lstep';
  });
  if (document.getElementById(STEPS[0])) {
    document.getElementById(STEPS[0]).classList.add('active');
    document.getElementById('loadingStatus').textContent = MESSAGES[0];
  }
  loadingInterval = setInterval(function() {
    var cur = document.getElementById(STEPS[loadingStep]);
    if (cur) cur.className = 'lstep done';
    loadingStep = Math.min(loadingStep + 1, STEPS.length - 1);
    var next = document.getElementById(STEPS[loadingStep]);
    if (next) next.classList.add('active');
    document.getElementById('loadingStatus').textContent = MESSAGES[loadingStep];
  }, 10000);
}

function stopLoadingAnim() {
  clearInterval(loadingInterval);
  STEPS.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.className = 'lstep done';
  });
}

function newAnalysis() {
  state.selectedFiles = [];
  state.analysisId = null;
  state.nickname = null;
  renderFileList();

  // Hide export buttons
  document.getElementById('excelBtn').style.display = 'none';
  document.getElementById('sheetsBtn').style.display = 'none';

  // Clear iframe
  var frame = document.getElementById('dashboardFrame');
  frame.style.height = '900px';
  var doc = frame.contentDocument || frame.contentWindow.document;
  doc.open(); doc.write(''); doc.close();

  document.getElementById('uploadForm').reset();
  showPanel('uploadPanel');
}

// ── Panel switching ───────────────────────────────────────────────────────────

function showPanel(id) {
  ['uploadPanel', 'loadingPanel', 'resultsPanel'].forEach(function(p) {
    var el = document.getElementById(p);
    if (el) el.classList.toggle('hidden', p !== id);
  });
}

// ── Exports ───────────────────────────────────────────────────────────────────

function downloadExcel() {
  if (!state.analysisId) return;
  window.open('/export/excel/' + state.analysisId, '_blank');
}

function openSheetsModal() {
  document.getElementById('sheetsModal').classList.remove('hidden');
  setError('sheetsError', '');
}

function closeSheetsModal() {
  document.getElementById('sheetsModal').classList.add('hidden');
}

function exportToSheets() {
  var shareEmail = document.getElementById('sheetsEmail').value.trim();
  if (!shareEmail || !shareEmail.includes('@')) {
    setError('sheetsError', 'Please enter a valid Google account email.');
    return;
  }

  var btn = document.getElementById('sheetsConfirmBtn');
  btn.disabled = true;
  btn.textContent = 'Creating sheet…';
  setError('sheetsError', '');

  var fd = new FormData();
  fd.append('analysis_id', state.analysisId);
  fd.append('share_email', shareEmail);
  fd.append('nickname', state.nickname || 'MFR Analysis');

  fetch('/export/sheets', {method: 'POST', body: fd})
    .then(function(r) {
      if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Export failed.'); });
      return r.json();
    })
    .then(function(data) {
      closeSheetsModal();
      window.open(data.url, '_blank');
    })
    .catch(function(e) {
      setError('sheetsError', e.message || 'Export failed.');
    })
    .finally(function() {
      btn.disabled = false;
      btn.textContent = 'Create & Share Sheet';
    });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setError(id, msg) {
  var el = document.getElementById(id);
  if (el) el.textContent = msg;
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Enter key handlers
document.addEventListener('keydown', function(e) {
  if (e.key !== 'Enter') return;
  var t = e.target;
  if (t.id === 'loginEmail') requestCode();
  if (t.id === 'loginCode') verifyCode();
});
