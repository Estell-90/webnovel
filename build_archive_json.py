# -*- coding: utf-8 -*-
"""sheet1.html 과 동일 규칙으로 archive.json 생성 (아카이브용 백업 데이터)."""
import json
import os
import re
from html.parser import HTMLParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(SCRIPT_DIR, "sheet1.html")
OUT = os.path.join(SCRIPT_DIR, "archive.json")


def pad2(n):
    return str(n).zfill(2)


def parse_korean_date(s):
    if not s or not str(s).strip():
        return None
    m = re.match(r"(\d{2,4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})", str(s).strip())
    if not m:
        return None
    y_raw = m.group(1)
    yy = y_raw[-2:] if len(y_raw) >= 4 else pad2(int(y_raw) % 100)
    mm = pad2(int(m.group(2)))
    dd = pad2(int(m.group(3)))
    return yy + mm + dd


def last_day_yymmdd(yymmdd):
    if not yymmdd or len(yymmdd) != 6:
        return yymmdd
    y = int(yymmdd[:2])
    mo = int(yymmdd[2:4])
    yyyy = 2000 + y
    import calendar

    ld = calendar.monthrange(yyyy, mo)[1]
    return pad2(y) + pad2(mo) + pad2(ld)


class TdCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tbody = False
        self.in_td = False
        self.rows = []
        self.cur = []
        self.td_buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self.in_tbody = True
        elif self.in_tbody and tag == "tr":
            self.cur = []
        elif self.in_tbody and tag == "td":
            self.in_td = True
            self.td_buf = []

    def handle_endtag(self, tag):
        if tag == "tbody":
            self.in_tbody = False
        elif self.in_tbody and tag == "tr":
            if self.cur:
                self.rows.append(self.cur)
        elif tag == "td" and self.in_td:
            self.in_td = False
            self.cur.append("".join(self.td_buf).strip())

    def handle_data(self, data):
        if self.in_td:
            self.td_buf.append(data)


def cell(row, i):
    return row[i] if i < len(row) else ""


def find_hashtag_col(rows):
    if len(rows) < 2:
        return -1
    header = rows[1]
    for i, text in enumerate(header):
        t = str(text).strip()
        if re.search(r"해시\s*태그|해쉬\s*태그", t):
            return i
    return -1


def find_daily_keyword_col(rows):
    """매일 구간(열 0~7) 헤더에서 정확히 '키워드'인 열."""
    if len(rows) < 2:
        return -1
    header = rows[1]
    for i, text in enumerate(header):
        if i > 7:
            break
        if re.match(r"^키워드\s*$", str(text).strip()):
            return i
    return -1


def find_nth_header_col(rows, pattern, nth):
    if len(rows) < 2:
        return -1
    header = rows[1]
    hit = 0
    for i, text in enumerate(header):
        t = str(text).strip()
        if not re.match(pattern, t):
            continue
        if hit == nth:
            return i
        hit += 1
    return -1


def detect_columns(rows):
    daily_title = find_nth_header_col(rows, r"^제목$", 0)
    weekly_title = find_nth_header_col(rows, r"^제목$", 1)
    monthly_title = find_nth_header_col(rows, r"^제목$", 2)
    weekly_platform = find_nth_header_col(rows, r"^플랫폼$", 1)
    monthly_platform = find_nth_header_col(rows, r"^플랫폼$", 2)
    weekly_keyword = find_nth_header_col(rows, r"^키워드\s*$", 1)
    monthly_keyword = find_nth_header_col(rows, r"^키워드\s*$", 2)
    weekly_date = find_nth_header_col(rows, r"^날짜$", 1)
    monthly_date = find_nth_header_col(rows, r"^날짜$", 2)
    if monthly_date < 0 and monthly_title >= 0:
        monthly_date = monthly_title - 3
    return {
        "daily_date": 0,
        "daily_title": daily_title if daily_title >= 0 else 2,
        "daily_platform": 3,
        "daily_genre": 4,
        "daily_keyword": find_daily_keyword_col(rows),
        "weekly_date": weekly_date if weekly_date >= 0 else 8,
        "weekly_title": weekly_title if weekly_title >= 0 else 11,
        "weekly_platform": weekly_platform if weekly_platform >= 0 else 12,
        "weekly_keyword": weekly_keyword if weekly_keyword >= 0 else 13,
        "weekly_extra_keyword": (weekly_keyword + 1) if weekly_keyword >= 0 else 14,
        "monthly_date": monthly_date if monthly_date >= 0 else 16,
        "monthly_title": monthly_title if monthly_title >= 0 else 19,
        "monthly_platform": monthly_platform if monthly_platform >= 0 else 20,
        "monthly_keyword": monthly_keyword if monthly_keyword >= 0 else 21,
        "monthly_extra_keyword": (monthly_keyword + 1) if monthly_keyword >= 0 else 22,
    }


