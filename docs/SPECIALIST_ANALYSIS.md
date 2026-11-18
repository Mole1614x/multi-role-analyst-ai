# Specialist analysis

Select the named role on the project and include the method phrase in the analysis request. The methods operate on the selected immutable dataset version. An omitted or unavailable method leaves ordinary role analysis available.

| Role | Baseline capability | Expanded capability |
| --- | --- | --- |
| Data | Descriptive statistics for one numeric measure | |
| Business | Actual minus target | |
| Market research | Segment size divided by market size | |
| Finance | Profit and profit margin | Budget variance and cash flow |
| Marketing | Attributed revenue divided by ad spend | Last-touch attribution |
| Sales | Total booked revenue | |
| Product | Retained divided by eligible | Retention and churn per cohort |
| HR | Aggregate turnover with small samples suppressed | |
| Operations | Fulfillment divided by orders | |
| BI | Completeness, missing cells, duplicate rows | |
| Risk | Interquartile-range outlier count | |
| Investment | Compounded periodic return and sample volatility | |

- **Budget variance** uses `actual` and `budget`, in one currency and comparable reporting periods. Sum each column over complete rows. Amount variance is actual minus budget. The rate is amount variance divided by the absolute planned total and is absent for a zero total. Sign shows direction and does not imply favorability.
- **Cash flow** uses nonnegative `cash_inflow` and `cash_outflow` in one currency. Net cash flow is summed inflows minus summed outflows across complete rows.
- **Attribution** uses `conversion_id`, `channel`, `touch_at`, and `conversion_value`. Supply only eligible pre-conversion touches and use a single currency. The latest UTC timestamp assigns the entire conversion and its revenue to one channel. Incomplete rows, inconsistent values, and ties across channels prevent calculation.
- **Cohort churn** uses `cohort`, `eligible`, and `retained`. Supply disjoint counts for a common observation window. Sum complete rows for each cohort. Churn count is eligible minus retained and churn rate is churn divided by eligible. Retention rate is retained divided by eligible. Both rates are fractions and are absent for empty cohorts.

Numeric coercion failures and nonfinite inputs are missing. Each result records excluded rows. Neither currency conversion nor attribution incrementality is inferred.
