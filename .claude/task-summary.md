# Postal Inspector Python Refactor - Task Summary

## Overview
25 tasks organized in 7 phases to refactor bash-based email scanner to Python.

## Phase Diagram

```
Phase 1: Foundation          Phase 2: Scanner       Phase 3: Transport
┌─────────────────────┐     ┌──────────────────┐   ┌─────────────────────┐
│ T001 Core Package   │────▶│ T004 Prompts     │   │ T007 IMAP Client    │
│ T002 Settings       │────▶│ T005 AI Analyzer │   │ T008 LMTP Client    │
│ T003 Verdict/Models │     └──────────────────┘   │ T009 Maildir Manager│
│ T006 Logging        │                            └─────────────────────┘
└─────────────────────┘                                      │
         │                                                   │
         └───────────────────────────────────────────────────┘
                                    │
                                    ▼
Phase 4: Services              Phase 5: Testing       Phase 6: Docker
┌──────────────────────┐      ┌──────────────────┐   ┌─────────────────┐
│ T010 Mail Processor  │      │ T015 Scanner     │   │ T019 Processor  │
│ T011 Health Check    │      │ T016 Transport   │   │ T020 Briefing   │
│ T012 Briefing Gen    │      │ T017 Config/Core │   │ T021 Compose    │
│ T013 Scheduler       │      │ T018 Integration │   │ T022 uv.lock    │
│ T014 CLI             │      └──────────────────┘   └─────────────────┘
└──────────────────────┘                                     │
                                                             ▼
                                              Phase 7: Documentation
                                              ┌─────────────────────┐
                                              │ T023 Env Config     │
                                              │ T024 Documentation  │
                                              │ T025 E2E Testing    │
                                              └─────────────────────┘
```

## Parallel Execution Groups

### Wave 1 (No Dependencies)
- **T001** Core Package Structure
- **T022** Create uv.lock File

### Wave 2 (After T001)
- **T002** Pydantic Settings
- **T003** Verdict/Models
- **T006** Logging Setup

### Wave 3 (After T002, T003)
- **T004** Prompt Templates
- **T007** IMAP Client
- **T008** LMTP Client
- **T009** Maildir Manager

### Wave 4 (After Wave 3)
- **T005** AI Analyzer (needs T004)
- **T011** Health Check

### Wave 5 (After T005, T007-T009)
- **T010** Mail Processor
- **T012** Briefing Generator
- **T013** Scheduler

### Wave 6 (After Wave 5)
- **T014** CLI Interface
- **T015** Scanner Tests
- **T016** Transport Tests
- **T017** Config Tests

### Wave 7 (After T014)
- **T018** Integration Tests
- **T019** Processor Dockerfile
- **T020** Briefing Dockerfile

### Wave 8 (After Wave 7)
- **T021** docker-compose.yml
- **T023** Env Configuration

### Wave 9 (Final)
- **T024** Documentation
- **T025** E2E Testing

## Task Complexity Summary

| Complexity | Count | Tasks |
|------------|-------|-------|
| Small | 7 | T001, T003, T006, T013, T017, T020, T022, T023 |
| Medium | 11 | T002, T004, T008, T009, T011, T014, T015, T016, T019, T021, T024 |
| Large | 7 | T005, T007, T010, T012, T018, T025 |

## Expert Assignment

| Expert Type | Tasks |
|-------------|-------|
| Python | T001-T014 (14 tasks) |
| Testing | T015-T018, T025 (5 tasks) |
| Docker | T019-T021 (3 tasks) |
| Config | T022-T024 (3 tasks) |

## Critical Path

```
T001 → T002 → T005 → T010 → T014 → T019 → T021 → T025
```

This is the longest dependency chain and determines minimum completion time.

## Key Files to Reference

| File | Purpose |
|------|---------|
| `services/ai-scanner/mail-scanner.sh` | Core logic to port |
| `services/daily-briefing/daily-briefing.sh` | Briefing logic to port |
| `services/mail-fetch/entrypoint.sh` | Fetchmail config reference |
| `CLAUDE.md` | Project rules |
| `pyproject.toml` | Dependencies (already created) |
