# Documentation Organization Plan

**Date:** 2025-11-07
**Status:** Proposed
**Purpose:** Organize scattered MD files into proper directories with clear categorization

---

## Current Problem

**20+ markdown files scattered in root directory**, making it difficult to:
- Find relevant documentation
- Understand what's current vs. outdated
- Maintain documentation consistency

---

## Proposed Structure

### 1. **docs/** - User-Facing Documentation
**Purpose:** End-user guides, tutorials, and references

**Status:** ✅ Well organized, keep as-is

**Files:**
```
docs/
├── README.md                          # ✅ Documentation index
├── QUICK_START.md                     # ✅ Core platform quick start
├── API_REFERENCE.md                   # ✅ Complete API docs
├── GETTING_STARTED_STREAMING.md       # ✅ Streaming guide
├── JOBS_QUICK_START.md                # ✅ Data quality guide
├── SOLUTION_SUMMARY.md                # ✅ Architecture overview
├── DATA_QUALITY_REPORT.md             # ✅ Original analysis
├── ADAPTIVE_CHUNKING.md               # ✅ Technical explanation
├── SMART_GAP_FILLING.md               # ✅ Technical explanation
├── DOLLAR_VOLUME_SAMPLING.md          # ✅ Feature docs
├── LIQUIDITY_ANALYZER_EXPLAINED.md    # ✅ Feature docs
├── KEDRO_INTEGRATION.md               # ✅ Integration guide
├── DELTA_LAKE_SETUP.md                # ✅ Setup guide
├── DATA_ACCESS.md                     # ✅ Usage guide
└── legacy/                            # ✅ Archived old docs
    └── (historical files)
```

---

### 2. **specs/** - Technical Specifications & Plans
**Purpose:** Architecture decisions, design docs, code reviews, implementation plans

**Current Files:**
```
specs/
├── MODULAR_SYSTEM_SUMMARY.md          # ✅ Architecture spec
├── STREAMING_INTEGRATION_PLAN.md      # ✅ Design doc
├── STREAMING_IMPLEMENTATION_SUMMARY.md # ✅ Implementation summary
├── PHASE_4_COMPLETE.md                # ✅ Milestone summary
├── dollar-volume-sampling-tools.md    # ✅ Technical spec
├── rllib_specs.md                     # ✅ RLlib integration spec
├── code_review_2025-10-21.md          # ✅ Code review
├── code_review_2025-10-21_corrective_plan.md # ✅ Action plan
├── cli_modernization_plan.md          # ✅ CLI refactor plan
└── refactoring_rest_api_oop.md        # ✅ NEW - OOP refactor plan
```

**Files to ADD (from root):**
```
specs/implementations/                  # NEW subdirectory
├── IMPLEMENTATION_SUMMARY.md          # ← ROOT: General implementation
├── DAGSTER_SETUP_SUMMARY.md           # ← ROOT: Dagster implementation
├── ARCHITECTURE_UPDATE.md             # ← ROOT: Architecture changes
├── CONFIGURATION_IMPROVEMENTS.md      # ← ROOT: Config changes
└── NOTEBOOK_FIXES_SUMMARY.md          # ← ROOT: Notebook updates

specs/fixes/                           # NEW subdirectory
├── WEBSOCKET_FIX.md                   # ← ROOT: Bug fix
├── WEBSOCKET_COMPLETE_FIX.md          # ← ROOT: Bug fix complete
├── LOGGING_UPDATE.md                  # ← ROOT: Feature update
├── CRASH_RECOVERY_FIX.md              # ← ROOT: Bug fix
├── INCREMENTAL_WRITES.md              # ← ROOT: Feature update
├── ROW_COUNTING_FIX.md                # ← ROOT: Bug fix
├── QUICK_START_FIXED.md               # ← ROOT: Doc fix
├── NOTEBOOK_FIXES.md                  # ← ROOT: Bug fixes
└── SPREAD_ESTIMATION_NOTE.md          # ← ROOT: Technical note

specs/investigations/                  # NEW subdirectory
├── OCT10_CRASH_INVESTIGATION_REPORT.md # ← ROOT: Post-mortem
├── OCT10_CRASH_ROOT_CAUSE_ANALYSIS.md  # ← ROOT: Root cause
└── TIME_METRICS_ENHANCEMENT.md         # ← ROOT: Analysis/proposal
```

---

### 3. **Root Directory** - Essential Project Files Only
**Purpose:** Project entry points and essential navigation

