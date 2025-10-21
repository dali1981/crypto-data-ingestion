# Corrective Action Plan — 2025-10-21

## Scope
This plan tracks high-impact fixes from the code review and organizes them into prioritized, verifiable steps with file-level targets and acceptance criteria.

## Priority P0 (same day)

- Packaging: fix dependency pins and add missing `numpy`
  - Files: `pyproject.toml:6`
  - Actions:
    - Replace unrealistic pins with widely available versions.
    - Add `numpy>=1.26` to `dependencies`.
  - Suggested deps: `matplotlib>=3.8`, `scikit-learn>=1.3`, `scipy>=1.11`, `numba>=0.60`, `plotly>=5.22`.
  - Acceptance:
    - `uv pip install -e .` succeeds in a clean environment.
    - `pytest -k import` passes for import-related tests.

- Consumers exports: remove non-existent names
  - File: `src/binance_tick_data/consumers/__init__.py:1`
  - Actions:
    - Remove `StreamingConfig`, `MetricsConfig`, `PublisherConfig` from imports and `__all__` (or add real classes in `consumer_config.py` if required).
  - Acceptance:
    - `from binance_tick_data.consumers import *` does not raise ImportError.

- Sources API/test mismatch: align imports
  - Option A (preferred, minimal risk): add alias exports
    - File: `src/binance_tick_data/sources/__init__.py`
    - Add:
      - `binance_rest_api = binance_historical_data`
      - `binance_websocket = binance_realtime_data`
  - Option B: update tests
    - File: `tests/test_imports.py:26`
    - Replace with `binance_historical_data` and `binance_realtime_data`.
  - Acceptance:
    - `pytest tests/test_imports.py::test_library_sources_import` passes.

- README corrections: advocate console scripts and fix broken link
  - File: `README.md`
  - Actions:
    - Replace direct module invocations with console scripts from `[project.scripts]`:
      - `binance-download`, `binance-download-safe`, `binance-stream`.
    - Update `INSTALLATION.md` link to `docs/QUICK_START.md` (or `docs/legacy/INSTALLATION.md`).
  - Acceptance:
    - Commands in README run as documented in a fresh environment.

## Priority P1 (1–3 days)

- Dataset/schema naming coherence via AppConfig
  - Files: `src/binance_tick_data/repository.py`, `README.md`, examples under `examples/`
  - Actions:
    - Prefer `AppConfig.database.get_table_path(...)` for fully-qualified names in v1 repo where feasible.
    - Document the canonical schema/dataset names and remove implicit concatenation like `{dataset_name}_realtime`.
    - Optionally deprecate v1 repository in docs in favor of `repository_v2`.
  - Acceptance:
    - Example queries consistently work across README and examples without manual schema edits.

- Test hygiene: mark network/integration tests
  - Files: `tests/test_library_setup.py`, `tests/test_gap_detection.py`, `tests/test_repository_connection.py`, `tests/test_repository_readonly.py`
  - Actions:
    - Add `@pytest.mark.integration` on tests that require network/database.
    - Skip by default unless `RUN_NETWORK_TESTS=1` is set (via `pytest.importorskip` pattern or `pytest.skip` on env var).
  - Acceptance:
    - `pytest -q` runs unit tests reliably without network.
    - `RUN_NETWORK_TESTS=1 pytest -m integration` runs integration tests.

- Optional dependencies for broader tool compatibility
  - File: `pyproject.toml`
  - Actions:
    - Add `[project.optional-dependencies]` mapping:
      - `dev = ["pytest", "seaborn"]`
      - `redis = ["redis>=5"]` (for event publisher backend)
  - Acceptance:
    - `pip install .[dev]` and `pip install .[redis]` succeed.

- Logging helper (polish)
  - Files: new `src/binance_tick_data/logging.py` (optional)
  - Actions:
    - Provide `configure(level="INFO")` helper to standardize formatting where desired.
  - Acceptance:
    - Importing and calling the helper adjusts root/package logger formatting.

## Priority P2 (backlog)

- Remove large binaries from VCS
  - Files: `binance_pipeline.duckdb`, `binance_gap_filler.duckdb`
  - Actions:
    - Purge from history using `git filter-repo` or `git filter-branch` outside this environment.
    - Ensure `.gitignore` continues to exclude `*.duckdb`.
  - Acceptance:
    - Repository size reduced; no DuckDB artifacts tracked.

- Normalize numeric types at ingestion
  - Files: `src/binance_tick_data/sources/rest_api.py`, `src/binance_tick_data/sources/websocket.py`
  - Actions:
    - Convert `price`/`qty` to numeric before load to reduce repeated SQL casts and improve DuckDB performance.
  - Acceptance:
    - Queries no longer rely on `CAST(... AS DECIMAL)` for basic aggregations.

- Sample dataset generator for examples/tests
  - Files: new `examples/generate_sample_data.py` or `tests/utils.py`
  - Actions:
    - Provide small synthetic dataset to exercise repository APIs offline.
  - Acceptance:
    - Examples/tests can run without network or full databases.

- Document mixed yield semantics in sources
  - Files: `docs/README.md`, `docs/QUICK_START.md`
  - Actions:
    - Explain that `aggregated_trades` yields batches, others yield rows.
  - Acceptance:
    - Docs clarify expectations for dlt pipeline behavior.

- Deprecate legacy repository in docs
  - Files: README and examples
  - Actions:
    - Recommend `repository_v2` as the default and note differences.
  - Acceptance:
    - New users are guided to `repository_v2`.

## Risk & Rollback
- Packaging changes risk dependency conflicts: keep pins moderate and test with `uv`/`pip` in clean envs.
- Export changes risk breaking external users: prefer adding aliases for backward compatibility before removing legacy names; version bump accordingly.
- README changes are low risk and reversible.

## Validation Checklist
- [ ] Clean install succeeds: `uv pip install -e .`
- [ ] Imports work: `pytest tests/test_imports.py -q`
- [ ] Unit tests pass without network: `pytest -q`
- [ ] Integration tests pass when enabled: `RUN_NETWORK_TESTS=1 pytest -m integration -q`
- [ ] README commands verified with console scripts

