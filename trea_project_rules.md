# 备份，忽略

# Project Rules (AI Development)

## Project Position
Long-term endpoint security analysis tool. Design priority: correctness > maintainability > extensibility > UI.

## Architecture Rules
- Layered architecture: core / modules / ui / utils
- Data model is the single source of truth (SSOT)
- UI is view-only, updates via model notifications only
- Modules provide structured data, no UI logic
- No direct UI object references between Tabs

## Data & State
- Each security item is an Entry with static fields and dynamic states (hash, signature, timestamp, threat, etc.)
- All state changes must be written back to the data model

## UI Rules (Qt)
- Use Qt Model/View (QAbstractItemModel + View)
- All displayed data from model.data()
- No business logic in View or Delegate

## Forbidden
- setIndexWidget or embedding QWidget in views
- QStandardItemModel
- UI-level state storage
- Silent refactor or cross-module modification
- New frameworks or UI paradigms

## Module Extension Rules
- Follow existing data model concepts
- No private or incompatible state definitions
- Modules must not depend on other modules' UI

## Work Scope
- Only modify explicitly specified files
- No optimization/refactor beyond task scope
- If a rule must be broken, explain and wait for confirmation

## Documentation Rules

| File | Update When | Required Content |
|------|-------------|------------------|
| README.md | New feature, architecture change, module refactor | Feature list with technical details: purpose, boundaries, UI path, core module path, data structures, data flow, cross-references |
| TASKS.md | Every new task | Task ID, priority (P0/P1/P2), status (TODO/DOING/DONE), goal, acceptance criteria, affected files, progress with timestamps |

**Change Synchronization:**
- New Feature/Architecture Change/Module Refactor: Update README + Create TASK entry
- Bug Fix: Optional TASK note if significant
