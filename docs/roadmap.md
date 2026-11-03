# Roadmap

## Project Phases

### Stage 1: Foundation (Current Phase) ✅
**Goal:** Establish architecture, data model, schemas, and core foundations

**Completed:**
- [x] Repository structure
- [x] Documentation framework
- [x] Synthetic datasets (Asteron Group)
- [x] Financial model specification
- [x] Domain schemas (Pydantic)
- [x] Analytics module structure
- [x] Scenario engine interfaces
- [x] AI provider interfaces
- [x] API route structure
- [x] Frontend shell
- [x] Initial tests
- [x] Configuration and security foundations

### Stage 2: Core Implementation (Stronger Model) 🔄
**Goal:** Complete the financial engine and AI capabilities

**Planned:**
- [ ] **Financial Engine**
  - [ ] Complete variance bridge analysis
  - [ ] Revenue/expense decomposition
  - [ ] Period-over-period comparisons
  - [ ] Department rollups
  - [ ] Full reconciliation logic

- [ ] **Scenario Engine**
  - [ ] Full assumption application
  - [ ] Dependency resolution
  - [ ] Automatic recalculation of affected metrics
  - [ ] Cash flow impact modeling
  - [ ] Scenario comparison with detailed deltas
  - [ ] Sensitivity analysis

- [ ] **Driver-Based Forecasting**
  - [ ] Implement revenue models
  - [ ] Compensation modeling
  - [ ] Driver propagation
  - [ ] Forecast vs actual tracking

- [ ] **AI Pipeline**
  - [ ] Question interpreter implementation
  - [ ] Analysis planner with validation
  - [ ] Evidence package generation
  - [ ] Grounded explanation generator
  - [ ] End-to-end question answering
  - [ ] Prompt engineering and grounding

- [ ] **Cash Flow**
  - [ ] Full cash flow projection
  - [ ] Working capital modeling
  - [ ] Collection/payment timing
  - [ ] Liquidity analysis

- [ ] **API Completion**
  - [ ] Fully functional endpoints
  - [ ] Proper error handling
  - [ ] Request/response validation
  - [ ] Integration tests

- [ ] **Frontend Enhancement**
  - [ ] Data visualization with charts
  - [ ] Interactive scenario builder
  - [ ] AI question interface
  - [ ] Evidence display
  - [ ] Responsive improvements

- [ ] **Testing & Evaluation**
  - [ ] Comprehensive unit tests
  - [ ] Integration tests
  - [ ] Scenario tests
  - [ ] AI grounding evaluation
  - [ ] Financial accuracy tests

### Stage 3: Polish & Enhancement (Future) 💡
**Goal:** Production-quality improvements (if extended)

**Ideas:**
- [ ] Data export (PDF, Excel)
- [ ] Additional chart types
- [ ] More sophisticated scenarios
- [ ] Comparison across multiple periods
- [ ] Custom metrics
- [ ] Dark mode
- [ ] Additional visualizations

## Priorities

**Immediate (Stage 2 Start):**
1. Complete core financial calculations with full reconciliation
2. Implement scenario engine recalculation logic
3. Build evidence package generation
4. Wire up basic question answering pipeline

**Key Principles:**
- Correctness over features
- Deterministic calculations first
- Evidence before explanations
- Test financial logic thoroughly
- Keep it simple and maintainable

## Dependencies

Stage 2 will need:
- Stronger reasoning model for complex financial logic
- More computation time for thorough implementation
- Focus on correctness and edge cases

## Success Metrics

**Stage 1 (Done when):**
- [x] All documents created
- [x] Structure in place
- [x] Schemas defined
- [x] Tests pass for implemented parts
- [x] Frontend builds
- [x] Backend starts

**Stage 2 (Done when):**
- [ ] Can answer "Why is operating expense above budget?" correctly
- [ ] Scenario modeling works end-to-end
- [ ] All financial calculations reconciled
- [ ] AI explanations grounded in evidence
- [ ] Comprehensive tests pass
- [ ] End-to-end workflows functional

## Notes

- This is a portfolio project, not a commercial product
- Focus on demonstrating solid engineering practices
- Financial accuracy is critical
- Architecture should support extension
- Keep Stage 1 boundaries clear
