// MFR Director — Google Sheets Add-on
// Institutional-grade MFR portfolio analysis powered by Claude AI

function onInstall(e) {
  onOpen(e);
}

function onOpen(e) {
  SpreadsheetApp.getUi()
    .createAddonMenu()
    .addItem('⚡ Analyze Portfolio', 'showSidebar')
    .addSeparator()
    .addItem('⚙️ Settings (API Key)', 'showSettings')
    .addToUi();
}

function onHomepage(e) {
  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('MFR Director'))
    .addSection(
      CardService.newCardSection()
        .addWidget(CardService.newTextParagraph().setText('Institutional-grade MFR portfolio intelligence.'))
        .addWidget(CardService.newTextButton()
          .setText('Open Analysis Panel')
          .setOnClickAction(CardService.newAction().setFunctionName('showSidebar')))
    ).build();
}

function showSidebar() {
  const html = HtmlService.createTemplateFromFile('Sidebar')
    .evaluate()
    .setTitle('MFR Director')
    .setWidth(360);
  SpreadsheetApp.getUi().showSidebar(html);
}

function showSettings() {
  const html = HtmlService.createTemplateFromFile('Settings')
    .evaluate()
    .setWidth(440)
    .setHeight(260);
  SpreadsheetApp.getUi().showModalDialog(html, '⚙️ MFR Director — API Settings');
}

// ── Settings ────────────────────────────────────────────────────────────────

function saveApiKey(apiKey) {
  if (!apiKey || apiKey.trim().length < 10) {
    return { success: false, message: 'Invalid API key.' };
  }
  PropertiesService.getUserProperties().setProperty('ANTHROPIC_API_KEY', apiKey.trim());
  return { success: true };
}

function getApiKeyStatus() {
  const key = PropertiesService.getUserProperties().getProperty('ANTHROPIC_API_KEY');
  return key ? 'configured' : 'missing';
}

// ── Sheet Helpers ────────────────────────────────────────────────────────────

function getSheetNames() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheets().map(s => s.getName());
}

function readSheet(sheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) return null;
  const data = sheet.getDataRange().getValues();
  return data.map(row => row.join('\t')).join('\n');
}

// ── Main Analysis ─────────────────────────────────────────────────────────────

function runAnalysis(config) {
  // config: { city, nickname, sheets: [{name, reportType}] }

  const apiKey = PropertiesService.getUserProperties().getProperty('ANTHROPIC_API_KEY');
  if (!apiKey) throw new Error('API key not configured. Open Settings first.');

  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Read all selected sheets
  const fileSections = config.sheets.map(function(sel) {
    const sheet = ss.getSheetByName(sel.name);
    if (!sheet) return null;
    const data = sheet.getDataRange().getValues();
    const tsv = data.map(function(row) { return row.join('\t'); }).join('\n');
    const label = sel.reportType && sel.reportType !== sel.name
      ? sel.reportType + ' [Sheet: ' + sel.name + ']'
      : sel.name;
    return '=== REPORT: ' + label + ' ===\n' + tsv + '\n=== END ===';
  }).filter(Boolean).join('\n\n');

  if (!fileSections) throw new Error('No valid sheets selected.');

  const userMessage =
    'Property City/Submarket: ' + config.city + '\n' +
    'Property Nickname for this session: ' + config.nickname + '\n\n' +
    'The following MFR reports are provided as tab-separated values from Google Sheets:\n\n' +
    fileSections + '\n\n' +
    'Execute the full 6-step analysis sequence. ' +
    'Produce the complete HTML dashboard and the structured JSON summary data.';

  // Call Claude API
  var result = callClaude(apiKey, userMessage);
  var responseText = result.content[0].text;

  // Extract HTML dashboard
  var htmlMatch = responseText.match(/<html_dashboard>([\s\S]*?)<\/html_dashboard>/);
  var htmlDashboard = htmlMatch ? htmlMatch[1].trim() : null;

  // Extract structured sheets data (JSON)
  var sheetsMatch = responseText.match(/<sheets_data>([\s\S]*?)<\/sheets_data>/);
  var sheetsData = null;
  if (sheetsMatch) {
    try { sheetsData = JSON.parse(sheetsMatch[1].trim()); } catch (e) {}
  }

  // Write structured results to a new sheet
  var resultsSheetName = null;
  if (sheetsData) {
    resultsSheetName = writeSummarySheet(ss, config.nickname, sheetsData);
  }

  return {
    html: htmlDashboard,
    resultsSheetName: resultsSheetName,
    rawResponse: htmlDashboard ? null : responseText
  };
}

// ── Claude API Call ──────────────────────────────────────────────────────────

function callClaude(apiKey, userMessage) {
  var systemPrompt = getSystemPrompt();

  var payload = JSON.stringify({
    model: 'claude-opus-4-7',
    max_tokens: 32000,
    system: [
      {
        type: 'text',
        text: systemPrompt,
        cache_control: { type: 'ephemeral' }
      }
    ],
    messages: [{ role: 'user', content: userMessage }]
  });

  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-beta': 'prompt-caching-2024-07-31'
    },
    payload: payload,
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', options);
  var json = JSON.parse(response.getContentText());

  if (response.getResponseCode() !== 200) {
    throw new Error('Claude API error: ' + (json.error ? json.error.message : response.getContentText()));
  }

  return json;
}