**Keep in Root:**
```
/
├── README.md                          # ✅ Main project README
├── CLAUDE.md                          # ✅ Claude Code instructions
├── PROJECT_STRUCTURE.md               # ❓ Move to docs/?
├── DIRECTORY_ORGANIZATION.md          # ❌ REMOVE (superseded by this doc)
├── README_STREAMING.md                # ❓ Merge into main README or move to docs/
├── REPOSITORY_USAGE.md                # ❓ Move to docs/DATA_ACCESS.md (merge)?
├── DOLLAR_VOLUME_BARS_SUMMARY.md      # ❓ Move to docs/DOLLAR_VOLUME_SAMPLING.md (merge)?
└── DAGSTER_QUICK_REFERENCE.md         # ❓ Move to dagster_pipeline/ directory?
```

---

### 4. **Other Component READMEs** - Keep As-Is
**Purpose:** Component-specific documentation stays with components

```
examples/README.md                     # ✅ Examples guide
examples/ANALYSIS_README.md            # ✅ Analysis examples
jobs/README.md                         # ✅ Jobs technical docs
notebooks/README.md                    # ✅ Notebooks guide
dagster_pipeline/README.md             # ✅ Dagster docs
dagster_pipeline/QUICK_START.md        # ✅ Dagster quick start
```

---

## Detailed Actions

### Action 1: Create New Subdirectories

```bash
mkdir -p specs/implementations
mkdir -p specs/fixes
mkdir -p specs/investigations
```

### Action 2: Move Files to specs/

**Move to `specs/implementations/`:**
```bash
mv IMPLEMENTATION_SUMMARY.md specs/implementations/
mv DAGSTER_SETUP_SUMMARY.md specs/implementations/
mv ARCHITECTURE_UPDATE.md specs/implementations/
mv CONFIGURATION_IMPROVEMENTS.md specs/implementations/
mv NOTEBOOK_FIXES_SUMMARY.md specs/implementations/
```

**Move to `specs/fixes/`:**
```bash
mv WEBSOCKET_FIX.md specs/fixes/
mv WEBSOCKET_COMPLETE_FIX.md specs/fixes/
mv LOGGING_UPDATE.md specs/fixes/
mv CRASH_RECOVERY_FIX.md specs/fixes/
mv INCREMENTAL_WRITES.md specs/fixes/
mv ROW_COUNTING_FIX.md specs/fixes/
mv QUICK_START_FIXED.md specs/fixes/
mv NOTEBOOK_FIXES.md specs/fixes/
mv SPREAD_ESTIMATION_NOTE.md specs/fixes/
```

**Move to `specs/investigations/`:**
```bash
mv OCT10_CRASH_INVESTIGATION_REPORT.md specs/investigations/
mv OCT10_CRASH_ROOT_CAUSE_ANALYSIS.md specs/investigations/
mv TIME_METRICS_ENHANCEMENT.md specs/investigations/
```

### Action 3: Consolidate or Move Root Files

**Option A: Merge into existing docs**
```bash
# Merge DOLLAR_VOLUME_BARS_SUMMARY.md → docs/DOLLAR_VOLUME_SAMPLING.md
# Merge REPOSITORY_USAGE.md → docs/DATA_ACCESS.md
# Delete DIRECTORY_ORGANIZATION.md (superseded)
```

