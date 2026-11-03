# Architecture

## Overview

The Financial Planning & Scenario Intelligence platform is a modular monolith designed for corporate FP&A analysis. It separates concerns cleanly to allow the difficult financial logic to be completed in Stage 2 without rebuilding the foundation.

## Design Principles

1. **Deterministic First**: All financial calculations are explicit, testable, and independent of LLMs
2. **Evidence-Based**: Every number must be traceable to source data and calculations
3. **Separation of Concerns**: Analytics layer has no API/LLM dependencies
4. **Type Safety**: Strong Pydantic schemas throughout
5. **Modular Monolith**: Simple deployment, clear module boundaries
6. **Synthetic Data**: Portfolio demonstration with realistic corporate patterns

## System Architecture

```
┌─────────────────┐
│   React Frontend │
│  (TypeScript)   │
└─────────┬───────┘
          │ HTTP/REST
┌─────────▼───────┐
│  FastAPI Backend │
├─────────────────┤
│ API Routes       │
├─────────────────┤
│ Services Layer   │
├─────────────────┤
│ Analytics Engine │  ← Deterministic Calculations
├─────────────────┤
│ Scenarios/Models │
├─────────────────┤
│ Data Layer       │  ← CSV/JSON Loading
└─────────────────┘
```

## Backend Structure

### Core (`app/core/`)
- `config.py`: Environment configuration
- `logging.py`: Structured logging setup

### Schemas (`app/schemas/`)
Pydantic models for all domain entities - financial periods, line items, metrics, variances, scenarios, analysis plans, evidence, insights.

### Data Layer (`app/data/`)
- `loader.py`: Load CSV/JSON datasets
- `repository.py`: Data access abstraction (in-memory)
- `validation.py`: Data validation logic

### Models (`app/models/`)
Financial model definitions and structures.

### Analytics (`app/analytics/`)
Core calculation engines:
- `calculations.py`: Shared financial formulas
- `variance_analyzer.py`: Budget vs actual/forecast variance
- `profitability_analyzer.py`: Margins and profitability
- `driver_analyzer.py`: Driver-based analysis
- `sensitivity_analyzer.py`: What-if sensitivity
- `cash_flow_analyzer.py`: Cash flow calculations

### Scenarios (`app/scenarios/`)
- `engine.py`: Scenario application logic (foundation)
- `assumptions.py`: Assumption validation
- `comparison.py`: Scenario comparison

### Services (`app/services/`)
Orchestration layer coordinating analytics and data.

### AI (`app/ai/`)
- `question_interpreter.py`: Parse natural language questions (interface)
- `analysis_planner.py`: Plan analysis steps (interface)
- `explanation_generator.py`: Generate explanations (interface)
- `providers/`: LLM provider abstractions (OpenAI-compatible)

### API Routes (`app/api/routes/`)
REST endpoints for health, datasets, financials, scenarios, questions.

## Frontend Structure

- `components/`: Reusable UI components (tables, charts, metrics)
- `pages/`: Page-level components (Overview, Performance, Scenarios, Ask Finance, Evidence)
- `services/`: API client
- `types/`: TypeScript type definitions
- `hooks/`: React hooks

## Data Flow

### Financial Analysis Flow
1. Load datasets from CSV/JSON
2. Validate data schemas
3. Compute deterministic metrics via analytics engines
4. Return structured results with evidence

### Scenario Flow (Foundation)
1. Load baseline from actuals/budget/forecast
2. Validate scenario assumptions
3. Apply changes in isolation (no mutation)
4. Recalculate affected metrics
5. Compare with baseline
6. Return traceable results

### AI Question Flow (Stage 2)
1. Question → QuestionInterpreter (parse intent)
2. → AnalysisPlanner (create validated plan)
3. → Deterministic Financial Model (compute results)
4. → Evidence Package (collect traceable evidence)
5. → ExplanationGenerator (LLM explains results)
6. → Structured FinancialInsight

**Critical:** LLM never computes financial numbers - only explains pre-computed deterministic results.

## Storage

- **Stage 1**: In-memory storage for analysis runs
- **No persistent database** (by design for simplicity)
- **Datasets loaded from filesystem**

## Security

- Environment variables for secrets
- No credentials in code/frontend
- Input validation via Pydantic
- No arbitrary code execution
- Configurable timeouts
- Structured errors (no raw traces)

## Technology Stack

**Backend:** Python 3.11+, FastAPI, Pydantic v2, Pandas, httpx, pytest  
**Frontend:** React 18, TypeScript, Vite, lightweight charting  
**Data:** CSV, JSON  
**No:** Kubernetes, Redis, Celery, databases, vector DBs, multi-agent frameworks

## Box 2 implementation status

The Stage 1 placeholders are now implemented (see README "What works"). Added modules:
`analytics/forecasting.py` (projection + cash model), `services/container.py` (service wiring),
`api/utils.py` (JSON sanitising), `schemas/analysis.py` (strict plan, evidence and request schemas).
Services are process-wide singletons; scenarios and evidence are held in memory.
Still deferred: persistence, authentication, live-LLM evaluation suite, frontend unit tests.
