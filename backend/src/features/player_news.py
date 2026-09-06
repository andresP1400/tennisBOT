"""Player news and contextual research module.

Uses GPT Researcher (https://github.com/assafelovic/gpt-researcher) for
autonomous research on tennis players before matches. Falls back to a
simple web search when GPT Researcher is unavailable.

Provides:
  - injury status detection
  - recent form analysis from news
  - coach change detection
  - surface preference context
  - fatigue / retirement signals

These "soft signals" complement the hard statistical features in the ML
model, capturing information that numbers alone miss.

Usage:
    from features.player_news import PlayerNewsResearcher
    researcher = PlayerNewsResearcher()
    report = researcher.research_player("Jannik Sinner", "Clay")
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any


from logging_config import get_logger
from features.news_signals import (
    merge_facts,
    parse_coach_change,
    parse_form_context,
    parse_injury_status,
)

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

_news_cache: dict[str, Any] = {}
NEWS_CACHE_TTL = 3600  # 1 hour


def _now_iso() -> str:
    """Current UTC time as ISO 8601 (datetime.utcnow() is deprecated)."""
    return datetime.now(timezone.utc).isoformat()


class PlayerNewsResearcher:
    """Research tennis player context using GPT Researcher or fallback."""

    def __init__(self, llm_provider: str | None = None) -> None:
        self.llm_provider = llm_provider or config.settings.llm_provider
        self._researcher: Any = None

    def _get_researcher(self) -> Any:
        """Lazy-initialize GPT Researcher."""
        if self._researcher is not None:
            return self._researcher
        try:
            from gpt_researcher import GPTResearcher

            self._researcher = GPTResearcher
            return self._researcher
        except ImportError:
            logger.warning(
                " [WARN] gpt-researcher not installed. Install with: pip install gpt-researcher"
            )
            logger.warning(" [WARN] Using fallback web search mode")
            return None

    async def _research_with_gpt_researcher(self, query: str) -> str:
        """Run GPT Researcher for a specific query."""
        Researcher = self._get_researcher()
        if Researcher is None:
            return ""
        try:
            # Point gpt_researcher at NVIDIA NIM (OpenAI-compatible). It
            # parses "<provider>:<model>" strings and reads env vars for
            # API key / base URL, so we only set FAST/SMART/STRATEGIC LLM
            # env vars (overriding any stale config) and leave the OpenAI
            # client to pick up OPENAI_API_KEY/OPENAI_BASE_URL from env.
            api_key = config.settings.openai_api_key
            base_url = config.settings.openai_base_url
            model = config.settings.nvidia_model
            if (
                api_key
                and "nvapi-" in api_key
                and "integrate.api.nvidia.com" in base_url
            ):
                os.environ["FAST_LLM"] = f"openai:{model}"
                os.environ["SMART_LLM"] = f"openai:{model}"
                os.environ["STRATEGIC_LLM"] = f"openai:{model}"
                os.environ["FAST_LLM_MODEL"] = ""  # clear legacy aliases
                os.environ["SMART_LLM_MODEL"] = ""
                os.environ["LLM_PROVIDER"] = "openai"
            if not config.settings.tavily_api_key:
                os.environ["RETRIEVER"] = "duckduckgo"  # free, no API key
            researcher = Researcher(
                query=query,
                report_type="research_report",
                max_subtopics=4,
                subtopics=[],
            )
            return await researcher.conduct_research()  # type: ignore[no-any-return]
        except Exception as e:
            logger.warning(f" [WARN] GPT Researcher failed: {e}")
            return ""

    def _fallback_web_search(self, query: str) -> str:
        """Simple fallback using requests + web search when GPT Researcher is unavailable."""
        try:
            import requests

            url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("Abstract", "")  # type: ignore[no-any-return]
        except Exception as exc:
            logger.warning("fallback web search failed: %s", exc)
        return ""

    def _llm_extract_facts(
        self, player_name: str, surface: str | None = None
    ) -> dict[str, Any] | None:
        """Extract structured facts directly from the LLM (fast, primary source).

        Returns a dict with injury/form/coach keys, or None when the LLM is
        unusable. JSON is parsed from the model reply so detail fields are
        always populated (never silently empty).
        """
        api_key = config.settings.openai_api_key
        base_url = config.settings.openai_base_url
        model = config.settings.nvidia_model
        if not api_key or "nvapi-" not in api_key:
            return None
        try:
            from openai import OpenAI
            import json

            client = OpenAI(api_key=api_key, base_url=base_url, timeout=60)
            surface_ctx = surface or "any"
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            prompt = (
                f"Tennis player: {player_name}. Surface context: {surface_ctx}. "
                f"Current date: {today}.\n"
                "Report ONLY recent facts (last ~6 months, current season): "
                "(1) injury status [flag 0=none,1=minor,2=major; severity 0-2; "
                "detail = specific body part/surgery or 'no injury concerns reported'] "
                "(2) recent form [sentiment -1/0/1; detail = CURRENT-season streaks/"
                "results ONLY, never career achievements or historical titles; "
                "if you have no current-season info use sentiment 0 and detail "
                "'no specific recent information'] "
                "(3) coach change [flag 0/1; detail, only if this season]. "
                "Reply with ONLY valid JSON: "
                '{"injury":{"flag":0,"severity":0,"detail":""},'
                '"form":{"sentiment":0,"detail":""},'
                '"coach":{"flag":0,"detail":""}}'
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=400,
            )
            content = (resp.choices[0].message.content or "").strip()
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group(0))
            injury = data.get("injury") or {}
            form = data.get("form") or {}
            coach = data.get("coach") or {}
            result = {
                "injury_flag": int(injury.get("flag", 0)),
                "injury_severity": int(injury.get("severity", 0)),
                "injury_detail": str(injury.get("detail", "")).strip(),
                "form_sentiment": int(form.get("sentiment", 0)),
                "form_detail": str(form.get("detail", "")).strip(),
                "coach_change_flag": int(coach.get("flag", 0)),
                "coach_change_detail": str(coach.get("detail", "")).strip(),
            }
            return result
        except Exception as e:
            logger.warning(f" [WARN] LLM fact extraction failed: {e}")
            return None

    def _run_research(self, query: str) -> str:
        """Run GPT Researcher asynchronously, or fall back to web search.

        Uses asyncio.run() instead of asyncio.get_event_loop() to avoid
        DeprecationWarning on Python 3.12+.
        """
        try:
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if running_loop is not None:
                # We're inside an async context: don't block; use fallback.
                return self._fallback_web_search(query)
            return asyncio.run(self._research_with_gpt_researcher(query))
        except Exception:
            return self._fallback_web_search(query)

    def research_player(
        self,
        player_name: str,
        surface: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Research a tennis player's current context.

        Combines injury status, recent form, and coach changes into
        structured features for the model.
        """
        cache_key = f"{player_name}|{surface}"
        if not force_refresh and cache_key in _news_cache:
            age = time.time() - _news_cache[cache_key].get("timestamp", 0)
            if age < NEWS_CACHE_TTL:
                return _news_cache[cache_key]  # type: ignore[no-any-return]

        surface_ctx = f" on {surface}" if surface else ""
        query = (
            f"Is {player_name} injured{surface_ctx}? "
            f"{player_name} recent form and results. "
            f"Has {player_name} changed coach recently?"
        )
        research_text = self._run_research(query)
        injury = parse_injury_status(research_text)
        form = parse_form_context(research_text)
        coach = parse_coach_change(research_text)
        regex_facts = {**injury, **form, **coach}
        llm_facts = self._llm_extract_facts(player_name, surface)
        facts = merge_facts(regex_facts, llm_facts)
        result = {
            "injury_flag": facts["injury_flag"],
            "injury_severity": facts["injury_severity"],
            "injury_detail": facts["injury_detail"],
            "form_sentiment": facts["form_sentiment"],
            "form_detail": facts["form_detail"],
            "coach_change_flag": facts["coach_change_flag"],
            "coach_change_detail": facts["coach_change_detail"],
            "raw_research": research_text[:500] if research_text else "",
            "timestamp": time.time(),
            "timestamp_iso": _now_iso(),
        }
        _news_cache[cache_key] = result
        return result

    def research_matchup(
        self,
        player1: str,
        player2: str,
        surface: str | None = None,
    ) -> dict[str, Any]:
        """Research both players for a matchup and compute diff features."""
        p1 = self.research_player(player1, surface)
        p2 = self.research_player(player2, surface)
        return {
            "p1_injury_flag": p1["injury_flag"],
            "p2_injury_flag": p2["injury_flag"],
            "injury_flag_diff": p1["injury_flag"] - p2["injury_flag"],
            "p1_injury_severity": p1["injury_severity"],
            "p2_injury_severity": p2["injury_severity"],
            "injury_severity_diff": p1["injury_severity"] - p2["injury_severity"],
            "p1_form_sentiment": p1["form_sentiment"],
            "p2_form_sentiment": p2["form_sentiment"],
            "form_sentiment_diff": p1["form_sentiment"] - p2["form_sentiment"],
            "p1_coach_change_flag": p1["coach_change_flag"],
            "p2_coach_change_flag": p2["coach_change_flag"],
            "coach_change_diff": p1["coach_change_flag"] - p2["coach_change_flag"],
            "p1_injury_detail": p1["injury_detail"],
            "p2_injury_detail": p2["injury_detail"],
            "p1_form_detail": p1["form_detail"],
            "p2_form_detail": p2["form_detail"],
            "p1_coach_change_detail": p1["coach_change_detail"],
            "p2_coach_change_detail": p2["coach_change_detail"],
        }
