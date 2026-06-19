# E2E Test Infra: Stock Terminal AI Polish

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Methodology: Category-Partition + BVA + Pairwise + Workload Testing.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | F1: Flask Server Launch | ORIGINAL_REQUEST § R2 | 5      | 5      | ✓      |
| 2 | F2: Full Terminal Compilation | ORIGINAL_REQUEST § R2 | 5      | 5      | ✓      |
| 3 | F3: External API Error Degradation | ORIGINAL_REQUEST § R2 | 5      | 5      | ✓      |
| 4 | F4: Dashboard Base Rendering | ORIGINAL_REQUEST § R1 | 5      | 5      | ✓      |
| 5 | F5: UI Missing Data Handling | ORIGINAL_REQUEST § R1 | 5      | 5      | ✓      |
| 6 | F6: Tab Navigation (8 tabs) | ORIGINAL_REQUEST § R1 | 5      | 5      | ✓      |
| 7 | F7: Interactive Controls (Buttons/Sliders) | ORIGINAL_REQUEST § R1 | 5      | 5      | ✓      |

## Test Architecture
- Test runner: `pytest`
- Test cases location: `tests/e2e/`
- Execution: `python -m pytest tests/e2e/`
- Pre-requisites: Test environment starts the Flask server and uses a headless browser (e.g., Playwright) for frontend tests, requests library for backend API testing.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Compiling highly-traded ticker and verifying dashboard | F1, F2, F4, F6, F7 | Medium |
| 2 | API rate limit during compilation gracefully degrades UI | F2, F3, F4, F5 | High |
| 3 | User navigates all 8 tabs without JS errors | F4, F6, F7 | Low |
| 4 | Generating output artifacts while inputs are partially missing | F2, F5, F7 | Medium |
| 5 | End-to-End stress compilation and navigation | F1-F7 | High |

## Coverage Thresholds
- Tier 1: ≥5 per feature
- Tier 2: ≥5 per feature (where boundaries exist)
- Tier 3: pairwise coverage of major feature interactions
- Tier 4: ≥5 realistic application scenarios
