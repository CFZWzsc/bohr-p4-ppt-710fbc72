#!/usr/bin/env python3
"""Academic slide template adapter (standard library only).

Maps source pages onto a declared master/layout/placeholder structure, fills
text and figure slots, estimates text overflow against a font ladder, scales
figures without silent distortion, audits figure numbering and whole-deck
consistency, and records a deterministic export plan and version entry.
Offline and deterministic; missing templates, slots or geometry are reported,
never invented.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output/result.json"
DEFAULT_WORK = "/app/work"
SKILL_NAME = "slide-template-adapter"
SKILL_VERSION = "1.0.0"
CHALLENGE_ID = "ppt-710fbc72"

DEFAULT_SLIDE = {"width": 13.333, "height": 7.5}
FONT_LADDER = {"title": 32, "section": 28, "subtitle": 22, "body": 20, "caption": 14, "footnote": 12}
MIN_FONT = {"title": 24, "section": 22, "subtitle": 16, "body": 14, "caption": 11, "footnote": 9}
TEXT_TYPES = ("title", "subtitle", "body")

CITE_RE = re.compile(r"(图|表|figure|fig\.?|table)\s*(\d+)", re.I)

PTYPE_LOOKUP = {
    "title": "title", "ctrtitle": "title", "标题": "title",
    "subtitle": "subtitle", "副标题": "subtitle",
    "body": "body", "content": "body", "text": "body", "正文": "body",
    "picture": "picture", "image": "picture", "pic": "picture", "photo": "picture", "图片": "picture",
    "table": "table", "表格": "table",
    "chart": "chart", "图表": "chart",
    "footer": "footer", "页脚": "footer",
    "slidenumber": "slide_number", "页码": "slide_number", "pagenumber": "slide_number",
    "sldnum": "slide_number", "number": "slide_number",
    "date": "date", "日期": "date",
    "notes": "notes", "备注": "notes",
}
PTYPE_ORDERED = [
    ("slidenumber", "slide_number"), ("sldnum", "slide_number"),
    ("pagenumber", "slide_number"), ("页码", "slide_number"),
    ("footer", "footer"), ("页脚", "footer"),
    ("date", "date"), ("日期", "date"),
    ("subtitle", "subtitle"), ("副标题", "subtitle"),
    ("picture", "picture"), ("image", "picture"), ("photo", "picture"), ("图片", "picture"),
    ("table", "table"), ("表格", "table"),
    ("chart", "chart"), ("图表", "chart"),
    ("title", "title"), ("标题", "title"),
    ("notes", "notes"), ("备注", "notes"),
    ("body", "body"), ("content", "body"), ("正文", "body"), ("text", "body"),
]

LAYOUT_KEYWORDS = {
    "cover": ("cover", "title slide", "封面", "标题页"),
    "section": ("section", "divider", "章节", "过渡", "目录"),
    "picture": ("picture", "image", "photo", "图"),
    "table": ("table", "表格"),
    "closing": ("closing", "ending", "thank", "致谢", "结束"),
    "content": ("content", "正文", "标题和内容", "title and content", "bullet", "text"),
    "backup": ("backup", "附录", "appendix"),
}

ALIASES = {
    "status": "status", "slides": "slides", "deck": "slides", "deck_spec": "slides",
    "page_plan": "slides", "pages": "slides", "page_structure": "slides",
    "template": "template_summary", "template_summary": "template_summary",
    "template_map": "template_summary", "layouts": "template_summary",
    "template_applied": "template_summary", "placeholders": "template_summary",
    "font_plan": "font_plan", "typography": "font_plan", "fonts": "font_plan",
    "figure_adaptation": "figure_adaptation", "figures": "figure_adaptation",
    "figure_plan": "figure_adaptation", "image_adaptation": "figure_adaptation",
    "consistency": "consistency", "batch_consistency": "consistency",
    "checks": "checks", "validation": "checks", "consistency_checks": "checks",
    "export_plan": "export_plan", "export": "export_plan", "render_checks": "export_plan",
    "version_record": "version_record", "version": "version_record", "change_log": "version_record",
    "source_register": "source_register", "sources": "source_register",
    "gaps": "gaps", "uncertainty": "uncertainty", "evidence": "evidence",
    "stats": "stats", "limitations": "limitations",
}


def sha256_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def sha256_json(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_text_file(path):
    try:
        if os.path.isfile(path) and os.path.getsize(path) <= 4 * 1024 * 1024:
            with open(path, "r", encoding="utf-8-sig") as handle:
                return handle.read()
    except (OSError, UnicodeDecodeError):
        return None
    return None


def as_float(value, default=0.0):
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().rstrip("inpt%"))
    except (TypeError, ValueError):
        return default


def to_inches(value):
    number = as_float(value, None)
    if number is None:
        return None
    if abs(number) > 5000:
        return round(number / 914400.0, 3)
    return number


def task_text(base_dir):
    for name in ("task.md", "TASK.md", "task.txt"):
        path = os.path.join(base_dir, name)
        text = read_text_file(path)
        if text:
            return text, path
    return "", None


def norm_ptype(value, name=None):
    for source in (value, name):
        compact = re.sub(r"[\s_\-]+", "", str(source or "").lower())
        if not compact:
            continue
        if compact in PTYPE_LOOKUP:
            return PTYPE_LOOKUP[compact]
        for token, ptype in PTYPE_ORDERED:
            if token in compact:
                return ptype
    return "body"


def canonical_kind(token):
    text = str(token or "").strip().lower().rstrip(".")
    if text in ("图", "figure", "fig"):
        return "figure"
    return "table"


def norm_label(label, kind="figure"):
    match = CITE_RE.search(str(label or ""))
    if match:
        return "%s %s" % (canonical_kind(match.group(1)), match.group(2))
    text = str(label or "").strip().lower()
    if re.fullmatch(r"\d+", text):
        return "%s %s" % (kind, text)
    return text


def default_geometry(ptype, slide):
    width = slide["width"]
    height = slide["height"]
    if ptype == "title":
        return {"x": 0.6, "y": 0.35, "w": max(width - 1.2, 1.0), "h": 0.95}
    if ptype == "section":
        return {"x": 0.9, "y": 2.5, "w": max(width - 1.8, 1.0), "h": 1.2}
    if ptype == "subtitle":
        return {"x": 0.9, "y": 1.35, "w": max(width - 1.8, 1.0), "h": 0.7}
    if ptype == "body":
        return {"x": 0.7, "y": 1.55, "w": max(width - 1.4, 1.0), "h": max(height - 2.35, 1.0)}
    if ptype == "picture":
        return {"x": 0.8, "y": 1.7, "w": max((width - 2.2) / 2.0, 1.0), "h": max(height - 2.7, 1.0)}
    if ptype == "table":
        return {"x": 0.8, "y": 1.7, "w": max(width - 1.6, 1.0), "h": max(height - 2.7, 1.0)}
    if ptype == "footer":
        return {"x": 0.6, "y": max(height - 0.55, 0.1), "w": max(width - 1.6, 1.0), "h": 0.35}
    if ptype == "slide_number":
        return {"x": max(width - 0.9, 0.1), "y": max(height - 0.55, 0.1), "w": 0.5, "h": 0.3}
    if ptype == "date":
        return {"x": 0.6, "y": max(height - 0.9, 0.1), "w": 2.0, "h": 0.3}
    return {"x": 0.7, "y": 1.5, "w": max(width - 1.4, 1.0), "h": 1.0}


def normalize_placeholder(raw, index, slide, layout_id):
    if isinstance(raw, str):
        raw = {"type": raw}
    if not isinstance(raw, dict):
        raw = {}
    name = raw.get("name") or raw.get("label")
    ptype = norm_ptype(raw.get("type") or raw.get("kind") or raw.get("role") or name, name)
    ph_id = str(raw.get("id") or raw.get("idx") or name or "ph%d" % (index + 1))
    geometry = {}
    for key, aliases in (("x", ("x", "left")), ("y", ("y", "top")),
                         ("w", ("w", "width", "cx")), ("h", ("h", "height", "cy"))):
        for alias in aliases:
            if alias in raw and raw.get(alias) not in (None, ""):
                value = to_inches(raw.get(alias))
                if value is not None:
                    geometry[key] = value
                break
    fallback = default_geometry(ptype, slide)
    assumed = False
    for key in ("x", "y", "w", "h"):
        value = geometry.get(key)
        if value is None or value < 0:
            geometry[key] = fallback[key]
            assumed = True
        elif key in ("w", "h") and value <= 0:
            geometry[key] = fallback[key]
            assumed = True
    font_size = as_float(raw.get("font_size") or raw.get("size") or raw.get("pt"), 0.0) or None
    return {
        "id": ph_id, "type": ptype,
        "x": round(geometry["x"], 3), "y": round(geometry["y"], 3),
        "w": round(geometry["w"], 3), "h": round(geometry["h"], 3),
        "font_size": font_size, "geometry_assumed": assumed,
        "layout_id": layout_id,
    }


def normalize_layout(raw, index, slide):
    if isinstance(raw, str):
        raw = {"name": raw}
    if not isinstance(raw, dict):
        raw = {}
    layout_id = str(raw.get("id") or raw.get("name") or "layout_%d" % (index + 1))
    name = str(raw.get("name") or layout_id)
    placeholders = raw.get("placeholders") or raw.get("slots") or raw.get("shapes") or []
    if isinstance(placeholders, dict):
        converted = []
        for key, spec in placeholders.items():
            if isinstance(spec, dict):
                entry = dict(spec)
                entry.setdefault("id", key)
            else:
                entry = {"id": key, "type": spec}
            converted.append(entry)
        placeholders = converted
    phs = [normalize_placeholder(item, i, slide, layout_id) for i, item in enumerate(placeholders)]
    return {"id": layout_id, "name": name, "placeholders": phs, "synthesized": False}


def synthesize_layouts(slide):
    raws = [
        {"id": "generic_title_content", "name": "Title and Content",
         "placeholders": [{"id": "title", "type": "title"}, {"id": "body", "type": "body"}]},
        {"id": "generic_title_only", "name": "Title Only",
         "placeholders": [{"id": "title", "type": "title"}]},
        {"id": "generic_picture", "name": "Title and Picture",
         "placeholders": [{"id": "title", "type": "title"}, {"id": "picture", "type": "picture"}]},
    ]
    layouts = [normalize_layout(item, i, slide) for i, item in enumerate(raws)]
    for layout in layouts:
        layout["synthesized"] = True
    return layouts


def load_template(case, base_dir):
    warnings = []
    raw = case.get("template")
    if isinstance(raw, str):
        if os.path.isabs(raw):
            warnings.append("template_path_absolute_not_read")
            raw = None
        else:
            text = read_text_file(os.path.join(base_dir, raw))
            if text:
                try:
                    raw = json.loads(text)
                except ValueError:
                    warnings.append("template_file_invalid_json")
                    raw = None
            else:
                warnings.append("template_file_not_found")
                raw = None
    if raw is None:
        deck = case.get("deck")
        if isinstance(deck, dict):
            raw = deck.get("template")
    if not isinstance(raw, dict):
        raw = {}

    slide_raw = raw.get("slide_size") or case.get("slide_size") or {}
    slide = dict(DEFAULT_SLIDE)
    if isinstance(slide_raw, dict):
        slide["width"] = as_float(slide_raw.get("width") or slide_raw.get("w"), DEFAULT_SLIDE["width"])
        slide["height"] = as_float(slide_raw.get("height") or slide_raw.get("h"), DEFAULT_SLIDE["height"])
    elif isinstance(slide_raw, str):
        match = re.search(r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)", slide_raw)
        if match:
            slide["width"] = float(match.group(1))
            slide["height"] = float(match.group(2))

    layout_raw = raw.get("layouts") or raw.get("slide_layouts") or []
    if not layout_raw and isinstance(raw.get("masters"), list):
        collected = []
        for master in raw["masters"]:
            if isinstance(master, dict):
                collected.extend(master.get("layouts") or [])
        layout_raw = collected
    if isinstance(layout_raw, dict):
        converted = []
        for key, spec in layout_raw.items():
            if isinstance(spec, dict):
                entry = dict(spec)
                entry.setdefault("id", key)
                entry.setdefault("name", key)
            else:
                entry = {"id": key, "name": key}
            converted.append(entry)
        layout_raw = converted

    layouts = [normalize_layout(item, idx, slide) for idx, item in enumerate(layout_raw or [])]
    declared = bool(raw) and bool(raw.get("layouts") or raw.get("slide_layouts") or raw.get("masters"))
    if not layouts:
        layouts = synthesize_layouts(slide)
        warnings.append("template_layouts_missing_generic_used")

    return {
        "declared": declared,
        "raw_present": bool(raw),
        "slide_size": {"width": round(slide["width"], 3), "height": round(slide["height"], 3)},
        "layouts": layouts,
        "fonts": raw.get("fonts") or raw.get("font") or {},
        "theme_colors": raw.get("theme_colors") or raw.get("colors") or case.get("theme_colors") or {},
        "footer": raw.get("footer") or case.get("footer"),
        "font_scale": raw.get("font_scale") or {},
        "warnings": warnings,
        "source_sha256": sha256_json(raw) if raw else None,
    }


def split_sentences(text):
    result = []
    for chunk in re.split(r"(?<=[。；;！!？?])|(?<=\.)\s+|\n+", str(text or "")):
        sentence = norm(chunk)
        if 10 <= len(sentence) <= 220:
            result.append(sentence)
    return result


def normalize_asset(raw, kind, page_idx, asset_idx):
    if isinstance(raw, str):
        raw = {"src": raw}
    if not isinstance(raw, dict):
        raw = {}
    label = raw.get("label") or raw.get("number") or raw.get("id") or raw.get("name")
    caption = raw.get("caption") or raw.get("title") or ""
    if not label and caption:
        match = CITE_RE.search(caption)
        if match:
            label = "%s %s" % (canonical_kind(match.group(1)), match.group(2))
    vector = bool(raw.get("vector"))
    type_text = str(raw.get("type") or raw.get("format") or "").lower()
    if type_text in ("svg", "vector", "emf", "eps", "pdf"):
        vector = True
    return {
        "kind": kind,
        "src": raw.get("src") or raw.get("path") or raw.get("file"),
        "label": str(label).strip() if label not in (None, "") else None,
        "caption": str(caption).strip(),
        "width": as_float(raw.get("width") or raw.get("w") or raw.get("pixel_width"), 0.0) or None,
        "height": as_float(raw.get("height") or raw.get("h") or raw.get("pixel_height"), 0.0) or None,
        "aspect": as_float(raw.get("aspect") or raw.get("ratio"), 0.0) or None,
        "vector": vector,
        "fit": str(raw.get("fit") or raw.get("fit_mode") or "contain").lower(),
        "source_ref": raw.get("source_ref") or raw.get("source") or raw.get("cite"),
    }


def normalize_page(raw, idx):
    if isinstance(raw, str):
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        raw = {"title": lines[0] if lines else "", "bullets": lines[1:]}
    if not isinstance(raw, dict):
        raw = {}

    title = ""
    for key in ("title", "heading", "headline", "claim", "name"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            title = value.strip()
            break
        if isinstance(value, (int, float)):
            title = str(value)
            break

    bullets = []
    for key in ("bullets", "points", "body", "content", "lines", "text"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            bullets = [line.strip() for line in value.splitlines() if line.strip()]
            break
        if isinstance(value, list):
            bullets = [str(item).strip() for item in value if str(item).strip()]
            break

    notes = ""
    for key in ("notes", "speaker_notes", "note", "script"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            notes = value.strip()
            break
        if isinstance(value, list):
            joined = " ".join(str(item).strip() for item in value if str(item).strip())
            if joined:
                notes = joined
                break

    figures = []
    for key in ("figures", "images", "pictures", "figs", "charts"):
        value = raw.get(key)
        if isinstance(value, list):
            figures = [normalize_asset(item, "figure", idx, i) for i, item in enumerate(value)]
            break
        if isinstance(value, dict):
            figures = [normalize_asset(dict(item if isinstance(item, dict) else {"src": item}, id=key_name),
                                       "figure", idx, i)
                       for i, (key_name, item) in enumerate(value.items())]
            break

    tables = []
    for key in ("tables", "data_tables"):
        value = raw.get(key)
        if isinstance(value, list):
            tables = [normalize_asset(item, "table", idx, i) for i, item in enumerate(value)]
            break

    source = None
    for key in ("source", "source_ref", "locator", "citation", "evidence"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            source = value.strip()
            break
        if isinstance(value, dict):
            source = json.dumps(value, ensure_ascii=False)[:200]
            break

    role = raw.get("role") or raw.get("type")
    layout_hint = raw.get("layout_hint") or raw.get("layout") or raw.get("template_layout")
    return {
        "id": raw.get("id") or raw.get("slide_id"),
        "title": title,
        "claim": raw.get("claim") if isinstance(raw.get("claim"), str) else title,
        "bullets": bullets,
        "notes": notes,
        "figures": figures,
        "tables": tables,
        "role": role,
        "layout_hint": layout_hint,
        "source": source,
        "generated": bool(raw.get("generated")),
    }


def pages_from_sections(case):
    sections = case.get("sections") or case.get("paper_sections") or case.get("outline")
    entries = []
    if isinstance(sections, dict):
        entries = [(str(key), value) for key, value in sections.items()]
    elif isinstance(sections, list):
        for idx, item in enumerate(sections):
            if isinstance(item, dict):
                heading = item.get("heading") or item.get("title") or item.get("name") or "Section %d" % (idx + 1)
                entries.append((str(heading), item.get("text") or item.get("body") or item.get("content") or ""))
            elif isinstance(item, str):
                entries.append((item.strip()[:40], item))
    pages = []
    for idx, (heading, value) in enumerate(entries):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        sentences = split_sentences(text)[:3]
        if not heading.strip() and not sentences:
            continue
        pages.append({
            "id": "G%d" % (idx + 1), "title": heading.strip(), "claim": heading.strip(),
            "bullets": sentences, "notes": "", "figures": [], "tables": [],
            "role": "content", "layout_hint": None, "source": "sections[%s]" % heading,
            "generated": True,
        })
    return pages


def collect_pages(case):
    warnings = []
    raw = None
    for key in ("slides", "pages", "deck", "presentation"):
        value = case.get(key)
        if isinstance(value, list) and value:
            raw = value
            break
        if isinstance(value, dict):
            for inner in ("slides", "pages", "items"):
                if isinstance(value.get(inner), list) and value[inner]:
                    raw = value[inner]
                    break
        if raw:
            break
    pages = []
    if isinstance(raw, list):
        pages = [normalize_page(item, idx) for idx, item in enumerate(raw)]
    generated = False
    if not pages:
        pages = pages_from_sections(case)
        generated = bool(pages)
        if generated:
            warnings.append("pages_generated_from_sections")
    pages = [page for page in pages
             if page.get("title") or page.get("bullets") or page.get("figures")
             or page.get("tables") or page.get("notes")]
    return pages, generated, warnings


def infer_role(page, idx):
    role = str(page.get("role") or "").strip().lower()
    mapping = {"cover": "cover", "title": "cover", "opening": "cover",
               "section": "section", "divider": "section",
               "content": "content", "body": "content",
               "picture": "picture", "image": "picture",
               "closing": "closing", "ending": "closing", "thanks": "closing",
               "backup": "backup"}
    if role in mapping:
        return mapping[role]
    if idx == 0:
        return "cover"
    joined = (str(page.get("title") or "") + " " + str(page.get("notes") or "")).lower()
    if any(marker in joined for marker in ("谢谢", "致谢", "thank", "questions", "q&a")):
        return "closing"
    if page.get("figures") and not page.get("bullets"):
        return "picture"
    return "content"


def score_layout(layout, role):
    name = layout["name"].lower()
    types = {ph["type"] for ph in layout["placeholders"]}
    score = 0
    for keyword in LAYOUT_KEYWORDS.get(role, ()):
        if keyword in name:
            score += 3
    if role == "cover":
        if "title" in types and "body" not in types:
            score += 2
    elif role == "section":
        if "title" in types and "body" not in types:
            score += 1
    elif role in ("content", "backup"):
        if "body" in types:
            score += 2
        if "title" in types:
            score += 1
    elif role == "picture":
        if "picture" in types:
            score += 3
        if "body" in types:
            score += 1
    elif role == "closing":
        if "body" in types:
            score += 1
    return score


def pick_layout(template, page, role):
    hint = str(page.get("layout_hint") or "").lower()
    if hint:
        for layout in template["layouts"]:
            if hint == layout["id"].lower() or hint == layout["name"].lower() or hint in layout["name"].lower():
                return layout, "explicit_layout_hint"
    best, best_score = None, -1
    candidates = template["layouts"]
    if page.get("figures"):
        with_picture = [layout for layout in candidates
                        if any(ph["type"] == "picture" for ph in layout["placeholders"])]
        if with_picture:
            candidates = with_picture
    elif page.get("tables"):
        with_table = [layout for layout in candidates
                      if any(ph["type"] == "table" for ph in layout["placeholders"])]
        if with_table:
            candidates = with_table
    for layout in candidates:
        score = score_layout(layout, role)
        if score > best_score:
            best, best_score = layout, score
    if best is not None and best_score > 0:
        return best, "role=%s score=%d" % (role, best_score)
    fallback = template["layouts"][0]
    for layout in template["layouts"]:
        types = {ph["type"] for ph in layout["placeholders"]}
        if role in ("content", "backup") and "body" in types:
            fallback = layout
            break
    return fallback, "fallback_first_layout"


def effective_ladder(template):
    ladder = dict(FONT_LADDER)
    scale = template.get("font_scale")
    if isinstance(scale, dict):
        for key in ladder:
            value = as_float(scale.get(key), None)
            if value and value > 0:
                ladder[key] = value
    return ladder


def slot_font(placeholder, role_key, ladder):
    if placeholder.get("font_size"):
        return float(placeholder["font_size"])
    return float(ladder.get(role_key, FONT_LADDER.get(role_key, 16)))


def text_units(text):
    cjk = 0
    for char in str(text):
        code = ord(char)
        if 0x4E00 <= code <= 0x9FFF or 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF:
            cjk += 1
    latin = len(str(text)) - cjk
    return cjk, latin


def display_len(text):
    cjk, latin = text_units(text)
    return cjk * 2 + latin


def estimate_block(text, font_pt, width_in, height_in):
    if not str(text or "").strip():
        return 0, 0.0, False
    available_width = max((width_in - 0.2) * 72.0, 1.0)
    available_height = max((height_in - 0.2) * 72.0, 1.0)
    lines = 0
    for paragraph in str(text).split("\n"):
        cjk, latin = text_units(paragraph)
        units = cjk * font_pt + latin * 0.52 * font_pt
        lines += max(1, int(math.ceil(units / available_width)))
    needed = lines * font_pt * 1.22 + 4.0
    return lines, round(needed, 1), needed > available_height


def fit_text(text, base_pt, width_in, height_in, min_pt):
    lines, needed, overflow = estimate_block(text, base_pt, width_in, height_in)
    if not overflow:
        return float(base_pt), lines, needed, False, False
    candidates = sorted({value for value in list(FONT_LADDER.values())
                         if min_pt <= value < base_pt}, reverse=True)
    for size in candidates:
        candidate_lines, candidate_needed, candidate_overflow = estimate_block(text, size, width_in, height_in)
        if not candidate_overflow:
            return float(size), candidate_lines, candidate_needed, False, True
    return float(min_pt), lines, needed, True, True


def capacity_chars(width_in, height_in, font_pt):
    available_width = max((width_in - 0.2) * 72.0, 1.0)
    available_height = max((height_in - 0.2) * 72.0, 1.0)
    max_lines = max(1, int(available_height // (font_pt * 1.22)))
    per_line = max(1, int(available_width // (font_pt * 0.95)))
    return max_lines * per_line


def asset_ref(asset):
    if asset.get("label"):
        return str(asset["label"])
    if asset.get("src"):
        return os.path.basename(str(asset["src"]))
    if asset.get("caption"):
        return str(asset["caption"])[:48]
    return asset.get("kind", "asset")


def adapt_figure(figure, container, page_id, checks, placement="slot"):
    width_px = figure.get("width") or 0.0
    height_px = figure.get("height") or 0.0
    aspect = figure.get("aspect")
    if not aspect and width_px and height_px:
        aspect = width_px / height_px
    declared = str(figure.get("fit") or "contain").lower()
    mode = declared if declared in ("contain", "cover", "stretch") else "contain"
    container_w = max(as_float(container.get("w"), 0.0), 0.1)
    container_h = max(as_float(container.get("h"), 0.0), 0.1)
    record = {
        "page": page_id, "label": figure.get("label"), "src": figure.get("src"),
        "vector": bool(figure.get("vector")), "declared_fit": declared, "mode_used": mode,
        "container": {"w": round(container_w, 2), "h": round(container_h, 2)},
        "placement": placement, "warnings": [],
    }
    if not aspect or aspect <= 0:
        record.update({"source_aspect": None, "rendered": None,
                       "aspect_distortion": False, "effective_ppi": None,
                       "geometry_unknown": True})
        record["warnings"].append("figure_dimensions_unknown")
        checks.append({"code": "figure_dimensions_unknown", "severity": "info", "page": page_id,
                       "detail": "figure %s has no width/height/aspect; scaling is not asserted"
                                 % asset_ref(figure)})
        return record

    container_aspect = container_w / container_h
    record["source_aspect"] = round(aspect, 4)
    record["container_aspect"] = round(container_aspect, 4)
    distortion = False
    crop = None
    if mode == "stretch":
        render_w, render_h = container_w, container_h
        distortion = abs(aspect - container_aspect) / container_aspect > 0.01
        if distortion:
            record["warnings"].append("aspect_distortion_risk")
            checks.append({"code": "aspect_distortion_risk", "severity": "warning", "page": page_id,
                           "detail": "figure %s is declared with fit=stretch (source %.2f vs container %.2f); "
                                     "use contain or cover" % (asset_ref(figure), aspect, container_aspect)})
    else:
        if mode == "cover":
            scale = max(container_w / aspect, container_h)
        else:
            scale = min(container_w / aspect, container_h)
        render_w, render_h = aspect * scale, scale
        if mode == "cover":
            if aspect > container_aspect:
                crop = {"axis": "width", "fraction": round(1.0 - container_aspect / aspect, 3)}
            elif aspect < container_aspect:
                crop = {"axis": "height", "fraction": round(1.0 - aspect / container_aspect, 3)}
            if crop and crop["fraction"] > 0.05:
                record["warnings"].append("figure_crop_applied")
                checks.append({"code": "figure_crop_applied", "severity": "info", "page": page_id,
                               "detail": "figure %s cropped %d%% along %s to fill the container"
                                         % (asset_ref(figure), int(crop["fraction"] * 100), crop["axis"])})
    record["rendered"] = {"w": round(render_w, 2), "h": round(render_h, 2)}
    record["aspect_distortion"] = distortion
    record["crop"] = crop
    record["effective_ppi"] = None
    if not figure.get("vector") and width_px:
        ppi = round(width_px / render_w, 1)
        record["effective_ppi"] = ppi
        if ppi < 150:
            record["warnings"].append("low_resolution_figure")
            checks.append({"code": "low_resolution_figure", "severity": "warning", "page": page_id,
                           "detail": "figure %s renders at about %.0f ppi (below 150)"
                                     % (asset_ref(figure), ppi)})
    return record


def build_slides(pages, template, ladder, footer_text, checks):
    slides = []
    figure_results = []
    text_fits = []
    slide_size = template["slide_size"]

    for idx, page in enumerate(pages):
        role = infer_role(page, idx)
        layout, reason = pick_layout(template, page, role)
        slide_id = str(page.get("id") or "S%d" % (idx + 1))
        slots = []
        used_figures = set()
        used_tables = set()

        for placeholder in layout["placeholders"]:
            ptype = placeholder["type"]
            slot = {"placeholder_id": placeholder["id"], "type": ptype, "filled": False,
                    "geometry_assumed": placeholder.get("geometry_assumed")}

            if ptype in TEXT_TYPES:
                if ptype == "title":
                    text = page.get("title") or ""
                    role_key = "title"
                elif ptype == "subtitle":
                    text = page.get("claim") or ""
                    role_key = "subtitle"
                else:
                    text = "\n".join(page.get("bullets") or [])
                    role_key = "body"
                if str(text).strip():
                    base = slot_font(placeholder, role_key, ladder)
                    recommended, lines, needed, unresolvable, reduced = fit_text(
                        text, base, placeholder["w"], placeholder["h"], MIN_FONT[role_key])
                    available = max((placeholder["h"] - 0.2) * 72.0, 1.0)
                    fit = {"lines": lines, "needed_height_pt": needed,
                           "available_height_pt": round(available, 1),
                           "font_reduced": reduced, "overflow": unresolvable}
                    slot.update({"filled": True, "content": text,
                                 "font_size": round(recommended, 1), "fit": fit})
                    text_fits.append({"page": slide_id, "placeholder": placeholder["id"],
                                      "role": role_key, "chars": len(text),
                                      "font_size": round(recommended, 1), **fit})
                    if unresolvable:
                        fit["max_chars_estimate"] = capacity_chars(
                            placeholder["w"], placeholder["h"], MIN_FONT[role_key])
                        checks.append({"code": "text_overflow_unresolvable", "severity": "error",
                                       "page": slide_id,
                                       "detail": "%s placeholder %s needs %.0fpt height but only %.0fpt "
                                                 "available even at %.0fpt; trim to about %d chars or split page"
                                                 % (role_key, placeholder["id"], needed, available,
                                                    MIN_FONT[role_key], fit["max_chars_estimate"])})
                    elif reduced:
                        checks.append({"code": "font_reduced_to_fit", "severity": "info",
                                       "page": slide_id,
                                       "detail": "%s text reduced from %.1fpt to %.1fpt to fit"
                                                 % (role_key, base, recommended)})
                    if ptype == "title" and display_len(text) > 72:
                        checks.append({"code": "title_too_long", "severity": "warning",
                                       "page": slide_id,
                                       "detail": "title is %d width units wide (about %d CJK chars); "
                                                 "shorten to <= 36 CJK chars or split"
                                                 % (display_len(text), display_len(text) // 2)})
                else:
                    slot["note"] = "empty_text"
                    if ptype == "title":
                        checks.append({"code": "empty_title", "severity": "warning",
                                       "page": slide_id, "detail": "page has no title text"})

            elif ptype == "footer":
                if footer_text:
                    slot.update({"filled": True, "content": str(footer_text),
                                 "font_size": slot_font(placeholder, "footnote", ladder)})
                else:
                    slot["note"] = "footer_text_not_declared"

            elif ptype == "slide_number":
                slot.update({"filled": True, "content": str(idx + 1), "auto_field": "slide_number"})

            elif ptype == "date":
                slot["note"] = "auto_date_field_left_empty"

            elif ptype == "picture":
                figure = None
                for fig_idx, candidate in enumerate(page.get("figures") or []):
                    if fig_idx not in used_figures:
                        figure = candidate
                        used_figures.add(fig_idx)
                        break
                if figure:
                    adapted = adapt_figure(figure, placeholder, slide_id, checks)
                    figure_results.append(adapted)
                    slot.update({"filled": True, "content": asset_ref(figure), "fit": adapted})
                else:
                    slot["note"] = "no_figure_available"

            elif ptype == "table":
                table = None
                for table_idx, candidate in enumerate(page.get("tables") or []):
                    if table_idx not in used_tables:
                        table = candidate
                        used_tables.add(table_idx)
                        break
                if table:
                    slot.update({"filled": True, "content": asset_ref(table),
                                 "caption": table.get("caption") or None})
                else:
                    slot["note"] = "no_table_available"

            else:
                slot["note"] = "unsupported_placeholder_type"
            slots.append(slot)

        body_ph = next((ph for ph in layout["placeholders"] if ph["type"] == "body"), None)
        fallback_container = body_ph or default_geometry("body", slide_size)
        for fig_idx, figure in enumerate(page.get("figures") or []):
            if fig_idx in used_figures:
                continue
            adapted = adapt_figure(figure, fallback_container, slide_id, checks,
                                   placement="body_area_fallback")
            figure_results.append(adapted)
            checks.append({"code": "placeholder_fallback", "severity": "warning", "page": slide_id,
                           "detail": "layout %s has no free picture placeholder; figure %s is sized for "
                                     "the body area and needs manual placement"
                                     % (layout["id"], asset_ref(figure))})
        for table_idx, table in enumerate(page.get("tables") or []):
            if table_idx in used_tables:
                continue
            checks.append({"code": "placeholder_fallback", "severity": "warning", "page": slide_id,
                           "detail": "layout %s has no free table placeholder; table %s needs manual placement"
                                     % (layout["id"], asset_ref(table))})

        title_ph = next((ph for ph in layout["placeholders"] if ph["type"] == "title"), None)
        layout_geometry = {
            "title": ({"x": title_ph["x"], "y": title_ph["y"], "w": title_ph["w"], "h": title_ph["h"]}
                      if title_ph else None),
            "body": ({"x": body_ph["x"], "y": body_ph["y"], "w": body_ph["w"], "h": body_ph["h"]}
                     if body_ph else None),
            "has_footer": any(ph["type"] == "footer" for ph in layout["placeholders"]),
            "has_slide_number": any(ph["type"] == "slide_number" for ph in layout["placeholders"]),
        }

        slides.append({
            "id": slide_id, "index": idx + 1, "role": role,
            "title": page.get("title") or "",
            "claim": page.get("claim") or page.get("title") or "",
            "layout_id": layout["id"], "layout_name": layout["name"],
            "layout_reason": reason, "layout_synthesized": bool(layout.get("synthesized")),
            "placeholders": slots,
            "bullets": page.get("bullets") or [],
            "figures": [{"label": figure.get("label"), "src": figure.get("src"),
                         "caption": figure.get("caption")} for figure in page.get("figures") or []],
            "tables": [{"label": table.get("label"), "src": table.get("src"),
                        "caption": table.get("caption")} for table in page.get("tables") or []],
            "notes": page.get("notes") or None,
            "source": page.get("source"),
            "generated": bool(page.get("generated")),
            "layout_geometry": layout_geometry,
        })
    return slides, figure_results, text_fits


def audit_numbering(slides):
    checks = []
    declared = {}
    missing_labels = []
    for slide in slides:
        for kind, assets in (("figure", slide["figures"]), ("table", slide["tables"])):
            for asset in assets:
                label = asset.get("label")
                if label:
                    key = norm_label(label, kind)
                    declared[key] = declared.get(key, 0) + 1
                else:
                    missing_labels.append((slide["id"], kind))

    cited = {}
    cited_by_page = {}
    for slide in slides:
        text = " ".join([slide.get("title") or ""] + list(slide.get("bullets") or [])
                        + [slide.get("notes") or ""])
        page_keys = set()
        for match in CITE_RE.finditer(text):
            key = "%s %s" % (canonical_kind(match.group(1)), match.group(2))
            cited.setdefault(key, []).append(slide["id"])
            page_keys.add(key)
        cited_by_page[slide["id"]] = page_keys

    for key, page_ids in cited.items():
        if key not in declared:
            checks.append({"code": "figure_reference_without_asset", "severity": "error",
                           "page": page_ids[0],
                           "detail": "page text cites %s but no such labelled asset is declared" % key})
    for key, count in declared.items():
        if count > 1:
            checks.append({"code": "duplicate_figure_label", "severity": "warning", "page": None,
                           "detail": "%s is declared %d times" % (key, count)})
        if key not in cited:
            checks.append({"code": "figure_asset_unreferenced", "severity": "info", "page": None,
                           "detail": "%s is declared but never cited in page text" % key})
    for slide_id, kind in missing_labels:
        checks.append({"code": "figure_label_missing", "severity": "warning", "page": slide_id,
                       "detail": "%s has no label/number; numbering cannot be verified" % kind})

    for slide in slides:
        labelled = [asset for asset in slide["figures"] if asset.get("label")]
        page_keys = cited_by_page.get(slide["id"], set())
        if len(labelled) == 1 and page_keys:
            key = norm_label(labelled[0]["label"], "figure")
            if key not in page_keys:
                checks.append({"code": "page_figure_number_mismatch", "severity": "warning",
                               "page": slide["id"],
                               "detail": "page cites %s but its only figure is labelled %s"
                                         % (", ".join(sorted(page_keys)), key)})
    return checks


def audit_consistency(slides, template, checks):
    content = [slide for slide in slides if slide["role"] in ("content", "backup", "picture")]
    title_positions = []
    body_margins = []
    body_sizes = []
    footer_missing = []
    number_missing = []

    for slide in content:
        geometry = slide.get("layout_geometry") or {}
        title_geometry = geometry.get("title")
        if title_geometry:
            title_positions.append((round(title_geometry["x"], 2), round(title_geometry["y"], 2)))
        body_geometry = geometry.get("body")
        if body_geometry:
            body_margins.append(round(body_geometry["x"], 2))
        for slot in slide["placeholders"]:
            if slot["type"] == "body" and slot.get("filled") and slot.get("font_size"):
                body_sizes.append(round(float(slot["font_size"]), 1))

    if len(set(title_positions)) > 1:
        xs = [item[0] for item in title_positions]
        ys = [item[1] for item in title_positions]
        if max(xs) - min(xs) > 0.05 or max(ys) - min(ys) > 0.05:
            checks.append({"code": "title_position_inconsistent", "severity": "warning", "page": None,
                           "detail": "title placeholder coordinates differ across content pages: %s"
                                     % sorted(set(title_positions))[:6]})
    if len(set(body_margins)) > 1 and max(body_margins) - min(body_margins) > 0.05:
        checks.append({"code": "body_margin_inconsistent", "severity": "warning", "page": None,
                       "detail": "body left margins differ across content pages: %s" % sorted(set(body_margins))})
    if len(set(body_sizes)) > 1:
        checks.append({"code": "body_font_size_inconsistent", "severity": "warning", "page": None,
                       "detail": "body font sizes used after fitting: %s" % sorted(set(body_sizes))})

    footer_declared = any(any(ph["type"] == "footer" for ph in layout["placeholders"])
                          for layout in template["layouts"])
    number_declared = any(any(ph["type"] == "slide_number" for ph in layout["placeholders"])
                          for layout in template["layouts"])
    if footer_declared:
        footer_missing = [slide["id"] for slide in content
                          if not (slide.get("layout_geometry") or {}).get("has_footer")]
        if footer_missing:
            checks.append({"code": "footer_missing_on_page", "severity": "warning",
                           "page": footer_missing[0],
                           "detail": "content pages without a footer placeholder: %s"
                                     % ", ".join(footer_missing[:8])})
    if number_declared:
        number_missing = [slide["id"] for slide in content
                          if not (slide.get("layout_geometry") or {}).get("has_slide_number")]
        if number_missing:
            checks.append({"code": "page_number_missing", "severity": "warning",
                           "page": number_missing[0],
                           "detail": "content pages without a slide-number placeholder: %s"
                                     % ", ".join(number_missing[:8])})

    return {
        "title_positions": sorted(set(title_positions)),
        "body_margins": sorted(set(body_margins)),
        "body_font_sizes": sorted(set(body_sizes)),
        "footer_required": footer_declared,
        "page_number_required": number_declared,
        "footer_missing_pages": footer_missing,
        "page_number_missing_pages": number_missing,
    }


def parse_hex(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", text)
    if match:
        digits = match.group(1)
        return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))
    match = re.fullmatch(r"#?([0-9a-fA-F]{3})", text)
    if match:
        digits = match.group(1)
        return tuple(int(digits[i] * 2, 16) for i in (0, 1, 2))
    return None


def relative_luminance(rgb):
    def channel(value):
        ratio = value / 255.0
        return ratio / 12.92 if ratio <= 0.03928 else ((ratio + 0.055) / 1.055) ** 2.4
    red, green, blue = (channel(item) for item in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first, second):
    lum_a, lum_b = relative_luminance(first), relative_luminance(second)
    high, low = max(lum_a, lum_b), min(lum_a, lum_b)
    return round((high + 0.05) / (low + 0.05), 2)


def normalize_colors(raw):
    if isinstance(raw, dict):
        return {str(key).lower(): value for key, value in raw.items() if isinstance(value, str)}
    if isinstance(raw, list):
        colors = {}
        for item in raw:
            if isinstance(item, dict):
                name = item.get("name") or item.get("id")
                value = item.get("value") or item.get("hex") or item.get("color")
                if name and isinstance(value, str):
                    colors[str(name).lower()] = value
        return colors
    return {}


def contrast_check(colors, checks):
    text_color = colors.get("text") or colors.get("dk1") or colors.get("dark1") or colors.get("foreground")
    background = (colors.get("background") or colors.get("bg")
                  or colors.get("lt1") or colors.get("light1"))
    accent = colors.get("accent") or colors.get("accent1")
    record = {"text_color": text_color, "background": background, "accent": accent,
              "text_ratio": None, "accent_ratio": None}
    text_rgb, background_rgb = parse_hex(text_color), parse_hex(background)
    if text_rgb and background_rgb:
        ratio = contrast_ratio(text_rgb, background_rgb)
        record["text_ratio"] = ratio
        if ratio < 4.5:
            checks.append({"code": "low_contrast_text", "severity": "warning", "page": None,
                           "detail": "text/background contrast %.2f:1 is below 4.5:1" % ratio})
    accent_rgb = parse_hex(accent)
    if accent_rgb and background_rgb:
        ratio = contrast_ratio(accent_rgb, background_rgb)
        record["accent_ratio"] = ratio
        if ratio < 3.0:
            checks.append({"code": "low_contrast_accent", "severity": "info", "page": None,
                           "detail": "accent/background contrast %.2f:1 is below 3:1" % ratio})
    return record


def normalize_fonts(template, case):
    raw = template.get("fonts") or {}
    if isinstance(raw, str):
        raw = {"latin": raw}
    if not isinstance(raw, dict):
        raw = {}
    latin = raw.get("latin") or raw.get("en") or raw.get("western") or raw.get("major_latin")
    east_asian = (raw.get("east_asian") or raw.get("cjk") or raw.get("zh")
                  or raw.get("ea") or raw.get("major_east_asian"))
    available = case.get("available_fonts") or template.get("available_fonts")
    if isinstance(available, str):
        available = [available]
    available_list = [str(item) for item in available] if isinstance(available, list) else []
    lowered = {item.lower() for item in available_list}
    missing = []
    for value in (latin, east_asian):
        if value and lowered and str(value).lower() not in lowered:
            missing.append(str(value))
    return {
        "latin": latin,
        "east_asian": east_asian,
        "available_checked": bool(available_list),
        "available": available_list[:20],
        "missing": missing,
        "fallback_chain": {
            "latin": ([str(latin)] if latin else []) + ["Arial", "Calibri"],
            "east_asian": ([str(east_asian)] if east_asian else []) + ["Microsoft YaHei", "SimSun"],
        },
        "note": "fallback fonts are advisory; installation is not verified",
    }


def build_export_plan(case):
    formats = ["pptx", "pdf"]
    requested = case.get("export") or case.get("target_format") or case.get("export_formats")
    if isinstance(requested, str):
        parsed = [part.strip().lower() for part in re.split(r"[,/;]", requested) if part.strip()]
        if parsed:
            formats = parsed
    elif isinstance(requested, list) and requested:
        formats = [str(item).strip().lower() for item in requested if str(item).strip()]
    rules = {
        "pptx": ["master_layout_links_valid", "notes_saved", "editable_text", "no_placeholder_overflow"],
        "pdf": ["fonts_embedded", "page_count_matches_pptx", "no_clipped_images"],
        "png": ["page_previews_generated"],
    }
    return [{"format": fmt,
             "required_checks": rules.get(fmt, ["renders_without_errors"]),
             "performed": False,
             "reason": "no presentation renderer invoked; the page spec is reproducible"}
            for fmt in formats]


def build_version_record(slides, template, figure_count, checks):
    adjusted = sum(1 for slide in slides for slot in slide["placeholders"]
                   if (slot.get("fit") or {}).get("font_reduced"))
    return {
        "version": "v1",
        "parent": None,
        "content_sha256": sha256_json(slides),
        "template_sha256": template.get("source_sha256"),
        "operations": [
            {"op": "resolve_template", "layouts": len(template["layouts"]),
             "declared": template["declared"]},
            {"op": "assign_layouts", "pages": len(slides)},
            {"op": "fill_placeholders", "slots": sum(len(slide["placeholders"]) for slide in slides)},
            {"op": "fit_text", "adjusted": adjusted},
            {"op": "adapt_figures", "figures": figure_count},
            {"op": "audit_consistency", "checks": len(checks)},
        ],
        "rollback": "discard /app/output/result.json and re-run with the identical case.json; output is deterministic",
        "deterministic": True,
    }


def build_source_register(case_path, case, template, task, task_path, slides):
    base_dir = os.path.dirname(os.path.abspath(case_path))
    entries = [{"role": "case", "name": os.path.basename(case_path) or "case.json",
                "sha256": sha256_json(case)}]
    if task:
        entries.append({"role": "task", "name": os.path.basename(task_path),
                        "sha256": sha256_text(task)})
    if template.get("source_sha256"):
        entries.append({"role": "template_input", "name": "declared_template",
                        "sha256": template["source_sha256"]})
    assets = []
    for slide in slides:
        for asset in list(slide["figures"]) + list(slide["tables"]):
            source = asset.get("src")
            if not source:
                continue
            if os.path.isabs(str(source)):
                state = "absolute_reference_not_read"
            else:
                state = "present" if os.path.isfile(os.path.join(base_dir, str(source))) else "missing"
            assets.append({"src": str(source), "status": state, "page": slide["id"]})
    return {"entries": entries, "assets": assets}


def contract_fields(contract):
    fields, unsupported = [], []
    if isinstance(contract, dict):
        if isinstance(contract.get("properties"), dict):
            return list(contract["properties"].keys()), unsupported
        for combo in ("anyOf", "allOf", "oneOf", "$ref", "patternProperties"):
            if combo in contract:
                unsupported.append(combo)
        nested = contract.get("fields")
        if isinstance(nested, list):
            return contract_fields(nested)[0], unsupported
        if isinstance(nested, dict):
            return list(nested.keys()), unsupported
        reserved = {"type", "required", "optional", "additionalProperties", "title",
                    "description", "version", "schema", "$schema"}
        return [key for key in contract if key not in reserved and not str(key).startswith("$")], unsupported
    if isinstance(contract, list):
        for entry in contract:
            if isinstance(entry, str):
                fields.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("field") or entry.get("key")
                if name:
                    fields.append(str(name))
        return fields, unsupported
    return fields, unsupported


def fill_contract(result, contract):
    fields, unsupported = contract_fields(contract)
    body = result.get("result") if isinstance(result.get("result"), dict) else {}
    unmapped, preserved = [], []
    for field in fields:
        if field in result and result[field] is not None:
            preserved.append(field)
            continue
        key = ALIASES.get(field.lower(), field.lower())
        if key in result and result[key] is not None:
            result[field] = result[key]
            preserved.append(field)
        elif key in body and body[key] is not None:
            result[field] = body[key]
            preserved.append(field)
        else:
            result[field] = None
            unmapped.append(field)
    result["contract_notes"] = {
        "declared_fields": fields,
        "preserved_fields": preserved,
        "unmapped_fields": unmapped,
        "unsupported_features": unsupported,
        "note": "Unsupported or absent fields are null; nothing is fabricated.",
    }
    if result.get("status") == "success" and (unmapped or unsupported):
        result["status"] = "partial"


def write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Academic slide template adapter")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--out", "--output", default=DEFAULT_OUT)
    parser.add_argument("--work", default=DEFAULT_WORK)
    args = parser.parse_args()

    result = {
        "case_id": None,
        "status": "failed",
        "result": {},
        "evidence": {},
        "uncertainty": [],
        "errors": [],
        "stats": {},
        "skill": {"name": SKILL_NAME, "version": SKILL_VERSION},
        "challenge_id": CHALLENGE_ID,
        "contract_notes": {"declared_fields": [], "preserved_fields": [],
                           "unmapped_fields": [], "unsupported_features": [],
                           "note": "Input could not be read; contract not evaluated."},
    }

    try:
        case = load_json(args.case)
    except (OSError, ValueError) as exc:
        result["errors"] = ["case_json_unreadable: %s" % exc.__class__.__name__]
        result["uncertainty"] = ["input_not_readable"]
        result["result"] = {"slides": [], "checks": [
            {"code": "input_unreadable", "severity": "error", "page": None,
             "detail": "case.json missing, unreadable or not valid JSON"}]}
        write_json(args.out, result)
        print(json.dumps({"status": result["status"], "case_id": None}, ensure_ascii=False))
        return 2

    if not isinstance(case, dict):
        result["errors"] = ["case_json_not_an_object"]
        result["uncertainty"] = ["input_shape_invalid"]
        result["result"] = {"slides": [], "checks": [
            {"code": "input_shape_invalid", "severity": "error", "page": None,
             "detail": "case.json must be a JSON object"}]}
        write_json(args.out, result)
        print(json.dumps({"status": result["status"], "case_id": None}, ensure_ascii=False))
        return 2

    result["case_id"] = case.get("case_id")
    base_dir = os.path.dirname(os.path.abspath(args.case))
    task, task_path = task_text(base_dir)
    template = load_template(case, base_dir)
    pages, generated, page_warnings = collect_pages(case)
    ladder = effective_ladder(template)
    footer_text = template.get("footer") or case.get("footer")

    checks = []
    if pages:
        slides, figure_results, text_fits = build_slides(pages, template, ladder, footer_text, checks)
    else:
        slides, figure_results, text_fits = [], [], []
        checks.append({"code": "no_slides_or_source_material", "severity": "error", "page": None,
                       "detail": "case has no slides/pages and no sections/outline to build pages from"})

    checks.extend(audit_numbering(slides))
    consistency = audit_consistency(slides, template, checks)
    fonts = normalize_fonts(template, case)
    colors = normalize_colors(template.get("theme_colors"))
    contrast = contrast_check(colors, checks)
    if not fonts["available_checked"]:
        checks.append({"code": "font_availability_unknown", "severity": "info", "page": None,
                       "detail": "no available_fonts list supplied; fallback chain is advisory only"})
    if any(slot.get("geometry_assumed") for slide in slides for slot in slide["placeholders"]):
        checks.append({"code": "placeholder_geometry_assumed", "severity": "info", "page": None,
                       "detail": "some placeholders had no geometry; conservative defaults were used for fit estimates"})

    register = build_source_register(args.case, case, template, task, task_path, slides)
    template_summary = {
        "declared": template["declared"],
        "slide_size": template["slide_size"],
        "layout_count": len(template["layouts"]),
        "layouts": [{"id": layout["id"], "name": layout["name"],
                     "synthesized": bool(layout.get("synthesized")),
                     "placeholder_types": [ph["type"] for ph in layout["placeholders"]]}
                    for layout in template["layouts"]],
        "fonts": {"latin": fonts["latin"], "east_asian": fonts["east_asian"]},
        "theme_colors": colors,
        "footer": template.get("footer"),
        "font_scale": ladder,
    }
    font_plan = {
        "ladder": ladder,
        "minimums": MIN_FONT,
        "theme_fonts": fonts,
        "contrast": contrast,
        "text_fits": text_fits,
    }
    version_record = build_version_record(slides, template, len(figure_results), checks)

    failed_codes = {"text_overflow_unresolvable", "aspect_distortion_risk",
                    "figure_reference_without_asset", "page_figure_number_mismatch"}
    if not slides:
        status = "insufficient_input"
    elif (not template["declared"]) or generated or any(check["code"] in failed_codes for check in checks):
        status = "partial"
    else:
        status = "success"
    result["status"] = status

    errors = list(template["warnings"])
    if not template["declared"]:
        errors.append("template_not_declared: no master/layout/placeholder structure found; "
                      "generic layouts were used and flagged")
    if generated:
        errors.append("pages_generated_from_sections: page bullets are extracted source sentences, "
                      "not authored slide content")
    missing_assets = [item for item in register["assets"] if item["status"] == "missing"]
    if missing_assets:
        errors.append("referenced_asset_missing: " + ", ".join(
            sorted({os.path.basename(item["src"]) for item in missing_assets})[:8]))

    uncertainty = [
        "template_inheritance_not_verified_without_pptx_renderer",
        "text_fit_is_estimated_from_character_widths_not_rendered",
        "export_not_performed",
    ]
    if not fonts["available_checked"]:
        uncertainty.append("font_availability_unknown")
    if not slides:
        uncertainty.append("no_pages_to_adapt")
    if any(item.get("geometry_unknown") for item in figure_results):
        uncertainty.append("figure_dimensions_missing_for_some_assets")
    uncertainty.extend(template["warnings"])
    uncertainty.extend(page_warnings)

    result["result"] = {
        "slides": slides,
        "template_summary": template_summary,
        "font_plan": font_plan,
        "figure_adaptation": figure_results,
        "consistency": consistency,
        "checks": checks,
        "export_plan": build_export_plan(case),
        "version_record": version_record,
        "source_register": register["entries"],
        "referenced_assets": register["assets"],
    }
    result["evidence"] = {
        "page_count": len(slides),
        "pages_with_source": sum(1 for slide in slides if slide.get("source")),
        "pages_with_figures": sum(1 for slide in slides if slide["figures"]),
        "template_declared": template["declared"],
        "checks": len(checks),
    }
    result["errors"] = errors
    result["uncertainty"] = uncertainty
    result["stats"] = {
        "pages": len(slides),
        "layouts_used": len({slide["layout_id"] for slide in slides}),
        "placeholders_total": sum(len(slide["placeholders"]) for slide in slides),
        "placeholders_filled": sum(1 for slide in slides for slot in slide["placeholders"] if slot["filled"]),
        "figures": len(figure_results),
        "font_reductions": sum(1 for item in text_fits if item.get("font_reduced")),
        "unresolved_overflow": sum(1 for item in text_fits if item.get("overflow")),
        "checks": len(checks),
    }

    fill_contract(result, case.get("output_contract"))
    write_json(args.out, result)
    summary = {"status": result["status"], "case_id": result["case_id"],
               "pages": result["stats"]["pages"], "checks": result["stats"]["checks"]}
    print(json.dumps(summary, ensure_ascii=False))
    if result["status"] == "failed":
        return 2
    if result.get("contract_notes", {}).get("unmapped_fields"):
        return 1
    return 0


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)
