"""Claude API integration — file parsing, analysis, response extraction."""
import io
import os
import re
import subprocess
import tempfile
from pathlib import Path

import anthropic

from system_prompt import get_system_prompt

MODEL = "claude-opus-4-7"
MAX_TOKENS = 32000


# ── File Reading ──────────────────────────────────────────────────────────────

def file_to_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()

    if ext in (".csv", ".txt", ".tsv"):
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return content.decode(enc)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    if ext in (".xlsx", ".xls"):
        try:
            import pandas as pd
            dfs = pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=str)
            parts = []
            for sheet_name, df in dfs.items():
                parts.append(f"[Sheet: {sheet_name}]")
                parts.append(df.fillna("").to_csv(index=False))
            return "\n".join(parts)
        except ImportError:
            return f"[Excel file — install pandas to parse: {filename}]"
        except Exception as e:
            return f"[Error reading Excel {filename}: {e}]"

    # Fallback: try UTF-8 text
    try:
        return content.decode("utf-8", errors="replace")
    except Exception:
        return f"[Binary file: {filename}]"


# ── Run Analysis ──────────────────────────────────────────────────────────────

def run_analysis(
    files: list[tuple[str, bytes]],  # [(filename, bytes), ...]
    city: str,
    nickname: str,
) -> dict:
    """
    Call Claude API and return parsed results:
      - html_dashboard: str | None
      - sheets_data: dict | None  (JSON for Sheets / Excel)
      - excel_code: str | None    (Python xlsxwriter code)
      - raw_response: str
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    # Build file sections
    sections = []
    for fname, content in files:
        text = file_to_text(fname, content)
        sections.append(f"=== FILE: {fname} ===\n{text}\n=== END FILE ===")

    files_block = "\n\n".join(sections)

    user_message = (
        f"Property City/Submarket: {city}\n"
        f"Property Nickname for this session: {nickname}\n\n"
        f"The following MFR report files have been uploaded:\n\n"
        f"{files_block}\n\n"
        "Execute the full 6-step analysis sequence. "
        "Produce the complete HTML dashboard, the structured JSON summary, "
        "and the Python/xlsxwriter Excel export code."
    )

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": get_system_prompt(),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = message.content[0].text
    return _parse_response(response_text)


# ── Response Parsing ──────────────────────────────────────────────────────────

def _parse_response(text: str) -> dict:
    import json

    result = {"html_dashboard": None, "sheets_data": None, "excel_code": None, "raw_response": text}

    # HTML dashboard
    m = re.search(r"<html_dashboard>([\s\S]*?)</html_dashboard>", text)
    if m:
        result["html_dashboard"] = m.group(1).strip()

    # Structured JSON for Sheets/Excel
    m = re.search(r"<sheets_data>([\s\S]*?)</sheets_data>", text)
    if m:
        try:
            result["sheets_data"] = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Python xlsxwriter code (fallback for Excel)
    m = re.search(r"<excel_code>([\s\S]*?)</excel_code>", text)
    if m:
        result["excel_code"] = m.group(1).strip()

    return result


# ── Excel Generation ──────────────────────────────────────────────────────────

def generate_excel(result: dict, nickname: str) -> Path | None:
    """
    Run the xlsxwriter code from Claude and return the output file path.
    Falls back to building a simple Excel from sheets_data if no code is present.
    """
    out_path = Path(tempfile.mkdtemp()) / f"{nickname.replace(' ', '_')}_mfr.xlsx"

    # Prefer xlsxwriter code from Claude
    if result.get("excel_code"):
        code = result["excel_code"]
        # Patch output path
        code = re.sub(
            r"['\"](?:/tmp/|/mnt/user-data/outputs/)[^'\"]+\.xlsx['\"]",
            f'"{out_path}"',
            code,
        )
        if str(out_path) not in code:
            code = code.replace("'mfr_output.xlsx'", f'"{out_path}"')
            code = code.replace('"mfr_output.xlsx"', f'"{out_path}"')

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            code_path = f.name

        try:
            subprocess.run(
                ["python3", code_path],
                capture_output=True,
                text=True,
                timeout=90,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        finally:
            Path(code_path).unlink(missing_ok=True)

        if out_path.exists():
            return out_path

    # Fallback: build simple Excel from sheets_data JSON
    if result.get("sheets_data"):
        _build_excel_from_json(result["sheets_data"], nickname, out_path)
        if out_path.exists():
            return out_path

    return None


def _build_excel_from_json(data: dict, nickname: str, out_path: Path) -> None:
    import xlsxwriter

    wb = xlsxwriter.Workbook(str(out_path))

    title_fmt = wb.add_format({"bold": True, "font_size": 14, "bg_color": "#0F1C2E", "font_color": "#FFFFFF", "align": "center"})
    section_fmt = wb.add_format({"bold": True, "bg_color": "#1E3A5F", "font_color": "#FFFFFF"})
    red_hdr_fmt = wb.add_format({"bold": True, "bg_color": "#A32D2D", "font_color": "#FFFFFF"})
    red_row_fmt = wb.add_format({"bg_color": "#FCEBEB"})
    blue_row_fmt = wb.add_format({"bg_color": "#E6F1FB"})
    noi_fmt = wb.add_format({"bold": True, "font_size": 12, "bg_color": "#854F0B", "font_color": "#FFFFFF", "align": "center"})

    ws = wb.add_worksheet("MFR Analysis")
    ws.set_column(0, 0, 5)
    ws.set_column(1, 1, 50)
    ws.set_column(2, 3, 20)

    row = 0
    ws.merge_range(row, 0, row, 3, f"MFR DIRECTOR — {nickname.upper()} ANALYSIS", title_fmt)
    row += 2

    if data.get("kpis"):
        ws.merge_range(row, 0, row, 3, "KEY PERFORMANCE INDICATORS", section_fmt)
        row += 1
        for kpi in data["kpis"]:
            ws.write(row, 0, kpi.get("label", ""))
            ws.write(row, 1, kpi.get("value", ""))
            row += 1
        row += 1

    if data.get("redFlags"):
        ws.write(row, 0, "#", red_hdr_fmt)
        ws.write(row, 1, "RED FLAG", red_hdr_fmt)
        ws.write(row, 2, "Monthly Leakage", red_hdr_fmt)
        ws.write(row, 3, "Annualized", red_hdr_fmt)
        row += 1
        for i, flag in enumerate(data["redFlags"]):
            fmt = red_row_fmt if i % 2 == 0 else None
            ws.write(row, 0, i + 1, fmt)
            ws.write(row, 1, flag.get("issue", ""), fmt)
            ws.write(row, 2, flag.get("monthlyImpact", ""), fmt)
            ws.write(row, 3, flag.get("annualizedImpact", ""), fmt)
            row += 1
        row += 1

    if data.get("directives"):
        ws.write(row, 0, "#", section_fmt)
        ws.write(row, 1, "TACTICAL DIRECTIVE", section_fmt)
        ws.write(row, 2, "Owner", section_fmt)
        ws.write(row, 3, "Deadline", section_fmt)
        row += 1
        for i, d in enumerate(data["directives"]):
            fmt = blue_row_fmt if i % 2 == 0 else None
            ws.write(row, 0, i + 1, fmt)
            ws.write(row, 1, d.get("action", ""), fmt)
            ws.write(row, 2, d.get("owner", ""), fmt)
            ws.write(row, 3, d.get("deadline", ""), fmt)
            row += 1
        row += 1

    if data.get("noiSummary"):
        ws.merge_range(row, 0, row, 3, f"TOTAL ANNUALIZED NOI AT RISK: {data['noiSummary']}", noi_fmt)

    wb.close()
