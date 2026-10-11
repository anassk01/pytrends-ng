"""Offline check: fake actor rows in, pytrends-shaped DataFrames out."""
import pytrends_ng
from pytrends_ng import TrendReq, _number

ROWS = [
    {"type": "keyword", "keyword": "claude",
     "timeline": [{"date": "2026-07-10T00:00:00Z", "value": 23}, {"date": "2026-07-11T00:00:00Z", "value": 20.5}],
     "interestByRegion": [{"geoCode": "US-CA", "geoName": "California", "value": 100},
                          {"geoCode": "US-TX", "geoName": "Texas", "value": 0}],
     "relatedQueriesTop": [{"query": "claude ai", "value": "100"}],
     "relatedQueriesRising": [{"query": "claude 5", "value": "+3,800%"}, {"query": "claude code", "value": "Breakout"}]},
    {"type": "keyword", "keyword": "gemini",
     "timeline": [{"date": "2026-07-10T00:00:00Z", "value": 40}, {"date": "2026-07-11T00:00:00Z", "value": 37}],
     "interestByRegion": [{"geoCode": "US-CA", "geoName": "California", "value": 80}],
     "relatedQueriesTop": [], "relatedQueriesRising": []},
    {"type": "trendingNow", "geo": "US", "title": "chicago marathon", "approxTraffic": "2000+"},
]


def make(calls):
    t = TrendReq(apify_token="x")

    def fake_run(run_input):
        calls.append(run_input)
        return ROWS
    t._run = fake_run
    return t


def test_pytrends_shapes():
    calls = []
    t = make(calls)
    t.build_payload(["claude", "gemini"], timeframe="today 3-m", geo="US")

    iot = t.interest_over_time()
    assert list(iot.columns) == ["claude", "gemini", "isPartial"]
    assert iot.index.name == "date" and iot["claude"].iloc[1] == 20.5

    rq = t.related_queries()
    assert rq["claude"]["rising"]["value"].tolist()[0] == 3800
    assert rq["claude"]["rising"]["formattedValue"].tolist()[1] == "Breakout"
    assert rq["gemini"]["top"] is None
    assert len(calls) == 1  # one run serves every method for the same payload

    ibr = t.interest_by_region(resolution="REGION", inc_low_vol=False, inc_geo_code=True)
    assert calls[-1]["regionLevel"] == "REGION" and len(calls) == 2
    assert list(ibr.index) == ["California"] and ibr.loc["California", "geoCode"] == "US-CA"

    assert t.trending_searches(pn="united_states")[0].tolist() == ["chicago marathon"]
    assert calls[-1] == {"trendingNowGeos": ["US"]}


def test_number():
    assert _number("+1,650%") == 1650 and _number("Breakout") is None and _number("81") == 81


if __name__ == "__main__":
    test_pytrends_shapes(); test_number(); print("ok", pytrends_ng.__version__)
