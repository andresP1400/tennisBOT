"""Regex-based signal parsers for tennis player news research.

Pure functions used by PlayerNewsResearcher to turn research text into
structured features (injury / form / coach). Regex hits on live web
research are treated as fresher evidence than LLM facts, so they win
during the merge.
"""
from __future__ import annotations

import re


def parse_injury_status(text: str) -> dict:
    """Extract injury signals from research text."""
    result: dict = {
        "injury_flag": 0,
        "injury_severity": 0,
        "injury_detail": "",
    }
    if not text:
        return result
    text_lower = text.lower()
    major_injuries = [
        r"torn\s+\w+", r"acl\s+tear", r"surgery", r"out\s+for\s+the\s+season",
        r"withdrawn?\s+(due|because|with)", r"retired?\s+(from|due|injury)",
        r"significant\s+injury", r"long-term\s+injury", r"serious\s+injury",
        r"stress\s+fracture", r"hernia", r"meniscus",
    ]
    minor_injuries = [
        r"niggle", r"slight\s+\w+\s+injury", r"minor\s+injury",
        r"strapping", r"heavily\s+strapped", r"received\s+treatment",
        r"groin\s+tightness", r"shoulder\s+soreness", r"back\s+spasms?",
        r"ankle\s+sprain", r"quad\s+strain", r"hamstring\s+tight",
        r"abrasion", r"blisters?", r"illness", r"flu", r"fever",
        r"covid", r"virus", r"stomach\s+bug",
    ]
    for pattern in major_injuries:
        if re.search(pattern, text_lower):
            result["injury_flag"] = 1
            result["injury_severity"] = 2
            match = re.search(pattern, text)
            if match:
                result["injury_detail"] = match.group(0)
            return result
    for pattern in minor_injuries:
        if re.search(pattern, text_lower):
            result["injury_flag"] = 1
            result["injury_severity"] = 1
            match = re.search(pattern, text)
            if match:
                result["injury_detail"] = match.group(0)
            return result
    return result


def parse_form_context(text: str) -> dict:
    """Extract recent form signals from research text."""
    result: dict = {
        "form_sentiment": 0,
        "form_detail": "",
    }
    if not text:
        return result
    text_lower = text.lower()
    positive = [
        r"on\s+a\s+winning\s+streak", r"in\s+excellent\s+form",
        r"playing\s+the\s+best\s+tennis", r"undefeated\s+in\s+\d+",
        r"won\s+the\s+title", r"defending\s+champion",
        r"in\s+great\s+shape", r"dominant\s+performance",
        r"career-high\s+ranking", r"climbing\s+the\s+rankings",
    ]
    negative = [
        r"losing\s+streak", r"poor\s+form", r"struggling\s+with",
        r"early\s+exit", r"first\s+round\s+exit", r"upset\s+loss",
        r"out\s+of\s+form", r"hasn't\s+won\s+in",
        r"slump", r"consecutive\s+defeats", r"dropped\s+in\s+the\s+rankings",
    ]
    for pattern in negative:
        if re.search(pattern, text_lower):
            result["form_sentiment"] = -1
            match = re.search(pattern, text)
            if match:
                result["form_detail"] = match.group(0)
            return result
    for pattern in positive:
        if re.search(pattern, text_lower):
            result["form_sentiment"] = 1
            match = re.search(pattern, text)
            if match:
                result["form_detail"] = match.group(0)
            return result
    return result


def parse_coach_change(text: str) -> dict:
    """Detect recent coach changes from research text."""
    result: dict = {"coach_change_flag": 0, "coach_change_detail": ""}
    if not text:
        return result
    text_lower = text.lower()
    patterns = [
        r"new\s+coach", r"parted?\s+ways\s+with\s+(?:his|her)\s+coach",
        r"split\s+with\s+coach", r"hired?\s+a?\s*new\s+coach",
        r"coaching\s+change", r"replaced?\s+(?:his|her)\s+coach",
    ]
    for pattern in patterns:
        if re.search(pattern, text_lower):
            result["coach_change_flag"] = 1
            match = re.search(pattern, text)
            if match:
                result["coach_change_detail"] = match.group(0)
            return result
    return result


def merge_facts(regex_facts: dict, llm_facts: dict | None) -> dict:
    """Merge regex (fresh web evidence) with LLM facts.

    Regex hits on live web research are treated as fresher evidence and
    win over the LLM; otherwise the LLM fills the fields so nothing
    stays empty.
    """
    merged = dict(regex_facts)
    if llm_facts is None:
        return merged
    if merged["injury_flag"] == 0 and llm_facts["injury_flag"]:
        merged["injury_flag"] = llm_facts["injury_flag"]
        merged["injury_severity"] = llm_facts["injury_severity"]
        merged["injury_detail"] = llm_facts["injury_detail"]
    elif merged["injury_flag"] == 0:
        merged["injury_detail"] = llm_facts["injury_detail"]
    if merged["form_sentiment"] == 0 and llm_facts["form_sentiment"]:
        merged["form_sentiment"] = llm_facts["form_sentiment"]
        merged["form_detail"] = llm_facts["form_detail"]
    elif merged["form_sentiment"] == 0:
        merged["form_detail"] = llm_facts["form_detail"]
    if merged["coach_change_flag"] == 0 and llm_facts["coach_change_flag"]:
        merged["coach_change_flag"] = llm_facts["coach_change_flag"]
        merged["coach_change_detail"] = llm_facts["coach_change_detail"]
    elif merged["coach_change_flag"] == 0:
        merged["coach_change_detail"] = llm_facts["coach_change_detail"]
    return merged
