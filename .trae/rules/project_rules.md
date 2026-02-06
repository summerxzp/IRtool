# Project Rules (AI Development)

## Project Position
This is a long-term endpoint security analysis tool, not a demo or generic GUI app.
Design priority: correctness > maintainability > extensibility > UI appearance.

## Architecture Rules
- Strict layered architecture: core / modules / ui / utils
- UI is view-only, never the source of truth
- Data model is the single source of truth (SSOT)
- Modules provide structured data, not UI logic
- UI objects shall never be directly referenced between Tabs.

## Data & State
- Each security item is an Entry with static fields and dynamic states
- Dynamic states include: hash, signature, timestamp, threat, etc.
- All state changes must be written back to the data model
- UI must update only via model notifications

## UI Rules (Qt)
- Use Qt Model/View (QAbstractItemModel + View)
- All displayed data must come from model.data()
- No business logic in View or Delegate

## Forbidden (Strict)
- setIndexWidget or embedding QWidget in views
- QStandardItemModel
- UI-level state storage (hash/signature/time)
- Silent refactor or cross-module modification
- Introducing new frameworks or UI paradigms

## Module Extension Rules
- New modules must follow existing data model concepts
- No private or incompatible state definitions
- Modules must not depend on other modules’ UI

## Work Scope
- Only modify explicitly specified files
- Do not optimize or refactor beyond task scope
- If a rule must be broken, explain and wait for confirmation