// ── Utilities (called from Sidebar) ─────────────────────────────────────────

function activateSummarySheet(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (sheet) ss.setActiveSheet(sheet);
}

function showRawResponseDialog(text) {
  var html = HtmlService.createHtmlOutput(
    '<pre style="font-family:monospace;font-size:11px;white-space:pre-wrap;padding:16px">' +
    text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') +
    '</pre>'
  ).setWidth(800).setHeight(600);
  SpreadsheetApp.getUi().showModalDialog(html, 'Raw Response');
}

// ── Write Summary Sheet ───────────────────────────────────────────────────────

function writeSummarySheet(ss, nickname, data) {
  var sheetName = 'MFR Analysis — ' + nickname;

  var existing = ss.getSheetByName(sheetName);
  if (existing) ss.deleteSheet(existing);
  var sheet = ss.insertSheet(sheetName, 0);

  var row = 1;

  // Title
  var titleCell = sheet.getRange(row, 1, 1, 4);
  titleCell.merge()
    .setValue('MFR DIRECTOR — ' + nickname.toUpperCase() + ' ANALYSIS')
    .setFontFamily('Arial')
    .setFontSize(14)
    .setFontWeight('bold')
    .setBackground('#0F1C2E')
    .setFontColor('#FFFFFF')
    .setHorizontalAlignment('center');
  row += 2;

  // KPIs
  if (data.kpis && data.kpis.length) {
    sheet.getRange(row, 1, 1, 4).merge()
      .setValue('KEY PERFORMANCE INDICATORS')
      .setFontWeight('bold').setFontSize(11)
      .setBackground('#1E3A5F').setFontColor('#FFFFFF');
    row++;

    data.kpis.forEach(function(kpi) {
      sheet.getRange(row, 1).setValue(kpi.label).setFontWeight('500');
      sheet.getRange(row, 2).setValue(kpi.value);
      if (kpi.flag === 'red') sheet.getRange(row, 1, 1, 2).setBackground('#FCEBEB');
      else if (kpi.flag === 'green') sheet.getRange(row, 1, 1, 2).setBackground('#EAF3DE');
      row++;
    });
    row++;
  }

  // Red Flags
  if (data.redFlags && data.redFlags.length) {
    sheet.getRange(row, 1).setValue('#').setFontWeight('bold').setBackground('#A32D2D').setFontColor('#FFFFFF');
    sheet.getRange(row, 2).setValue('RED FLAG').setFontWeight('bold').setBackground('#A32D2D').setFontColor('#FFFFFF');
    sheet.getRange(row, 3).setValue('Monthly Leakage').setFontWeight('bold').setBackground('#A32D2D').setFontColor('#FFFFFF');
    sheet.getRange(row, 4).setValue('Annualized').setFontWeight('bold').setBackground('#A32D2D').setFontColor('#FFFFFF');
    row++;

    data.redFlags.forEach(function(flag, i) {
      sheet.getRange(row, 1).setValue(i + 1);
      sheet.getRange(row, 2).setValue(flag.issue);
      sheet.getRange(row, 3).setValue(flag.monthlyImpact || '');
      sheet.getRange(row, 4).setValue(flag.annualizedImpact || '');
      if (i % 2 === 0) sheet.getRange(row, 1, 1, 4).setBackground('#FCEBEB');
      row++;
    });
    row++;
  }

  // Tactical Directives
  if (data.directives && data.directives.length) {
    sheet.getRange(row, 1).setValue('#').setFontWeight('bold').setBackground('#1E3A5F').setFontColor('#FFFFFF');
    sheet.getRange(row, 2).setValue('TACTICAL DIRECTIVE').setFontWeight('bold').setBackground('#1E3A5F').setFontColor('#FFFFFF');
    sheet.getRange(row, 3).setValue('Owner').setFontWeight('bold').setBackground('#1E3A5F').setFontColor('#FFFFFF');
    sheet.getRange(row, 4).setValue('Deadline').setFontWeight('bold').setBackground('#1E3A5F').setFontColor('#FFFFFF');
    row++;

    data.directives.forEach(function(d, i) {
      sheet.getRange(row, 1).setValue(i + 1);
      sheet.getRange(row, 2).setValue(d.action);
      sheet.getRange(row, 3).setValue(d.owner || '');
      sheet.getRange(row, 4).setValue(d.deadline || '');
      if (i % 2 === 0) sheet.getRange(row, 1, 1, 4).setBackground('#E6F1FB');
      row++;
    });
    row++;
  }

  // NOI Impact Summary
  if (data.noiSummary) {
    sheet.getRange(row, 1, 1, 4).merge()
      .setValue('TOTAL ANNUALIZED NOI AT RISK: ' + data.noiSummary)
      .setFontWeight('bold').setFontSize(12)
      .setBackground('#854F0B').setFontColor('#FFFFFF')
      .setHorizontalAlignment('center');
    row++;
  }

  sheet.setColumnWidth(1, 40);
  sheet.setColumnWidth(2, 380);
  sheet.setColumnWidth(3, 160);
  sheet.setColumnWidth(4, 140);

  return sheetName;
}
