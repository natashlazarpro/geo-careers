"""Read and write the employer workbook (one sheet per city, Natasha's column layout).

Other sheets (Reference Lists, Progress, ...) are left untouched. Existing rows are never removed.
"""
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import config

ALL_COLUMNS = config.COLUMNS + config.EXTRA_COLUMNS
URL_COLUMNS = {"c_url", "kp_url", "kununu_url", "li_url"}
WIDTHS = {"id": 5, "c_name": 28, "c_url": 28, "adress": 26, "postal_code": 11, "city": 12, "sector": 26,
          "g_role": 15, "g_stack": 40, "size": 9, "kp_url": 34, "kununu_url": 34, "kununu_rate": 11,
          "li_url": 34, "eng": 60, "de": 60, "sprach": 8, "lat": 10, "lon": 10, "open_jobs": 10,
          "job_titles": 45, "job_links": 45, "first_seen": 11, "last_seen": 11, "source": 12,
          "agent_check": 12, "agent_notes": 40}
HEADER_FILL = PatternFill("solid", fgColor="D9E7F5")
EXTRA_FILL = PatternFill("solid", fgColor="EEEEEE")


def read_city_sheets():
    """Return {sheet_name: DataFrame} for the 10 city sheets (empty frames for new cities)."""
    frames = {}
    existing = {}
    if config.WORKBOOK.exists():
        xl = pd.ExcelFile(config.WORKBOOK)
        for name in xl.sheet_names:
            df = xl.parse(name, dtype=object)
            df.columns = [str(c).strip() for c in df.columns]   # e.g. "kp_url " -> "kp_url"
            existing[name.lower()] = df
    for city, (sheet, _, _) in config.CITIES.items():
        df = existing.get(sheet, pd.DataFrame(columns=ALL_COLUMNS))
        for col in ALL_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[ALL_COLUMNS + [c for c in df.columns if c not in ALL_COLUMNS]]
        df = df.dropna(subset=["c_name"]).reset_index(drop=True)
        frames[sheet] = df.astype(object)
    return frames


def _clean(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def write_city_sheets(frames):
    wb = load_workbook(config.WORKBOOK) if config.WORKBOOK.exists() else Workbook()
    if "Sheet" in wb.sheetnames and len(wb.sheetnames) == 1:
        wb.remove(wb["Sheet"])

    city_sheets = [s for s, _, _ in config.CITIES.values()]
    for sheet in city_sheets:
        df = frames[sheet]
        ws = wb[sheet] if sheet in wb.sheetnames else wb.create_sheet(sheet, index=city_sheets.index(sheet))
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row)
        cols = list(df.columns)
        for ci, col in enumerate(cols, start=1):
            cell = ws.cell(row=1, column=ci, value=col)
            cell.font = Font(bold=True)
            cell.fill = EXTRA_FILL if col in config.EXTRA_COLUMNS else HEADER_FILL
            dim = ws.column_dimensions[get_column_letter(ci)]
            dim.width = WIDTHS.get(col, 14)
            # Only Natasha's columns are shown; the agent's tracking columns stay in the file, hidden
            dim.hidden = col not in config.COLUMNS
        for ri, row in enumerate(df.itertuples(index=False), start=2):
            for ci, (col, val) in enumerate(zip(cols, row), start=1):
                val = _clean(val)
                cell = ws.cell(row=ri, column=ci, value=val)
                if col in URL_COLUMNS and isinstance(val, str) and val.strip():
                    url = val.strip()
                    cell.hyperlink = url if url.startswith("http") else "https://" + url
                    cell.font = Font(color="0563C1", underline="single")
                if col in ("eng", "de", "g_stack", "job_titles", "job_links", "agent_notes"):
                    cell.alignment = Alignment(wrap_text=False, vertical="top")
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{max(ws.max_row, 1)}"

    config.WORKBOOK.parent.mkdir(exist_ok=True)
    wb.save(config.WORKBOOK)
