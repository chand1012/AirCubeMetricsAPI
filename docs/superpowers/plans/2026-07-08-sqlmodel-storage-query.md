# SQLModel Storage Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store AirCube readings in SQLite for seven days and expose typed SQLModel-backed latest/query API responses.

**Architecture:** Add a focused storage module with the SQLModel table, engine/session helpers, insert/latest/query/cleanup operations. Keep FastAPI request handling in `aircube_metrics_api/api.py`, with `AirCubeState` delegating persistence to the storage layer while preserving Prometheus updates.

**Tech Stack:** FastAPI, SQLModel, SQLite, unittest, uv.

---

### Task 1: Storage Model And Repository

**Files:**
- Create: `aircube_metrics_api/storage.py`
- Test: `tests/test_storage.py`
- Modify: `pyproject.toml`

- [ ] Write failing storage tests for insert, latest, time-window query, daily aggregation, and seven-day cleanup.
- [ ] Add `sqlmodel>=0.0.27` dependency and refresh `uv.lock`.
- [ ] Implement `AirCubeReading`, `AirCubeAggregate`, `AirCubeStore`, and session helpers.
- [ ] Run `uv run python -m unittest discover -s tests`.

### Task 2: API Integration

**Files:**
- Modify: `aircube_metrics_api/api.py`
- Modify: `api.py`
- Test: `tests/test_api.py`

- [ ] Write failing API tests proving `/latest` reads newest DB row and `/query` returns raw SQLModel rows.
- [ ] Write failing API tests proving `/query?aggregate=day` returns averaged buckets.
- [ ] Wire `AirCubeState` to an `AirCubeStore`, initialize schema on lifespan startup, and store serial readings on update.
- [ ] Add `AIRCUBE_DATABASE_URL` with default `sqlite:///./aircube.sqlite3`.
- [ ] Run `uv run python -m unittest discover -s tests`.

### Task 3: Docker And Docs

**Files:**
- Modify: `docker-compose.yml`
- Modify: `README.md`

- [ ] Add persistent `./data:/data` volume and `AIRCUBE_DATABASE_URL=sqlite:////data/aircube.sqlite3`.
- [ ] Document retention, database config, and `/query` examples.
- [ ] Run tests and build Docker image.