def join_kw_parts(*parts):
    chunks = []
    for p in parts:
        if p is None:
            continue
        s = str(p).strip()
        if s:
            chunks.append(s)
    return " · ".join(chunks)


SHEET_PLACEHOLDER_DAILY_TITLES = frozenset({"위클리", "먼슬리"})


def build_items(rows):
    tag_col = find_hashtag_col(rows)
    cols = detect_columns(rows)
    items = []
    last_weekly_yymmdd = None
    last_weekly_platform = ""
    last_weekly_keywords = ""
    last_monthly_date_str = None
    last_m_platform = ""
    last_m_keywords = ""
    for ri in range(3, len(rows)):
        r = rows[ri]
        if len(r) < 12:
            continue
        tags = cell(r, tag_col) if tag_col >= 0 else ""
        d_date = parse_korean_date(cell(r, cols["daily_date"]))
        d_title = cell(r, cols["daily_title"])
        if d_date and d_title and str(d_title).strip() not in SHEET_PLACEHOLDER_DAILY_TITLES:
            if cols["daily_keyword"] >= 0:
                base_kw = cell(r, cols["daily_keyword"])
            else:
                base_kw = " ".join(x for x in (cell(r, 5), cell(r, 6)) if x)
            kw = join_kw_parts(base_kw, tags)
            items.append(
                {
                    "date": d_date,
                    "type": "daily",
                    "title": d_title,
                    "platform": cell(r, cols["daily_platform"]),
                    "genre": cell(r, cols["daily_genre"]),
                    "keywords": kw,
                    "hashtags": "",
                }
            )
        w_date_cell = parse_korean_date(cell(r, cols["weekly_date"]))
        if w_date_cell:
            last_weekly_yymmdd = w_date_cell
        w_pl_raw = cell(r, cols["weekly_platform"])
        if w_pl_raw:
            last_weekly_platform = w_pl_raw
        w_kw_raw = cell(r, cols["weekly_keyword"])
        if w_kw_raw:
            last_weekly_keywords = w_kw_raw
        w_title = cell(r, cols["weekly_title"])
        if w_title and last_weekly_yymmdd:
            base_kw = " ".join(
                x
                for x in (
                    (w_kw_raw or last_weekly_keywords),
                    cell(r, cols["weekly_extra_keyword"]),
                )
                if x
            )
            kw = join_kw_parts(base_kw, tags)
            items.append(
                {
                    "date": last_weekly_yymmdd,
                    "type": "weekly",
                    "title": w_title,
                    "platform": w_pl_raw or last_weekly_platform,
                    "genre": "",
                    "keywords": kw,
                    "hashtags": "",
                }
            )
        m_date_header = parse_korean_date(cell(r, cols["monthly_date"]))
        if m_date_header:
            last_monthly_date_str = last_day_yymmdd(m_date_header)
            last_m_platform = ""
            last_m_keywords = ""
        m_pl_raw = cell(r, cols["monthly_platform"])
        if m_pl_raw:
            last_m_platform = m_pl_raw
        m_kw_raw = cell(r, cols["monthly_keyword"])
        if m_kw_raw:
            last_m_keywords = m_kw_raw
        m_title = cell(r, cols["monthly_title"])
        if m_title:
            m_date_str = last_monthly_date_str
            if not m_date_str and d_date:
                m_date_str = last_day_yymmdd(d_date)
            if m_date_str:
                base_kw = " ".join(
                    x
                    for x in (
                        (m_kw_raw or last_m_keywords),
                        cell(r, cols["monthly_extra_keyword"]),
                    )
                    if x
                )
                kw = join_kw_parts(base_kw, tags)
                items.append(
                    {
                        "date": m_date_str,
                        "type": "monthly",
                        "title": m_title,
                        "platform": m_pl_raw or last_m_platform,
                        "genre": "",
                        "keywords": kw,
                        "hashtags": "",
                    }
                )

    order = {"daily": 0, "weekly": 1, "monthly": 2}

    def sort_key(it):
        return (-int(it["date"]), order.get(it["type"], 9))

    items.sort(key=sort_key)
    return items


def main():
    if not os.path.isfile(SHEET):
        print("sheet1.html 없음:", SHEET)
        return 1
    with open(SHEET, encoding="utf-8") as f:
        html = f.read()
    col = TdCollector()
    col.feed(html)
    items = build_items(col.rows)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"items": items}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("archive.json:", len(items), "개 항목")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
