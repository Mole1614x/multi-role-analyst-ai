# Analyst roles

Select roles during project creation and narrow the assignment for each chat request. The role registry provides a capability template, output name, input expectations, and review policy for every role. Every role shares the same versioned dataset and calculation engine.

| Role | Implemented calculation | Required fields |
| --- | --- | --- |
| Data | Numeric summary | Named or first available numeric field |
| Business | Actual minus target | `actual`, `target` |
| Market research | Segment share | `segment_size`, `market_size` |
| Financial | Profit and margin | `revenue`, `expenses` |
| Marketing | Return on ad spend | `attributed_revenue`, `ad_spend` |
| Sales | Booked revenue | `revenue` |
| Product | Retention | `retained`, `eligible` |
| HR | Aggregate turnover | `departures`, `average_headcount`, at least ten complete rows |
| Operations | Fulfillment rate | `fulfilled`, `ordered` |
| Business intelligence | Completeness and duplicate rows | Any tabular dataset |
| Risk | IQR outlier count | Named or first available numeric field |
| Investment | Compounded return and observed volatility | `period_return` as a decimal |

An analysis marks unavailable results when required fields are missing. Review matching units, identifiers, and time windows before making decisions. To extend the registry, register a `Role` with a supported tool and input contract in `backend/app/analytics/roles.py`. Add tests for any new calculation or validation policy.
