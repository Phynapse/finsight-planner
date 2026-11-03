# Data Model

## Overview

This document describes the datasets, schemas, and relationships for the Financial Planning & Scenario Intelligence platform.

## Synthetic Client: Asteron Group

**Profile:**
- Medium-sized multinational business
- Multiple business units and operating departments
- Historical actuals spanning 2024-01 to 2026-09 (36-month window, but only 13 sampled months are present; many units report only in 2024-01)
- Realistic FP&A patterns with intentional variances

**Departments (representative):**
- Sales & Marketing
- Engineering & Product
- Customer Success
- Finance & Admin
- Operations
- General & Administrative

**Business Units:**
- North America
- Europe
- Asia Pacific

## Datasets

### 1. actuals.csv
**Purpose:** Historical recorded financial performance

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| period | string (YYYY-MM) | Reporting period |
| business_unit | string | Business unit name |
| department | string | Department name |
| financial_line | string | Line item (revenue, cogs, compensation_expense, etc.) |
| amount | float | Amount in USD (expenses stored as positive) |
| currency | string | Currency code (USD) |
| data_status | string | Status (actual, restated) |

**Financial Lines:**
- revenue
- cogs
- compensation_expense
- marketing_expense
- technology_expense
- facilities_expense
- other_operating_expense

### 2. budget.csv
**Purpose:** Approved financial plan

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| period | string (YYYY-MM) | Reporting period |
| business_unit | string | Business unit name |
| department | string | Department name |
| financial_line | string | Line item |
| budget_amount | float | Budgeted amount in USD |
| currency | string | Currency code (USD) |
| assumption_id | string | Reference to assumption (optional) |

### 3. forecast.csv
**Purpose:** Current estimate of future financial performance

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| period | string (YYYY-MM) | Reporting period |
| business_unit | string | Business unit name |
| department | string | Department name |
| financial_line | string | Line item |
| forecast_amount | float | Forecasted amount in USD |
| forecast_version | string | Forecast version (e.g., v1.0) |
| currency | string | Currency code (USD) |

**Note:** Historical periods may have forecast values; distinguish by context. Future periods are forecasts.

### 4. financial_drivers.csv
**Purpose:** Explicit assumptions and drivers for financial models

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| period | string (YYYY-MM) | Reporting period |
| business_unit | string | Business unit name |
| department | string | Department name |
| driver_name | string | Driver name |
| driver_value | float | Driver value |
| driver_unit | string | Unit of measure |
| scenario | string | Scenario (baseline, upside, downside) |
| assumption_source | string | Source of assumption |

**Key Drivers:**
- customer_count
- new_customers
- churn_rate
- average_revenue_per_customer
- headcount
- average_compensation
- marketing_spend
- cost_per_acquisition
- collection_period_days

### 5. cash_flow.csv
**Purpose:** Cash flow and liquidity planning

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| period | string (YYYY-MM) | Reporting period |
| business_unit | string | Business unit name |
| opening_cash | float | Opening cash balance |
| customer_collections | float | Cash collected from customers |
| operating_payments | float | Operating expense payments |
| payroll_payments | float | Payroll payments |
| capital_expenditure | float | CapEx |
| debt_repayments | float | Debt repayments |
| other_cash_movements | float | Other cash flows |
| ending_cash | float | Ending cash balance |

**Validation:** `ending_cash = opening_cash + customer_collections - operating_payments - payroll_payments - capital_expenditure - debt_repayments + other_cash_movements` (with sign conventions)

### 6. scenarios.json
**Purpose:** Scenario definitions with explicit assumptions

**Structure:**
```json
{
  "scenarios": [
    {
      "scenario_id": "baseline",
      "name": "Baseline",
      "description": "...",
      "base_scenario": null,
      "assumptions": [
        {
          "assumption_name": "...",
          "target": {"business_unit": "...", "department": "...", "financial_line": "..."},
          "change_type": "percentage|absolute",
          "change_value": 0.0,
          "driver": "...",
          "description": "..."
        }
      ],
      "metadata": {}
    }
  ]
}
```

## Domain Schemas (Pydantic)

### Core Entities

**FinancialPeriod**
- period (str, YYYY-MM format)
- year, month

**FinancialLineItem**
- period, business_unit, department, financial_line
- amount, currency, source_type (actual|budget|forecast)

**FinancialMetric**
- metric_name, value, unit
- period, source, calculation_description

**VarianceResult**
- metric, actual_or_forecast_value, budget_value
- absolute_variance, percentage_variance (optional)
- favourable_unfavourable (optional), caveats (list)

**ForecastAssumption**
- assumption_name, value, unit
- period, source, scenario

**ScenarioDefinition**
- scenario_id, name, description
- assumptions (list), base_scenario (optional)
- metadata (dict)

**ScenarioResult**
- scenario_id, financial_outputs (dict)
- comparison_against_baseline (dict)
- changed_assumptions (list), caveats (list)

**AnalysisPlan**
- analysis_type, metric, period
- comparison_period (optional)
- dimensions (list), filters (dict)
- required_datasets (list), reasoning_goal

**EvidenceItem**
- evidence_id, metric, value, comparison_value
- absolute_change, percentage_change (optional)
- period, dimension
- source_dataset, calculation_description

**FinancialInsight**
- question, answer
- key_findings (list), evidence_references (list)
- recommendations (list), caveats (list)

## Relationships

- Actuals/Budget/Forecast share same dimensional keys (period, BU, department, financial_line)
- Financial drivers provide assumptions for models
- Cash flow is period-based, may roll up across BUs
- Scenarios reference targets in actuals/budget/forecast structure

## Data Integrity

- Periods in YYYY-MM format
- Consistent currency (USD)
- Valid financial line names
- Non-negative periods
- Cash flow reconciliation where possible
- No duplicate keys without reason
