"""Drop-in replacement for the archived pytrends library.

Same calls as pytrends (TrendReq, build_payload, interest_over_time, ...), but the
data comes from a hosted Google Trends actor on Apify, so there are no 429 errors
to handle on your side. Needs an Apify API token (free account, $5 monthly credit).
"""
import os
import re

import pandas as pd
import requests

__version__ = "0.1.0"
__all__ = ["TrendReq", "TrendsError"]

ACTOR = "githubanassk~google-trends-scraper"
API = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

# pytrends' trending_searches(pn=...) takes country names; the actor takes ISO codes.
# ponytail: common countries only; any two-letter code also works.
COUNTRY_CODES = {
    "united_states": "US", "united_kingdom": "GB", "canada": "CA", "australia": "AU",
    "india": "IN", "germany": "DE", "france": "FR", "japan": "JP", "brazil": "BR",
    "mexico": "MX", "spain": "ES", "italy": "IT", "netherlands": "NL", "south_korea": "KR",
    "indonesia": "ID", "turkey": "TR", "poland": "PL", "south_africa": "ZA", "nigeria": "NG",
    "philippines": "PH", "singapore": "SG", "sweden": "SE", "argentina": "AR",
}
GPROP = {"": "", "images": "images", "news": "news", "youtube": "youtube", "froogle": "froogle"}


class TrendsError(Exception):
    pass


def _number(formatted):
    """'+3,800%' -> 3800, '100' -> 100, 'Breakout' -> None (see formattedValue)."""
    digits = re.sub(r"[^\d]", "", str(formatted))
    return int(digits) if digits else None


class TrendReq:
    def __init__(self, hl="en-US", tz=360, geo="", timeout=None, proxies=None, retries=0,
                 backoff_factor=0, requests_args=None, apify_token=None, actor=ACTOR):
        # hl, tz, timeout, proxies, retries, backoff_factor and requests_args are
        # accepted for pytrends compatibility; the actor handles proxies and retries.
        token = apify_token or os.environ.get("APIFY_TOKEN")
        if not token:
            raise TrendsError("Set APIFY_TOKEN or pass apify_token=... "
                              "(free at https://console.apify.com/settings/integrations).")
        self._token, self._url = token, API.format(actor=actor.replace("/", "~"))
        self._timeout = timeout if isinstance(timeout, (int, float)) else 300
        self.geo = geo
        self.kw_list, self.cat, self.timeframe, self.gprop = [], 0, "today 5-y", ""
        self._runs = {}

    def build_payload(self, kw_list, cat=0, timeframe="today 5-y", geo="", gprop=""):
        if gprop not in GPROP:
            raise ValueError("gprop must be empty or one of images, news, youtube, froogle")
        self.kw_list, self.cat, self.timeframe, self.gprop = list(kw_list), cat, timeframe, gprop
        self.geo = geo or self.geo
        self._runs = {}  # new payload, new data

    def _run(self, run_input):
        """One HTTP call: start the actor, wait for it, return its rows."""
        resp = requests.post(self._url, json=run_input, timeout=self._timeout,
                             headers={"Authorization": f"Bearer {self._token}"})
        if resp.status_code >= 300:
            try:
                msg = resp.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                msg = resp.text[:300]
            raise TrendsError(f"Google Trends request failed ({resp.status_code}): {msg}")
        return resp.json()

    def _keywords(self, region_level=""):
        """One actor run per payload (and per region level); every method reads from it."""
        if not self.kw_list:
            raise TrendsError("Call build_payload(kw_list=[...]) first.")
        if region_level not in self._runs:
            rows = self._run({
                "keywords": self.kw_list, "geos": [self.geo] if self.geo else [],
                "timeframe": self.timeframe, "category": self.cat,
                "searchProperty": self.gprop, "regionLevel": region_level,
                "includeRelatedQueries": True,
            })
            self._runs[region_level] = {r["keyword"]: r for r in rows if r.get("type") == "keyword"}
        return self._runs[region_level]

    def interest_over_time(self):
        """DataFrame indexed by date, one column per keyword (shared 0-100 scale), plus isPartial."""
        rows = self._keywords()
        df = pd.DataFrame({
            kw: pd.Series({pd.Timestamp(p["date"]).tz_localize(None): p["value"] for p in rows[kw]["timeline"]})
            for kw in self.kw_list if kw in rows
        })
        if df.empty:
            return df
        df.index.name = "date"
        df["isPartial"] = False
        return df

    def interest_by_region(self, resolution="COUNTRY", inc_low_vol=True, inc_geo_code=False):
        # Worldwide + COUNTRY is the actor's automatic level; a country geo needs an explicit level.
        level = "" if resolution == "COUNTRY" and not self.geo else resolution.upper()
        if level == "CITY":
            raise TrendsError("City resolution is not supported; use REGION or DMA.")
        rows = self._keywords(level)
        frames = {}
        for kw in self.kw_list:
            regions = (rows.get(kw) or {}).get("interestByRegion") or []
            frames[kw] = pd.Series({r["geoName"]: r["value"] for r in regions})
        df = pd.DataFrame(frames)
        df.index.name = "geoName"
        if not inc_low_vol:
            df = df[(df.fillna(0) > 0).any(axis=1)]
        if inc_geo_code:
            codes = {r["geoName"]: r["geoCode"] for kw in self.kw_list
                     for r in (rows.get(kw) or {}).get("interestByRegion") or []}
            df.insert(0, "geoCode", df.index.map(codes))
        return df

    def related_queries(self):
        """{keyword: {"top": DataFrame, "rising": DataFrame}} like pytrends."""
        rows = self._keywords()
        out = {}
        for kw in self.kw_list:
            r = rows.get(kw) or {}
            out[kw] = {}
            for key, field in (("top", "relatedQueriesTop"), ("rising", "relatedQueriesRising")):
                items = r.get(field) or []
                out[kw][key] = pd.DataFrame(
                    [{"query": q["query"], "value": _number(q["value"]), "formattedValue": q["value"]} for q in items],
                    columns=["query", "value", "formattedValue"],
                ) if items else None
        return out

    def trending_searches(self, pn="united_states"):
        """DataFrame with one column (0) of trending search titles, like pytrends."""
        df = self.realtime_trending_searches(pn)
        return pd.DataFrame({0: df["title"]}) if not df.empty else pd.DataFrame({0: []})

    def realtime_trending_searches(self, pn="US", cat="all", count=300):
        code = pn.upper() if len(pn) == 2 else COUNTRY_CODES.get(pn.lower())
        if not code:
            raise ValueError(f"Unknown country '{pn}'. Use a two-letter code such as US or GB.")
        rows = [r for r in self._run({"trendingNowGeos": [code]}) if r.get("type") == "trendingNow"]
        return pd.DataFrame(rows[:count])

    today_searches = trending_searches

    def related_topics(self):
        raise TrendsError("related_topics is not available yet; related_queries is.")

    def suggestions(self, keyword):
        raise TrendsError("suggestions is not available yet.")
