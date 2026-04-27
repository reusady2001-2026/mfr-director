"""
Google Sheets export via service account.

Requires:
  - GOOGLE_SERVICE_ACCOUNT_JSON env var (path to service account key file)
    OR GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT (raw JSON string)
  - The service account needs: https://www.googleapis.com/auth/spreadsheets
                               https://www.googleapis.com/auth/drive.file

Flow:
  1. Create a new Google Sheet
  2. Write formatted data (KPIs, Red Flags, Directives, NOI)
  3. Share with the subscriber's email
  4. Return the sheet URL
"""
import json
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

COLOR = {
    "navy":   {"red": 0.059, "green": 0.110, "blue": 0.180},
    "blue":   {"red": 0.118, "green": 0.227, "blue": 0.373},
    "dark_red": {"red": 0.639, "green": 0.176, "blue": 0.176},
    "amber":  {"red": 0.522, "green": 0.310, "blue": 0.043},
    "light_red": {"red": 0.988, "green": 0.922, "blue": 0.922},
    "light_blue": {"red": 0.902, "green": 0.945, "blue": 0.984},
    "light_green": {"red": 0.918, "green": 0.953, "blue": 0.871},
    "white": {"red": 1, "green": 1, "blue": 1},
}


def _get_credentials():
    from google.oauth2 import service_account

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if path:
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

    raise RuntimeError(
        "Google service account not configured. "
        "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT."
    )


def export_to_sheets(data: dict, nickname: str, share_email: str) -> str:
    """
    Create a Google Sheet from sheets_data JSON.
    Share it with share_email.
    Returns the sheet URL.
    """
    from googleapiclient.discovery import build

    creds = _get_credentials()
    sheets_svc = build("sheets", "v4", credentials=creds)
    drive_svc = build("drive", "v3", credentials=creds)

    # Create spreadsheet
    title = f"MFR Director — {nickname}"
    spreadsheet = sheets_svc.spreadsheets().create(body={
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "MFR Analysis"}}],
    }).execute()

    spreadsheet_id = spreadsheet["spreadsheetId"]
    sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]

    # Build requests
    requests = []
    values = []  # (row_index, col_index, value)
    formats = []  # batch format requests

    row = 0

    # Title row
    values.append((row, 0, f"MFR DIRECTOR — {nickname.upper()} ANALYSIS"))
    formats.append(_merge_and_format(sheet_id, row, 0, row, 3, "navy", "white", 14, bold=True, halign="CENTER"))
    row += 2

    # KPIs
    if data.get("kpis"):
        values.append((row, 0, "KEY PERFORMANCE INDICATORS"))
        formats.append(_merge_and_format(sheet_id, row, 0, row, 3, "blue", "white", 11, bold=True))
        row += 1
        for kpi in data["kpis"]:
            values.append((row, 0, kpi.get("label", "")))
            values.append((row, 1, kpi.get("value", "")))
            flag = kpi.get("flag", "")
            if flag == "red":
                formats.append(_range_format(sheet_id, row, 0, row, 1, "light_red"))
            elif flag == "green":
                formats.append(_range_format(sheet_id, row, 0, row, 1, "light_green"))
            row += 1
        row += 1

    # Red Flags
    if data.get("redFlags"):
        for col, label in [(0, "#"), (1, "RED FLAG"), (2, "Monthly Leakage"), (3, "Annualized")]:
            values.append((row, col, label))
        formats.append(_range_format(sheet_id, row, 0, row, 3, "dark_red", font_color="white", bold=True))
        row += 1
        for i, flag in enumerate(data["redFlags"]):
            values.append((row, 0, i + 1))
            values.append((row, 1, flag.get("issue", "")))
            values.append((row, 2, flag.get("monthlyImpact", "")))
            values.append((row, 3, flag.get("annualizedImpact", "")))
            if i % 2 == 0:
                formats.append(_range_format(sheet_id, row, 0, row, 3, "light_red"))
            row += 1
        row += 1

    # Tactical Directives
    if data.get("directives"):
        for col, label in [(0, "#"), (1, "TACTICAL DIRECTIVE"), (2, "Owner"), (3, "Deadline")]:
            values.append((row, col, label))
        formats.append(_range_format(sheet_id, row, 0, row, 3, "blue", font_color="white", bold=True))
        row += 1
        for i, d in enumerate(data["directives"]):
            values.append((row, 0, i + 1))
            values.append((row, 1, d.get("action", "")))
            values.append((row, 2, d.get("owner", "")))
            values.append((row, 3, d.get("deadline", "")))
            if i % 2 == 0:
                formats.append(_range_format(sheet_id, row, 0, row, 3, "light_blue"))
            row += 1
        row += 1

    # NOI Summary
    if data.get("noiSummary"):
        values.append((row, 0, f"TOTAL ANNUALIZED NOI AT RISK: {data['noiSummary']}"))
        formats.append(_merge_and_format(sheet_id, row, 0, row, 3, "amber", "white", 12, bold=True, halign="CENTER"))

    # Build batch value update
    grid_data = {}
    for r, c, v in values:
        grid_data.setdefault(r, {})[c] = v

    max_col = 4
    value_rows = []
    for r in range(row + 1):
        row_vals = [grid_data.get(r, {}).get(c, "") for c in range(max_col)]
        value_rows.append(row_vals)

    sheets_svc.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="MFR Analysis!A1",
        valueInputOption="RAW",
        body={"values": value_rows},
    ).execute()

    # Apply formatting
    if formats:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": formats},
        ).execute()

    # Set column widths
    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [
            _column_width(sheet_id, 0, 40),
            _column_width(sheet_id, 1, 400),
            _column_width(sheet_id, 2, 180),
            _column_width(sheet_id, 3, 150),
        ]},
    ).execute()

    # Share with user
    drive_svc.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "user", "role": "writer", "emailAddress": share_email},
        sendNotificationEmail=True,
    ).execute()

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    return url


# ── Format helpers ────────────────────────────────────────────────────────────

def _rgb(name):
    return COLOR.get(name, {"red": 1, "green": 1, "blue": 1})


def _merge_and_format(sheet_id, r1, c1, r2, c2, bg, fg="white", font_size=11, bold=False, halign="LEFT"):
    return {
        "mergeCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": r1, "endRowIndex": r2 + 1,
                      "startColumnIndex": c1, "endColumnIndex": c2 + 1},
            "mergeType": "MERGE_ALL",
        }
    }


def _range_format(sheet_id, r1, c1, r2, c2, bg, font_color=None, bold=False):
    cell_format = {
        "backgroundColor": _rgb(bg),
        "textFormat": {"bold": bold},
    }
    if font_color:
        cell_format["textFormat"]["foregroundColor"] = _rgb(font_color)

    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": r1, "endRowIndex": r2 + 1,
                      "startColumnIndex": c1, "endColumnIndex": c2 + 1},
            "cell": {"userEnteredFormat": cell_format},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    }


def _column_width(sheet_id, col_index, pixel_size):
    return {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": col_index, "endIndex": col_index + 1},
            "properties": {"pixelSize": pixel_size},
            "fields": "pixelSize",
        }
    }
