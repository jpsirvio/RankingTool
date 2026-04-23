# Ranking Tool

A desktop application for ranking a list of items through pairwise comparisons. Instead of sorting a list by hand, the app presents two items at a time and asks you to pick the better one. A rating algorithm builds a ranked order from your choices.

Typical use cases: ranking a band's discography, comparing films, evaluating options, or any situation where direct head-to-head comparison is easier than assigning scores.

---

## Table of Contents

- [How the App Works](#how-the-app-works)
- [Workflow Overview](#workflow-overview)
- [Screen-by-Screen Guide](#screen-by-screen-guide)
  - [Project Browser](#1-project-browser)
  - [List Manager](#2-list-manager)
  - [Tier Assignment](#3-tier-assignment)
  - [Ranking](#4-ranking)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Building and Running](#building-and-running)
  - [Linux — End Users](#linux--end-users)
  - [Linux — Building from Source](#linux--building-from-source)
  - [Windows — End Users](#windows--end-users)
  - [Windows — Building from Source](#windows--building-from-source)
- [Project File Format](#project-file-format)
- [Technical Documentation](#technical-documentation)
  - [Repository Structure](#repository-structure)
  - [Architecture](#architecture)
  - [Ranking Algorithm](#ranking-algorithm)
  - [Tier System](#tier-system)
  - [Undo System](#undo-system)
  - [Pair Deduplication](#pair-deduplication)

---

## How the App Works

Ranking many items by hand is difficult because human judgment is inconsistent across large sets. The app solves this by breaking the problem into many small decisions — which of these two things is better? — and using a rating algorithm to build a global order from those answers.

To keep the number of comparisons manageable, items are first sorted into broad **tiers** (e.g. S, A, B, C, D, E). Comparisons then happen within each tier by default, so an S-tier item is never wastefully compared against a D-tier item. The algorithm also tracks which pairs have already been compared and never presents the same pair twice.

A **confidence score** tracks how settled the ranking is. Once the top items have been stable across many comparisons the app signals that ranking is complete, though you can always continue for more precision.

---

## Workflow Overview

```
New list → List Manager → Tier Assignment → Ranking
                                               ↕
                                        auto-saved to
                                        projects/<uuid>.json
```

1. **Create a list** — type or paste items, configure tier names and colors.
2. **Assign tiers** — place each item into a broad quality tier one by one, then adjust with drag-and-drop.
3. **Rank** — compare pairs within tiers. The live ranking updates after every choice.
4. **Resume any time** — the project is auto-saved after every comparison. Open it from the Project Browser to continue where you left off.

---

## Screen-by-Screen Guide

### 1. Project Browser

The opening screen. Lists all saved projects sorted by most recently modified.

Each project is shown as **List Name — YYYY-MM-DD HH:MM:SS**.

| Action | How |
|--------|-----|
| Open a project | Double-click or select and click **Open selected** |
| Create a new list | Click **New list** |
| Delete a project | Select it and click **Delete** |

Projects are stored in the `projects/` folder next to the application. The folder is created automatically on first run.

---

### 2. List Manager

Create or review a list and configure its tiers before starting.

**Items panel (left)**

- Type a single item name and press Enter or click **Add**.
- Paste multiple items into the bulk import box separated by newlines or semicolons, then click **Import from text**.
- Click **Import .txt file** to load a semicolon-separated or newline-separated text file.
- Drag rows in the list to reorder. Select and click **Remove selected** to delete.

**Tier configuration panel (right)**

Tiers define the broad quality groups. Items within the same tier are compared against each other during ranking.

- The default tier set is **S, A, B, C, D, E** (best to worst).
- Click **Add Tier** to add a new tier at the bottom.
- Click **Rename** on any tier row to rename it.
- Click **Colors** to open the color picker for that tier — choose background and text color from the swatch palette or enter a hex code directly.
- Use **↑** and **↓** to reorder tiers.
- Click **✕** to remove a tier.
- Click **Reset to defaults** to restore S, A, B, C, D, E with their default colors.

When you are ready, click **Continue to Tier Assignment →**. The project file is created at this point.

---

### 3. Tier Assignment

Assign every item to one of the tiers you configured.

**Flash-card mode** (top half)

Items are presented one at a time. Click a tier button to assign the current item and advance to the next. Click **Skip** to cycle the current item to the end of the queue.

**Drag board** (bottom half)

All assigned items appear as colored pills inside their tier bucket. Drag a pill to a different bucket to reassign it at any time — this works even after you have finished the flash-card queue.

If you click **Start Ranking →** with items still unassigned, they are automatically placed in the last tier so nothing is excluded from comparisons.

---

### 4. Ranking

The main comparison screen.

**Comparison cards**

Two items are shown side by side. Click the card for the item you prefer, or use keyboard shortcuts. The ranking list updates immediately after each choice.

- **Left card** — left item wins
- **Draw** button (center) — neither is clearly better
- **Right card** — right item wins

**Controls**

| Button | Keyboard | Action |
|--------|----------|--------|
| — | A | Left item wins |
| — | D | Right item wins |
| Draw | S | Draw / tie |
| ↩ Undo | Z | Undo the last comparison and re-open that pair |
| Skip | Space | Skip this pair for now (not recorded as ranked) |
| Reset | — | Wipe all comparison history and start over |

**Cross-tier comparisons**

By default, only items in the same tier are compared. Tick **Allow cross-tier comparisons** to compare items across tiers — useful for fine-tuning the boundary between tiers.

**Results list**

The ranked list below the cards has two sort modes toggled by buttons above it:

- **Tier → Score** (default) — items grouped under tier headers, sorted by score within each tier.
- **Score only** — flat global list ordered purely by score, with tier labels shown in brackets.

**Progress and confidence**

The progress bar shows how many unique pairs have been ranked out of the total possible within-tier pairs. The confidence percentage combines rating convergence (sigma) and ranking stability — once it reaches 100% the ranking is unlikely to change further.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| A | Left item wins |
| D | Right item wins |
| S | Draw |
| Z | Undo last comparison |
| Space | Skip current pair |

Shortcuts are active whenever the Ranking screen has focus.

---

## Building and Running

The app is distributed as a self-contained binary built with PyInstaller. End users need no Python installation.

### Linux — End Users

Unzip the distributed `RankingTool/` folder and run:

```bash
chmod +x launch_linux.sh    # once only
./launch_linux.sh
```

Or run the binary directly:

```bash
./RankingTool
```

If the app fails to start with an error about missing libraries, install the required system Qt libraries:

```bash
sudo apt install libxcb-xinerama0 libxcb-cursor0 libgl1
```

`launch_linux.sh` detects missing libraries automatically and prints the exact command to run.

---

### Linux — Building from Source

Requirements on the **build machine** only (not needed by end users):

```bash
sudo apt install python3 python3-venv python3-pip
sudo apt install libxcb-xinerama0 libxcb-cursor0 libgl1
```

Then:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

This creates a `build_venv/`, installs PyQt5 and PyInstaller into it, and produces:

```
dist/RankingTool/
├── RankingTool          ← self-contained binary
├── launch_linux.sh      ← end-user launcher
└── _internal/           ← PyInstaller support files
```

Distribute the entire `dist/RankingTool/` folder. End users run `launch_linux.sh`.

---

### Windows — End Users

Unzip the distributed `RankingTool\` folder and either:

- Double-click **`launch_windows.bat`**, or
- Double-click **`RankingTool.exe`** directly.

No installation required.

---

### Windows — Building from Source

Requirements on the **build machine** only:

- Python 3.8 or newer from [python.org](https://www.python.org/downloads/)
- During installation, tick **"Add Python to PATH"**

Then double-click **`build_windows.bat`**, or run it from a terminal:

```bat
build_windows.bat
```

This creates a `build_venv\`, installs PyQt5 and PyInstaller, and produces:

```
dist\RankingTool\
├── RankingTool.exe      ← self-contained binary
├── launch_windows.bat   ← end-user launcher
└── _internal\           ← PyInstaller support files
```

Distribute the entire `dist\RankingTool\` folder.

> **Note:** PyInstaller builds are platform-specific. A Windows build must be produced on a Windows machine; a Linux build on Linux. There is no cross-compilation.

---

## Project File Format

Projects are stored as JSON files in the `projects/` folder next to the application binary. Filenames are UUIDs — the human-readable name is stored inside the file.

```jsonc
{
  "version": 3,
  "list_name": "Iron Maiden Discography",
  "created_at": "2026-04-22 14:35:07",

  // The ordered list of item names
  "values": ["Powerslave", "Piece of Mind", "The Number of the Beast", "..."],

  // Tier names and their display colors
  "tier_config": {
    "tiers": ["S", "A", "B", "C", "D", "E"],
    "colors": {
      "S": ["#b91c1c", "#ffffff"],
      "A": ["#c2410c", "#ffffff"]
      // ...
    }
  },

  // Which tier each item is assigned to (null = unassigned)
  "tier_assignments": {
    "Powerslave": "S",
    "Piece of Mind": "A"
    // ...
  },

  // Whether cross-tier comparisons are enabled
  "allow_cross_tier": false,

  // TrueSkill-style rating for each item
  "ratings": {
    "Powerslave": { "mu": 28.4, "sigma": 7.1 }
    // ...
  },

  // Full comparison history: [item_a, item_b, result]
  // result is one of: "A", "B", "DRAW", "SKIP"
  "history": [
    ["Powerslave", "Piece of Mind", "A"],
    ["The Number of the Beast", "Killers", "B"]
  ],

  // Canonical sorted pair keys for all non-SKIP comparisons
  // Used to prevent the same pair being presented twice
  "ranked_pairs": [
    "Piece of Mind|Powerslave",
    "Killers|The Number of the Beast"
  ]
}
```

**Backwards compatibility:** version 2 files (without `ranked_pairs`) are loaded correctly — the engine reconstructs the set from the history on load.

---

## Technical Documentation

### Repository Structure

```
RankingTool/
├── qt_app.py            # PyQt5 UI — all screens and widgets
├── ranking_engine.py    # Core algorithm — ratings, pair selection, serialisation
├── requirements.txt     # Python dependencies (PyQt5)
├── RankingTool.spec     # PyInstaller build configuration
├── build_linux.sh       # Developer build script for Linux
├── build_windows.bat    # Developer build script for Windows
├── launch_linux.sh      # End-user launcher for Linux (pre-built binary)
├── launch_windows.bat   # End-user launcher for Windows (pre-built binary)
└── projects/            # Auto-created; stores project JSON files
```

---

### Architecture

The application is split into two modules with a strict separation of concerns:

**`ranking_engine.py`** — pure logic, no UI. Knows nothing about PyQt5. Can be imported and tested independently.

**`qt_app.py`** — presentation layer only. All state lives in the engine; the UI reads from it and calls its methods.

#### Screen flow

```
MainWindow (QMainWindow)
└── QStackedWidget
    ├── [0] ProjectBrowserScreen   open / delete projects
    ├── [1] ListManagerScreen      define items and tiers
    ├── [2] TierAssignmentScreen   place items into tiers
    └── [3] RankingScreen          pairwise comparisons
```

Navigation is driven by PyQt5 signals emitted from each screen. `MainWindow` wires all signal connections in `__init__` and owns the active `RankingEngine` instance.

#### Key classes in `qt_app.py`

| Class | Responsibility |
|-------|---------------|
| `TierColorDialog` | Modal dialog — swatch grid + hex inputs for per-tier colors |
| `TierRowWidget` | One row in the tier editor: pill preview + Rename / Colors / ↑↓ / ✕ |
| `DraggableItemLabel` | Draggable pill in the tier assignment board |
| `TierBucket` | Drop target for one tier in the drag board |
| `ProjectBrowserScreen` | Lists projects, opens or deletes them |
| `ListManagerScreen` | Item editor and tier configurator |
| `TierAssignmentScreen` | Flash-card assignment + drag board |
| `RankingScreen` | Comparison cards, results list, controls |
| `MainWindow` | Top-level window, navigation, auto-save wiring |

---

### Ranking Algorithm

The engine uses a simplified **TrueSkill-style** Bayesian rating system. Each item has two parameters:

- **μ (mu)** — the estimated skill / quality score. Higher is better.
- **σ (sigma)** — uncertainty. Starts high (8.333) and decreases with each comparison.

When item A beats item B in a comparison:

```
diff     = μ_A − μ_B
c        = √(σ_A² + σ_B²)
expected = 1 / (1 + exp(−diff / c))   # probability A was expected to win
score    = 1.0  (A win) | 0.5  (draw) | 0.0  (B win)

change   = k × (score − expected)     # k = 0.1

μ_A  += change × σ_A
μ_B  −= change × σ_B
σ_A  *= 0.99
σ_B  *= 0.99
```

Upsets (unexpected results) produce larger rating changes than expected results. Sigma decays after every comparison, making ratings increasingly stable over time.

#### Pair selection

The engine picks the next pair to present in three steps:

1. **Ranking neighbours** — sort all eligible items by current μ, then walk adjacent pairs. Prefer the pair with the highest combined σ (most uncertain neighbours).
2. **Random exploration** — add 10 random same-tier pairs to prevent the ranking from converging prematurely on a local ordering.
3. **Exhaustive fallback** — if no candidates remain from the above, scan all remaining unranked eligible pairs and pick one at random.

Returns `None` when all eligible pairs have been ranked.

#### Completion detection

Ranking is considered finished when either:

- All eligible pairs have been ranked (hard finish), **or**
- The top-10 ranking has been unchanged for `STABLE_THRESHOLD = 20` consecutive comparisons **and** at least one of those was a real verdict (not a skip).

#### Confidence score

```
avg_sigma       = mean(σ) across all items
sigma_score     = max(0, 1 − avg_sigma / 8.333)   # 0 = no convergence, 1 = fully converged
stability_score = min(1, stable_counter / 20)

confidence      = (sigma_score × 0.5 + stability_score × 0.5) × 100
```

---

### Tier System

Tiers serve two purposes:

1. **Reduce comparisons** — only same-tier pairs are generated by default, avoiding obvious mismatches.
2. **Organise results** — the ranking list can be displayed grouped by tier.

`TierConfig` stores:
- `tiers: list[str]` — ordered tier names (first = best).
- `colors: dict[str, tuple[str, str]]` — `(background_hex, text_hex)` per tier, persisted in the JSON and used consistently across all UI components.

Cross-tier comparisons can be enabled per-session with the **Allow cross-tier comparisons** checkbox. This setting is saved in the project file.

Items that reach the ranking phase without a tier assignment are automatically placed in the last (lowest) tier.

---

### Undo System

Undo is **O(1)** — no history replay.

Before every `submit_result()` call, the engine pushes a `RankingSnapshot` onto a stack:

```python
@dataclass
class RankingSnapshot:
    ratings:      dict[str, Rating]   # full copy of all ratings
    history:      list                # full copy of comparison history
    ranked_pairs: set[str]            # full copy of the ranked pair set
    stable_counter: int
```

`undo_last()` pops the top snapshot and restores all four fields. This means undoing a comparison also un-marks that pair from `ranked_pairs`, making it available for future selection again.

The snapshot stack is not persisted — closing and reopening a project clears undo history.

---

### Pair Deduplication

`ranked_pairs` is a `set[str]` of canonical pair keys. A key is produced by sorting the two item names alphabetically and joining with `|`:

```python
def _pair_key(a: str, b: str) -> str:
    return "|".join(sorted([a, b]))
```

This ensures `"Powerslave|Piece of Mind"` and `"Piece of Mind|Powerslave"` map to the same key. A pair is added to the set when a non-SKIP result is submitted, and removed again if that result is undone.

`get_next_pair()` calls `_pair_ok(a, b)` before adding any candidate, which rejects pairs already in `ranked_pairs`. When the set covers all possible within-tier pairs, `get_next_pair()` returns `None` and ranking is complete.