# pytrends-ng: pytrends without the 429 errors

[pytrends](https://github.com/GeneralMills/pytrends) was archived in April 2025 and its last release is from 2023. Google answers it with `429 Too Many Requests` most of the time. `pytrends-ng` keeps the same calls, so your code works again after changing one import:

```python
# from pytrends.request import TrendReq
from pytrends_ng import TrendReq

pytrends = TrendReq()  # reads APIFY_TOKEN from the environment
pytrends.build_payload(["chatgpt", "claude", "gemini"], timeframe="today 3-m", geo="US")

pytrends.interest_over_time()        # DataFrame: date index, one column per keyword, isPartial
pytrends.interest_by_region()        # DataFrame: one row per region
pytrends.related_queries()           # {keyword: {"top": DataFrame, "rising": DataFrame}}
pytrends.trending_searches(pn="united_states")
```

## How it works

The requests run on a hosted [Google Trends actor](https://apify.com/githubanassk/google-trends-scraper) on Apify, which rotates IPs and retries rate limits for you. No proxies to buy, no sleep loops.

1. Create a free Apify account. It includes $5 of usage every month.
2. Copy your API token from [Settings > Integrations](https://console.apify.com/settings/integrations).
3. `pip install pytrends-ng` and `export APIFY_TOKEN=...`

Pricing is $2 per 1,000 results, where one result is one keyword in one country with its full timeline, regions and related queries. A 5-keyword payload costs $0.01, so the free credit covers about 2,500 keywords a month.

## Better than the original

- **More than 5 keywords.** `build_payload` takes any number of keywords and puts them all on one shared 0-100 scale. Google's own limit is 5.
- **Small keywords stay accurate.** Keywords far smaller than the biggest one keep decimal values instead of rounding to 0.
- **One request per payload.** `interest_over_time`, `interest_by_region` and `related_queries` all read from the same run.

## Supported calls

| pytrends call | Status |
|---|---|
| `build_payload(kw_list, cat, timeframe, geo, gprop)` | Yes |
| `interest_over_time()` | Yes |
| `interest_by_region(resolution, inc_low_vol, inc_geo_code)` | COUNTRY, REGION, DMA (not CITY) |
| `related_queries()` | Yes. `value` is numeric; `formattedValue` keeps Google's text such as `Breakout` |
| `trending_searches(pn)`, `today_searches(pn)`, `realtime_trending_searches(pn)` | Yes |
| `related_topics()`, `suggestions()` | Not yet |

Constructor arguments such as `hl`, `tz`, `proxies` and `retries` are accepted and ignored, so existing code does not break.

## License

MIT. Not affiliated with Google or the original pytrends authors.