**Option B: Move to docs/**
```bash
mv PROJECT_STRUCTURE.md docs/
mv README_STREAMING.md docs/
mv REPOSITORY_USAGE.md docs/
mv DOLLAR_VOLUME_BARS_SUMMARY.md docs/
mv DAGSTER_QUICK_REFERENCE.md dagster_pipeline/
```

**Recommendation:** Option A (merge) - reduces redundancy

### Action 4: Update References in README.md

Update main README.md to reference organized docs:

**Before:**
```markdown
See [DAGSTER_SETUP_SUMMARY.md](DAGSTER_SETUP_SUMMARY.md) for complete details.
```

**After:**
```markdown
See [Dagster Setup](specs/implementations/DAGSTER_SETUP_SUMMARY.md) for complete details.
```

### Action 5: Create Index Files

**Create `specs/README.md`:**
```markdown
# Technical Specifications

## Implementation Summaries
- [General Implementation](implementations/IMPLEMENTATION_SUMMARY.md)
- [Dagster Setup](implementations/DAGSTER_SETUP_SUMMARY.md)
- [Architecture Updates](implementations/ARCHITECTURE_UPDATE.md)
- [Configuration Improvements](implementations/CONFIGURATION_IMPROVEMENTS.md)
- [Notebook Fixes](implementations/NOTEBOOK_FIXES_SUMMARY.md)

## Design Documents
- [Streaming Integration Plan](STREAMING_INTEGRATION_PLAN.md)
- [RLlib Integration Spec](rllib_specs.md)
- [CLI Modernization Plan](cli_modernization_plan.md)
- [OOP Refactoring Plan](refactoring_rest_api_oop.md)

## Bug Fixes & Updates
- [WebSocket Fixes](fixes/)
- [Crash Recovery Fix](fixes/CRASH_RECOVERY_FIX.md)
- [Logging Update](fixes/LOGGING_UPDATE.md)

## Investigations
- [Oct 10 Crash Investigation](investigations/OCT10_CRASH_INVESTIGATION_REPORT.md)
- [Oct 10 Root Cause Analysis](investigations/OCT10_CRASH_ROOT_CAUSE_ANALYSIS.md)

## Code Reviews
- [2025-10-21 Code Review](code_review_2025-10-21.md)
- [Corrective Action Plan](code_review_2025-10-21_corrective_plan.md)
```

---

## Documentation Status Review

### Current Implementation Status

| Feature | Status | Documentation | Needs Update? |
|---------|--------|---------------|---------------|
| **Historical data ingestion** | ✅ Implemented | docs/QUICK_START.md | ✅ Current |
| **Real-time streaming** | ✅ Implemented | docs/GETTING_STARTED_STREAMING.md | ✅ Current |
| **Data quality jobs** | ✅ Implemented | docs/JOBS_QUICK_START.md | ✅ Current |
| **Dollar volume sampling** | ✅ Implemented | docs/DOLLAR_VOLUME_SAMPLING.md | ✅ Current |
| **Dagster pipeline** | ✅ Implemented | dagster_pipeline/README.md | ✅ Current |
| **Repository pattern** | ✅ Implemented (v2) | docs/API_REFERENCE.md | ⚠️ Needs v2 update |
| **CLI modernization** | ❓ Partial? | README.md | ⚠️ Check status |
| **Adaptive chunking** | ✅ Implemented | docs/ADAPTIVE_CHUNKING.md | ✅ Current |
| **Smart gap filling** | ✅ Implemented | docs/SMART_GAP_FILLING.md | ✅ Current |
| **Liquidity analyzer** | ✅ Implemented | docs/LIQUIDITY_ANALYZER_EXPLAINED.md | ✅ Current |
| **OOP refactoring** | ❌ Proposed | specs/refactoring_rest_api_oop.md | ✅ Reflects status |

### Documentation Accuracy Checks Needed

1. **docs/API_REFERENCE.md**
   - ❓ Does it reference `repository_v2.BinanceDataRepository`?
   - ❓ Are all v2 methods documented?

2. **README.md**
   - ❓ Is CLI section accurate (unified `binance` command)?
   - ❓ Are database paths correct (`binance_pipeline.duckdb`)?

3. **specs/cli_modernization_plan.md**
   - ❓ Was this implemented?
   - ❓ Needs status update: "Status: Proposed" → "Status: Implemented"?

4. **specs/STREAMING_IMPLEMENTATION_SUMMARY.md**
   - ❓ Is implementation complete?
   - ❓ Status reflects reality?

---

## Final Directory Structure

```
/
├── README.md                          # Main entry point
├── CLAUDE.md                          # Claude instructions
│
├── docs/                              # User-facing documentation
│   ├── README.md                      # Documentation index
│   ├── QUICK_START.md
│   ├── API_REFERENCE.md
│   ├── GETTING_STARTED_STREAMING.md
│   ├── JOBS_QUICK_START.md
│   ├── SOLUTION_SUMMARY.md
│   ├── DATA_QUALITY_REPORT.md
│   ├── ADAPTIVE_CHUNKING.md
│   ├── SMART_GAP_FILLING.md
│   ├── DOLLAR_VOLUME_SAMPLING.md
│   ├── LIQUIDITY_ANALYZER_EXPLAINED.md
│   ├── KEDRO_INTEGRATION.md
│   ├── DELTA_LAKE_SETUP.md
│   ├── DATA_ACCESS.md
│   └── legacy/                        # Archived docs
│
├── specs/                             # Technical specs & plans
│   ├── README.md                      # Specs index (NEW)
│   ├── MODULAR_SYSTEM_SUMMARY.md
│   ├── STREAMING_INTEGRATION_PLAN.md
│   ├── STREAMING_IMPLEMENTATION_SUMMARY.md
│   ├── PHASE_4_COMPLETE.md
│   ├── dollar-volume-sampling-tools.md
│   ├── rllib_specs.md
│   ├── code_review_2025-10-21.md
│   ├── code_review_2025-10-21_corrective_plan.md
│   ├── cli_modernization_plan.md
│   ├── refactoring_rest_api_oop.md
│   ├── documentation_organization_plan.md (THIS FILE)
│   ├── implementations/               # Implementation summaries (NEW)
│   │   ├── IMPLEMENTATION_SUMMARY.md
│   │   ├── DAGSTER_SETUP_SUMMARY.md
│   │   ├── ARCHITECTURE_UPDATE.md
│   │   ├── CONFIGURATION_IMPROVEMENTS.md
│   │   └── NOTEBOOK_FIXES_SUMMARY.md
│   ├── fixes/                         # Bug fixes & updates (NEW)
│   │   ├── WEBSOCKET_FIX.md
│   │   ├── WEBSOCKET_COMPLETE_FIX.md
│   │   ├── LOGGING_UPDATE.md
│   │   ├── CRASH_RECOVERY_FIX.md
│   │   ├── INCREMENTAL_WRITES.md
│   │   ├── ROW_COUNTING_FIX.md
│   │   ├── QUICK_START_FIXED.md
│   │   ├── NOTEBOOK_FIXES.md
│   │   └── SPREAD_ESTIMATION_NOTE.md
│   └── investigations/                # Post-mortems & analyses (NEW)
│       ├── OCT10_CRASH_INVESTIGATION_REPORT.md
│       ├── OCT10_CRASH_ROOT_CAUSE_ANALYSIS.md
│       └── TIME_METRICS_ENHANCEMENT.md
│
├── examples/                          # Example code
│   ├── README.md
│   └── ANALYSIS_README.md
│
├── jobs/                              # Data quality jobs
│   └── README.md
│
├── notebooks/                         # Jupyter notebooks
│   └── README.md
│
└── dagster_pipeline/                  # Dagster orchestration
    ├── README.md
    └── QUICK_START.md
```

---

## Benefits of This Organization

### 1. Clear Separation of Concerns
- **docs/**: "How do I use this?" (user-facing)
- **specs/**: "How was this built?" (technical/historical)
- **Root**: Essential project files only

### 2. Easier Navigation
- New users start in `docs/`
- Developers check `specs/` for technical details
- Subdirectories group related content

### 3. Better Discoverability
- Index files (`docs/README.md`, `specs/README.md`)
- Clear naming conventions
- Logical grouping

### 4. Maintainability
- Easy to add new docs in correct location
- Clear where to archive old content
- Reduced root directory clutter

### 5. Version Control
- Easier to see what changed (organized by category)
- Better commit messages ("specs/fixes: add websocket fix")
- Clearer history

---

## Implementation Checklist

- [x] Create `specs/refactoring_rest_api_oop.md`
- [ ] Create new subdirectories:
  - [ ] `specs/implementations/`
  - [ ] `specs/fixes/`
  - [ ] `specs/investigations/`
- [ ] Move files from root to `specs/`:
  - [ ] Implementation summaries → `specs/implementations/`
  - [ ] Bug fixes → `specs/fixes/`
  - [ ] Investigations → `specs/investigations/`
- [ ] Create `specs/README.md` index
- [ ] Update main `README.md` references
- [ ] Verify documentation accuracy:
  - [ ] Check `docs/API_REFERENCE.md` for v2 methods
  - [ ] Check CLI documentation status
  - [ ] Update implementation status in specs
- [ ] Remove/merge redundant files:
  - [ ] Delete `DIRECTORY_ORGANIZATION.md`
  - [ ] Consider merging `DOLLAR_VOLUME_BARS_SUMMARY.md` → `docs/DOLLAR_VOLUME_SAMPLING.md`
  - [ ] Consider merging `REPOSITORY_USAGE.md` → `docs/DATA_ACCESS.md`

---

## Next Steps

1. **Review this plan** with team/user
2. **Execute file moves** (git mv for history preservation)
3. **Update references** in README and other files
4. **Create index files** (`specs/README.md`)
5. **Verify all links** work after moves
6. **Update documentation status** in specs where needed
7. **Commit with clear message**: "docs: organize documentation structure (specs, implementations, fixes, investigations)"

---

**Status:** Awaiting approval to proceed with reorganization.