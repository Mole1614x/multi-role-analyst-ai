# Specialist analysis

Select the named role on the project and include the method phrase in the analysis request. The methods operate on the selected immutable dataset version. Use a general analysis request to select the baseline method.

| Role | Baseline capability | Expanded capability |
| --- | --- | --- |
| Data | Descriptive statistics for one numeric measure | Pearson correlation |
| Business | Actual minus target | Business case return |
| Market research | Segment size divided by market size | TAM, SAM, and SOM estimates |
| Finance | Profit and profit margin | Budget variance and cash flow |
| Marketing | Attributed revenue divided by ad spend | Last-touch attribution |
| Sales | Total booked revenue | Weighted pipeline |
| Product | Retained divided by eligible | Retention and churn per cohort |
| HR | Aggregate turnover with small samples suppressed | Aggregate hiring funnel |
| Operations | Fulfillment divided by orders | Inventory days of supply |
| BI | Completeness, missing cells, duplicate rows | Key uniqueness |
| Risk | Interquartile-range outlier count | Expected loss |
| Investment | Compounded periodic return and sample volatility | Maximum drawdown |

- **Budget variance** uses `actual` and `budget`, in one currency and comparable reporting periods. Sum each column over complete rows. Amount variance is actual minus budget. The rate is amount variance divided by the absolute planned total and is absent for a zero total. Sign shows direction and does not imply favorability.
- **Cash flow** uses nonnegative `cash_inflow` and `cash_outflow` in one currency. Net cash flow is summed inflows minus summed outflows across complete rows.
- **Attribution** uses `conversion_id`, `channel`, `touch_at`, and `conversion_value`. Supply only eligible pre-conversion touches and use a single currency. The latest UTC timestamp assigns the entire conversion and its revenue to one channel. Incomplete rows, inconsistent values, and ties across channels prevent calculation.
- **Cohort churn** uses `cohort`, `eligible`, and `retained`. Supply disjoint counts for a common observation window. Sum complete rows for each cohort. Churn count is eligible minus retained and churn rate is churn divided by eligible. Retention rate is retained divided by eligible. Both rates are fractions and are absent for empty cohorts.

- **Pearson correlation** uses complete numeric pairs in `x` and `y`. It computes standard sample covariance divided by the product of sample standard deviations. It requires at least three complete pairs and two nonconstant measures.
- **Business case** sums comparable `expected_benefit` and nonnegative `implementation_cost` values. Net benefit is benefit minus cost. Return on cost divides that result by total cost and is absent when cost is zero.
- **Market sizing** or **TAM, SAM, SOM** uses nested counts in `total_accounts`, `serviceable_accounts`, and `obtainable_accounts`. Multiply each count by `annual_revenue_per_account` and sum disjoint segments. Results estimate annual revenue in the input currency.
- **Weighted pipeline** computes the sum of `deal_amount` times close `probability` in decimal form. Use one row per deal and a common currency.
- **Hiring funnel** sums `applicants`, `interviewed`, and `hired` over disjoint aggregates. It divides total interviews by applicants and total hires by interviews. Stage and drop-off counts below ten suppress all outputs.
- **Inventory coverage** divides summed `average_inventory` by summed `daily_demand` to estimate days of supply in comparable units. Zero demand leaves the ratio absent.
- **Key uniqueness** divides distinct complete `record_key` strings by the complete key count. The null and empty-key count appears as excluded rows.
- **Expected loss** sums `impact` times `probability` per event. Use nonnegative comparable impacts and probabilities on the same horizon expressed as decimals.
- **Maximum drawdown** starts wealth at 1, multiplies by one plus each chronological `period_return`, and reports the largest fraction lost from a prior peak. Returns must be complete for the observed window and at least minus one.

Numeric coercion failures and nonfinite inputs are missing. Each result records excluded rows. Neither currency conversion nor attribution incrementality is inferred.
