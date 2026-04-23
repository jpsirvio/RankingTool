"""
qt_app.py — PyQt5 front-end for the Ranking Tool.

Screen flow:
  0. ProjectBrowserScreen — list / open / delete saved projects
  1. ListManagerScreen    — create or edit a list and its tier config
  2. TierAssignmentScreen — assign each item to a tier (flash-card + drag board)
  3. RankingScreen        — pairwise comparisons, live results, auto-save

All persistent state is stored in JSON files under ./projects/.
File names are UUIDs; human-readable names come from the JSON payload.
Auto-save fires after every comparison, undo, and reset so no progress is lost.

Key classes:
  TierColorDialog  — modal dialog for picking per-tier bg/text colors
  TierRowWidget    — one row in the tier editor (pill preview + action buttons)
  ProjectBrowserScreen, ListManagerScreen, TierAssignmentScreen, RankingScreen
  MainWindow       — QMainWindow that owns the QStackedWidget and wires signals
"""

import sys
import json
import uuid
import re
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QStackedWidget,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QLineEdit, QTextEdit, QProgressBar, QFrame, QScrollArea,
    QFileDialog, QMessageBox, QInputDialog, QCheckBox,
    QSplitter, QSizePolicy, QSpacerItem,
    QStatusBar, QDialog, QDialogButtonBox, QGridLayout,
)
from PyQt5.QtCore import Qt, QMimeData, pyqtSignal
from PyQt5.QtGui import QColor, QDrag, QPainter, QBrush, QPen

from ranking_engine import (
    RankingEngine, TierConfig, MatchResult,
    DEFAULT_TIERS, default_color_for_index,
)

# ── Project folder ────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = APP_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

# ── App palette ───────────────────────────────────────────────────────────────
PALETTE = {
    "bg":       "#0f0f13",
    "surface":  "#1a1a24",
    "surface2": "#22222f",
    "border":   "#2e2e3f",
    "accent":   "#7c6af7",
    "accent2":  "#a78bfa",
    "text":     "#e8e6f0",
    "text_dim": "#7a7890",
    "red":      "#f87171",
    "green":    "#34d399",
    "win_a":    "#1e3a5f",
    "win_b":    "#1e3a2f",
}

# Swatch palette shown in the TierColorDialog.
# 36 colors arranged in thematic groups: reds/oranges, yellows/greens,
# blues, purples/pinks, dark neutrals, and light values for text use.
SWATCHES = [
    # Reds / Oranges
    "#b91c1c", "#dc2626", "#ef4444", "#f97316", "#c2410c", "#ea580c",
    # Yellows / Greens
    "#a16207", "#ca8a04", "#16a34a", "#15803d", "#059669", "#0d9488",
    # Blues
    "#0369a1", "#1d4ed8", "#2563eb", "#0891b2", "#0e7490", "#6366f1",
    # Purples / Pinks
    "#7c3aed", "#6d28d9", "#9333ea", "#be185d", "#db2777", "#e11d48",
    # Neutrals
    "#374151", "#4b5563", "#1f2937", "#111827", "#0f172a", "#1e293b",
    # Lights (for dark-bg use)
    "#ffffff", "#f1f5f9", "#e2e8f0", "#cbd5e1", "#f8fafc", "#f0fdf4",
]

APP_QSS = f"""
QMainWindow, QWidget {{
    background-color: {PALETTE['bg']};
    color: {PALETTE['text']};
    font-family: 'Segoe UI', 'SF Pro Display', Ubuntu, sans-serif;
    font-size: 13px;
}}
QLabel {{ color: {PALETTE['text']}; background: transparent; }}
QPushButton {{
    background-color: {PALETTE['surface2']};
    color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    padding: 7px 16px;
}}
QPushButton:hover {{
    background-color: {PALETTE['surface']};
    border-color: {PALETTE['accent']};
}}
QPushButton:pressed {{ background-color: {PALETTE['accent']}; color: white; }}
QPushButton#accent {{
    background-color: {PALETTE['accent']};
    color: white; border: none; font-weight: 600;
}}
QPushButton#accent:hover {{ background-color: {PALETTE['accent2']}; }}
QPushButton#danger {{
    background-color: transparent;
    color: {PALETTE['red']}; border-color: {PALETTE['red']};
}}
QPushButton#danger:hover {{ background-color: {PALETTE['red']}; color: white; }}
QLineEdit, QTextEdit {{
    background-color: {PALETTE['surface2']};
    color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px; padding: 6px 10px;
    selection-background-color: {PALETTE['accent']};
}}
QLineEdit:focus, QTextEdit:focus {{ border-color: {PALETTE['accent']}; }}
QListWidget {{
    background-color: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    border-radius: 8px; color: {PALETTE['text']}; outline: none;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-bottom: 1px solid {PALETTE['border']};
}}
QListWidget::item:selected {{ background-color: {PALETTE['accent']}; color: white; }}
QListWidget::item:hover {{ background-color: {PALETTE['surface2']}; }}
QProgressBar {{
    background-color: {PALETTE['surface2']};
    border: 1px solid {PALETTE['border']};
    border-radius: 8px; height: 14px;
    text-align: center; color: {PALETTE['text']}; font-size: 11px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {PALETTE['accent']}, stop:1 {PALETTE['accent2']});
    border-radius: 8px;
}}
QFrame#card {{
    background-color: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    border-radius: 10px;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {PALETTE['surface']}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {PALETTE['border']}; border-radius: 4px; min-height: 20px;
}}
QStatusBar {{
    background: {PALETTE['surface']}; color: {PALETTE['text_dim']};
    border-top: 1px solid {PALETTE['border']}; font-size: 11px;
}}
QCheckBox {{ color: {PALETTE['text_dim']}; spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {PALETTE['border']};
    border-radius: 3px; background: {PALETTE['surface2']};
}}
QCheckBox::indicator:checked {{
    background: {PALETTE['accent']}; border-color: {PALETTE['accent']};
}}
QDialog {{
    background-color: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    border-radius: 10px;
}}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{PALETTE['text_dim']};font-size:10px;"
        f"font-weight:600;letter-spacing:1.5px;"
    )
    return lbl


def h_line() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{PALETTE['border']};")
    return f


def is_valid_hex(s: str) -> bool:
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", s.strip()))


# ── Project helpers ───────────────────────────────────────────────────────────

def project_display_name(data: dict) -> str:
    name = data.get("list_name", "Unnamed")
    created = data.get("created_at", "")[:10]
    return f"{name} — {created}"


def list_projects() -> list[tuple[Path, dict]]:
    results = []
    for p in sorted(
        PROJECTS_DIR.glob("*.json"),
        key=lambda x: x.stat().st_mtime, reverse=True
    ):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            results.append((p, data))
        except Exception:
            pass
    return results


def save_project(path: Path, engine: RankingEngine, list_name: str, created_at: str):
    state = engine.export_state()
    state["list_name"] = list_name
    state["created_at"] = created_at
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
#  Color Picker Dialog
# ══════════════════════════════════════════════════════════════════════════════

class ColorSwatch(QFrame):
    """A single clickable color swatch."""
    clicked = pyqtSignal(str)

    def __init__(self, hex_color: str, size: int = 28):
        super().__init__()
        self._color = hex_color
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self._apply()

    def _apply(self):
        self.setStyleSheet(
            f"background:{self._color};"
            f"border:2px solid {PALETTE['border']};"
            f"border-radius:4px;"
        )

    def set_selected(self, selected: bool):
        border = PALETTE["accent"] if selected else PALETTE["border"]
        self.setStyleSheet(
            f"background:{self._color};"
            f"border:2px solid {border};"
            f"border-radius:4px;"
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self._color)


class TierColorDialog(QDialog):
    """
    Dialog to pick background and text color for a single tier.
    Shows a swatch grid + hex inputs + a live preview pill.
    """

    def __init__(self, tier_name: str, bg: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Color — {tier_name}")
        self.setModal(True)
        self.setMinimumWidth(440)

        self._bg   = bg
        self._text = text
        self._tier = tier_name

        self._bg_swatches:   list[ColorSwatch] = []
        self._text_swatches: list[ColorSwatch] = []

        self._build_ui()
        self._refresh_preview()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # Live preview
        root.addWidget(section_label("Preview"))
        self._preview = QLabel(self._tier)
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setFixedHeight(48)
        self._preview.setStyleSheet("border-radius:8px;font-size:18px;font-weight:700;")
        root.addWidget(self._preview)

        root.addWidget(h_line())

        # Background color
        root.addWidget(section_label("Background Color"))
        bg_grid, self._bg_swatches = self._swatch_grid(self._bg, self._on_bg_swatch)
        root.addLayout(bg_grid)

        bg_hex_row = QHBoxLayout()
        bg_hex_row.addWidget(QLabel("Hex:"))
        self._bg_edit = QLineEdit(self._bg)
        self._bg_edit.setMaximumWidth(100)
        self._bg_edit.setPlaceholderText("#rrggbb")
        self._bg_edit.textChanged.connect(self._on_bg_hex)
        self._bg_preview = QFrame()
        self._bg_preview.setFixedSize(28, 28)
        self._bg_preview.setStyleSheet(
            f"background:{self._bg};border:1px solid {PALETTE['border']};border-radius:4px;"
        )
        bg_hex_row.addWidget(self._bg_edit)
        bg_hex_row.addWidget(self._bg_preview)
        bg_hex_row.addStretch()
        root.addLayout(bg_hex_row)

        root.addWidget(h_line())

        # Text color
        root.addWidget(section_label("Text Color"))
        text_grid, self._text_swatches = self._swatch_grid(self._text, self._on_text_swatch)
        root.addLayout(text_grid)

        text_hex_row = QHBoxLayout()
        text_hex_row.addWidget(QLabel("Hex:"))
        self._text_edit = QLineEdit(self._text)
        self._text_edit.setMaximumWidth(100)
        self._text_edit.setPlaceholderText("#rrggbb")
        self._text_edit.textChanged.connect(self._on_text_hex)
        self._text_preview = QFrame()
        self._text_preview.setFixedSize(28, 28)
        self._text_preview.setStyleSheet(
            f"background:{self._text};border:1px solid {PALETTE['border']};border-radius:4px;"
        )
        text_hex_row.addWidget(self._text_edit)
        text_hex_row.addWidget(self._text_preview)
        text_hex_row.addStretch()
        root.addLayout(text_hex_row)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(f"color:{PALETTE['text']};")
        root.addWidget(btns)

    def _swatch_grid(self, selected: str, callback) -> tuple[QGridLayout, list[ColorSwatch]]:
        grid = QGridLayout()
        grid.setSpacing(4)
        swatches = []
        cols = 12
        for i, color in enumerate(SWATCHES):
            sw = ColorSwatch(color)
            sw.set_selected(color.lower() == selected.lower())
            sw.clicked.connect(callback)
            grid.addWidget(sw, i // cols, i % cols)
            swatches.append(sw)
        return grid, swatches

    def _on_bg_swatch(self, color: str):
        self._bg = color
        self._bg_edit.blockSignals(True)
        self._bg_edit.setText(color)
        self._bg_edit.blockSignals(False)
        self._bg_preview.setStyleSheet(
            f"background:{color};border:1px solid {PALETTE['border']};border-radius:4px;"
        )
        for sw in self._bg_swatches:
            sw.set_selected(sw._color.lower() == color.lower())
        self._refresh_preview()

    def _on_text_swatch(self, color: str):
        self._text = color
        self._text_edit.blockSignals(True)
        self._text_edit.setText(color)
        self._text_edit.blockSignals(False)
        self._text_preview.setStyleSheet(
            f"background:{color};border:1px solid {PALETTE['border']};border-radius:4px;"
        )
        for sw in self._text_swatches:
            sw.set_selected(sw._color.lower() == color.lower())
        self._refresh_preview()

    def _on_bg_hex(self, text: str):
        text = text.strip()
        if not text.startswith("#"):
            text = "#" + text
        if is_valid_hex(text):
            self._bg = text
            self._bg_preview.setStyleSheet(
                f"background:{text};border:1px solid {PALETTE['border']};border-radius:4px;"
            )
            for sw in self._bg_swatches:
                sw.set_selected(sw._color.lower() == text.lower())
            self._refresh_preview()

    def _on_text_hex(self, text: str):
        text = text.strip()
        if not text.startswith("#"):
            text = "#" + text
        if is_valid_hex(text):
            self._text = text
            self._text_preview.setStyleSheet(
                f"background:{text};border:1px solid {PALETTE['border']};border-radius:4px;"
            )
            for sw in self._text_swatches:
                sw.set_selected(sw._color.lower() == text.lower())
            self._refresh_preview()

    def _refresh_preview(self):
        self._preview.setStyleSheet(
            f"background:{self._bg};color:{self._text};"
            f"border-radius:8px;font-size:18px;font-weight:700;"
        )

    def result_colors(self) -> tuple[str, str]:
        return self._bg, self._text


# ══════════════════════════════════════════════════════════════════════════════
#  Tier Row Widget  (used inside ListManagerScreen)
# ══════════════════════════════════════════════════════════════════════════════

class TierRowWidget(QWidget):
    """
    One row in the tier editor: [colored pill] [name label] [Rename] [Colors] [↑] [↓] [✕]
    Emits signals for all actions.
    """
    rename_requested  = pyqtSignal(str)       # current name
    color_requested   = pyqtSignal(str)       # current name
    move_up           = pyqtSignal(str)
    move_down         = pyqtSignal(str)
    remove_requested  = pyqtSignal(str)

    def __init__(self, name: str, bg: str, text: str):
        super().__init__()
        self.tier_name = name
        self._bg   = bg
        self._text = text
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Colored pill preview — shows tier name with its bg/text colors
        self._pill = QLabel(self.tier_name)
        self._pill.setAlignment(Qt.AlignCenter)
        self._pill.setFixedHeight(28)
        self._pill.setMinimumWidth(56)
        self._apply_pill()
        layout.addWidget(self._pill)

        layout.addStretch()

        # Action buttons — let Qt size width from content so text always fits
        for label, signal in [
            ("Rename", self.rename_requested),
            ("Colors", self.color_requested),
            ("↑",      self.move_up),
            ("↓",      self.move_down),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setMinimumWidth(32)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _, s=signal: s.emit(self.tier_name))
            layout.addWidget(btn)

        del_btn = QPushButton("✕")
        del_btn.setObjectName("danger")
        del_btn.setFixedHeight(28)
        del_btn.setMinimumWidth(30)
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self.tier_name))
        layout.addWidget(del_btn)

    def _apply_pill(self):
        self._pill.setStyleSheet(
            f"background:{self._bg};color:{self._text};"
            f"border-radius:5px;font-weight:700;font-size:12px;padding:0 8px;"
        )

    def update_colors(self, bg: str, text: str):
        self._bg   = bg
        self._text = text
        self._apply_pill()

    def update_name(self, name: str):
        self.tier_name = name
        self._pill.setText(name)


# ══════════════════════════════════════════════════════════════════════════════
#  SCREEN 0 — Project Browser
# ══════════════════════════════════════════════════════════════════════════════

class ProjectBrowserScreen(QWidget):
    """
    Opening screen — lists all projects found in ./projects/.

    Each project is shown as 'List Name — YYYY.MM.DD HH:MM:SS'.
    Double-click or 'Open selected' loads the project.  If tier assignment
    is incomplete the app navigates to TierAssignmentScreen; otherwise it
    goes directly to RankingScreen.
    """
    open_project = pyqtSignal(Path, dict)
    new_project  = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)

        title = QLabel("Ranking Tool")
        title.setStyleSheet(f"font-size:28px;font-weight:700;color:{PALETTE['text']};")
        root.addWidget(title)
        root.addWidget(section_label("Projects"))

        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self._open_selected)
        root.addWidget(self.project_list, 1)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open selected")
        open_btn.clicked.connect(self._open_selected)
        del_btn = QPushButton("Delete")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete_selected)
        new_btn = QPushButton("New list")
        new_btn.setObjectName("accent")
        new_btn.setMinimumHeight(40)
        new_btn.clicked.connect(self.new_project.emit)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        btn_row.addWidget(new_btn)
        root.addLayout(btn_row)

        self.status_lbl = QLabel(f"Projects folder: {PROJECTS_DIR}")
        self.status_lbl.setStyleSheet(f"color:{PALETTE['text_dim']};font-size:10px;")
        root.addWidget(self.status_lbl)

    def refresh(self):
        self.project_list.clear()
        self._projects = list_projects()
        for path, data in self._projects:
            item = QListWidgetItem(project_display_name(data))
            item.setData(Qt.UserRole, (path, data))
            n     = len(data.get("values", []))
            pairs = len(data.get("ranked_pairs", []))
            item.setToolTip(f"{n} items · {pairs} pairs ranked · {path.name}")
            self.project_list.addItem(item)
        if not self._projects:
            self.project_list.addItem(
                "No projects yet — create a new list to get started"
            )

    def _open_selected(self):
        item = self.project_list.currentItem()
        if not item:
            return
        payload = item.data(Qt.UserRole)
        if payload is None:
            return
        self.open_project.emit(*payload)

    def _delete_selected(self):
        item = self.project_list.currentItem()
        if not item:
            return
        payload = item.data(Qt.UserRole)
        if payload is None:
            return
        path, data = payload
        if QMessageBox.question(
            self, "Delete project",
            f"Permanently delete '{project_display_name(data)}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            path.unlink(missing_ok=True)
            self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
#  SCREEN 1 — List Manager
# ══════════════════════════════════════════════════════════════════════════════

class ListManagerScreen(QWidget):
    """
    Screen 1 — create or edit a list and configure its tiers.

    Left panel:  item editor (type one-by-one, paste bulk, import .txt).
    Right panel: tier editor — each tier is a TierRowWidget with Rename,
                 Colors, move-up/down, and remove buttons.  Clicking Colors
                 opens TierColorDialog.

    Emits proceed(list_name, values, TierConfig) when the user continues.
    """
    proceed = pyqtSignal(str, list, object)   # list_name, values, TierConfig
    back    = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Internal tier state: ordered list of (name, bg, text)
        self._tiers: list[tuple[str, str, str]] = []
        self._tier_rows: list[TierRowWidget] = []
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(24)

        # ── Left: items ────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)

        header = QHBoxLayout()
        back_btn = QPushButton("← Projects")
        back_btn.clicked.connect(self.back.emit)
        self.screen_title = QLabel("New List")
        self.screen_title.setStyleSheet(
            f"font-size:20px;font-weight:700;color:{PALETTE['text']};"
        )
        header.addWidget(back_btn)
        header.addWidget(self.screen_title)
        header.addStretch()
        left.addLayout(header)

        left.addWidget(section_label("List name"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Iron Maiden Discography")
        left.addWidget(self.name_edit)

        left.addWidget(section_label("Items"))
        self.item_list = QListWidget()
        self.item_list.setDragDropMode(QListWidget.InternalMove)
        left.addWidget(self.item_list)

        row = QHBoxLayout()
        self.item_edit = QLineEdit()
        self.item_edit.setPlaceholderText("New item…")
        self.item_edit.returnPressed.connect(self._add_item)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_item)
        row.addWidget(self.item_edit)
        row.addWidget(add_btn)
        left.addLayout(row)

        left.addWidget(section_label("Bulk import (one per line or semicolons)"))
        self.bulk_edit = QTextEdit()
        self.bulk_edit.setPlaceholderText("Paste items here…")
        self.bulk_edit.setMaximumHeight(80)
        left.addWidget(self.bulk_edit)

        bulk_row = QHBoxLayout()
        for label, fn in [
            ("Import from text", self._bulk_import),
            ("Import .txt file", self._import_txt),
            ("Remove selected",  self._remove_selected),
        ]:
            b = QPushButton(label)
            if label == "Remove selected":
                b.setObjectName("danger")
            b.clicked.connect(fn)
            bulk_row.addWidget(b)
        left.addLayout(bulk_row)

        self.item_count_lbl = QLabel("0 items")
        self.item_count_lbl.setStyleSheet(
            f"color:{PALETTE['text_dim']};font-size:11px;"
        )
        left.addWidget(self.item_count_lbl)
        root.addLayout(left, 3)

        # ── Right: tier editor ─────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        right.addWidget(section_label("Tier Configuration"))

        # Scrollable tier rows container
        tier_scroll = QScrollArea()
        tier_scroll.setWidgetResizable(True)
        tier_scroll.setMaximumHeight(260)
        self._tier_container = QWidget()
        self._tier_layout = QVBoxLayout(self._tier_container)
        self._tier_layout.setSpacing(4)
        self._tier_layout.setContentsMargins(0, 0, 0, 0)
        self._tier_layout.addStretch()
        tier_scroll.setWidget(self._tier_container)
        right.addWidget(tier_scroll)

        # Add-tier row
        add_row = QHBoxLayout()
        self.tier_edit = QLineEdit()
        self.tier_edit.setPlaceholderText("New tier name…")
        self.tier_edit.returnPressed.connect(self._add_tier)
        add_tier_btn = QPushButton("Add Tier")
        add_tier_btn.clicked.connect(self._add_tier)
        add_row.addWidget(self.tier_edit)
        add_row.addWidget(add_tier_btn)
        right.addLayout(add_row)

        reset_btn = QPushButton("Reset to defaults (S A B C D E)")
        reset_btn.clicked.connect(self._reset_tiers)
        right.addWidget(reset_btn)

        right.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        go_btn = QPushButton("Continue to Tier Assignment →")
        go_btn.setObjectName("accent")
        go_btn.setMinimumHeight(44)
        go_btn.clicked.connect(self._proceed)
        right.addWidget(go_btn)

        root.addLayout(right, 2)

        # Populate with defaults
        self._reset_tiers()

    # ── Items ──────────────────────────────────────────────────

    def _add_item(self):
        text = self.item_edit.text().strip()
        if text:
            self.item_list.addItem(text)
            self.item_edit.clear()
            self._update_count()

    def _bulk_import(self):
        raw = self.bulk_edit.toPlainText().strip()
        if not raw:
            return
        sep = ";" if ";" in raw else "\n"
        items = [x.strip() for x in raw.split(sep) if x.strip()]
        existing = {self.item_list.item(i).text()
                    for i in range(self.item_list.count())}
        for item in items:
            if item not in existing:
                self.item_list.addItem(item)
                existing.add(item)
        self.bulk_edit.clear()
        self._update_count()

    def _import_txt(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Import .txt", "", "Text (*.txt)"
        )
        if not file:
            return
        with open(file, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        sep = ";" if ";" in raw else "\n"
        items = [x.strip() for x in raw.split(sep) if x.strip()]
        existing = {self.item_list.item(i).text()
                    for i in range(self.item_list.count())}
        for item in items:
            if item not in existing:
                self.item_list.addItem(item)
                existing.add(item)
        self._update_count()

    def _remove_selected(self):
        for item in self.item_list.selectedItems():
            self.item_list.takeItem(self.item_list.row(item))
        self._update_count()

    def _update_count(self):
        n = self.item_list.count()
        self.item_count_lbl.setText(f"{n} item{'s' if n != 1 else ''}")

    def _get_items(self) -> list[str]:
        return [self.item_list.item(i).text()
                for i in range(self.item_list.count())]

    # ── Tier editor ────────────────────────────────────────────

    def _rebuild_tier_ui(self):
        """Rebuild the tier row widgets from self._tiers."""
        # Remove all existing row widgets (but keep the stretch at end)
        while self._tier_layout.count() > 1:
            item = self._tier_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._tier_rows = []
        for name, bg, text in self._tiers:
            row = TierRowWidget(name, bg, text)
            row.rename_requested.connect(self._rename_tier)
            row.color_requested.connect(self._edit_tier_colors)
            row.move_up.connect(self._move_tier_up)
            row.move_down.connect(self._move_tier_down)
            row.remove_requested.connect(self._remove_tier)
            self._tier_layout.insertWidget(self._tier_layout.count() - 1, row)
            self._tier_rows.append(row)

    def _add_tier(self):
        name = self.tier_edit.text().strip()
        if not name:
            return
        if any(t[0] == name for t in self._tiers):
            QMessageBox.warning(self, "Duplicate", f"Tier '{name}' already exists.")
            return
        idx = len(self._tiers)
        bg, text = default_color_for_index(idx)
        self._tiers.append((name, bg, text))
        self.tier_edit.clear()
        self._rebuild_tier_ui()

    def _rename_tier(self, name: str):
        new, ok = QInputDialog.getText(
            self, "Rename tier", f"New name for '{name}':", text=name
        )
        if not ok or not new.strip():
            return
        new = new.strip()
        if any(t[0] == new for t in self._tiers):
            QMessageBox.warning(self, "Duplicate", f"Tier '{new}' already exists.")
            return
        self._tiers = [
            (new if t[0] == name else t[0], t[1], t[2])
            for t in self._tiers
        ]
        self._rebuild_tier_ui()

    def _edit_tier_colors(self, name: str):
        entry = next((t for t in self._tiers if t[0] == name), None)
        if not entry:
            return
        _, bg, text = entry
        dlg = TierColorDialog(name, bg, text, self)
        if dlg.exec_() == QDialog.Accepted:
            new_bg, new_text = dlg.result_colors()
            self._tiers = [
                (t[0], new_bg if t[0] == name else t[1],
                        new_text if t[0] == name else t[2])
                for t in self._tiers
            ]
            self._rebuild_tier_ui()

    def _move_tier_up(self, name: str):
        idx = next((i for i, t in enumerate(self._tiers) if t[0] == name), -1)
        if idx > 0:
            self._tiers[idx], self._tiers[idx - 1] = \
                self._tiers[idx - 1], self._tiers[idx]
            self._rebuild_tier_ui()

    def _move_tier_down(self, name: str):
        idx = next((i for i, t in enumerate(self._tiers) if t[0] == name), -1)
        if 0 <= idx < len(self._tiers) - 1:
            self._tiers[idx], self._tiers[idx + 1] = \
                self._tiers[idx + 1], self._tiers[idx]
            self._rebuild_tier_ui()

    def _remove_tier(self, name: str):
        self._tiers = [t for t in self._tiers if t[0] != name]
        self._rebuild_tier_ui()

    def _reset_tiers(self):
        self._tiers = []
        for i, name in enumerate(DEFAULT_TIERS):
            bg, text = default_color_for_index(i)
            self._tiers.append((name, bg, text))
        self._rebuild_tier_ui()

    def _get_tier_config(self) -> TierConfig:
        colors = {name: (bg, txt) for name, bg, txt in self._tiers}
        return TierConfig(
            tiers=[t[0] for t in self._tiers],
            colors=colors,
        )

    # ── Populate from existing project ────────────────────────

    def populate_from_data(self, data: dict):
        self.name_edit.setText(data.get("list_name", ""))
        self.item_list.clear()
        for v in data.get("values", []):
            self.item_list.addItem(v)
        self._update_count()

        tc = TierConfig.from_dict(data.get("tier_config", {"tiers": DEFAULT_TIERS}))
        self._tiers = []
        for i, name in enumerate(tc.tiers):
            bg, txt = tc.get_colors(name)
            self._tiers.append((name, bg, txt))
        self._rebuild_tier_ui()

    # ── Proceed ────────────────────────────────────────────────

    def _proceed(self):
        list_name = self.name_edit.text().strip()
        if not list_name:
            QMessageBox.warning(self, "Name required", "Please enter a list name.")
            self.name_edit.setFocus()
            return
        items = self._get_items()
        if len(items) < 2:
            QMessageBox.warning(self, "Too few items", "Add at least 2 items.")
            return
        if not self._tiers:
            QMessageBox.warning(self, "No tiers", "Add at least one tier.")
            return
        self.proceed.emit(list_name, items, self._get_tier_config())


# ══════════════════════════════════════════════════════════════════════════════
#  SCREEN 2 — Tier Assignment
# ══════════════════════════════════════════════════════════════════════════════

class DraggableItemLabel(QLabel):
    def __init__(self, text: str, bg: str, fg: str):
        super().__init__(text)
        self.item_name = text
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(34)
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet(
            f"background:{bg};color:{fg};"
            f"border:1px solid {bg};border-radius:6px;"
            f"padding:4px 10px;font-size:12px;font-weight:600;"
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.item_name)
            drag.setMimeData(mime)
            drag.exec_(Qt.MoveAction)


class TierBucket(QFrame):
    item_dropped = pyqtSignal(str, str)

    def __init__(self, tier_name: str, bg: str, fg: str):
        super().__init__()
        self.tier_name = tier_name
        self.bg = bg
        self.fg = fg
        self.setAcceptDrops(True)
        self.setMinimumHeight(72)
        self.setStyleSheet(
            f"background:{bg}22;"
            f"border:1px solid {bg}88;border-radius:8px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header = QLabel(tier_name)
        header.setStyleSheet(
            f"background:{bg};color:{fg};font-weight:700;font-size:13px;"
            f"border-radius:4px;padding:1px 6px;border:none;"
        )
        header.setFixedHeight(24)
        layout.addWidget(header)

        self.items_row = QHBoxLayout()
        self.items_row.setSpacing(4)
        self.items_row.setAlignment(Qt.AlignLeft)
        layout.addLayout(self.items_row)

        self._labels: dict[str, DraggableItemLabel] = {}

    def add_item(self, name: str):
        if name not in self._labels:
            lbl = DraggableItemLabel(name, self.bg, self.fg)
            self._labels[name] = lbl
            self.items_row.addWidget(lbl)

    def remove_item(self, name: str):
        if name in self._labels:
            lbl = self._labels.pop(name)
            self.items_row.removeWidget(lbl)
            lbl.deleteLater()

    def get_items(self) -> list[str]:
        return list(self._labels.keys())

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.item_dropped.emit(e.mimeData().text(), self.tier_name)
        e.acceptProposedAction()


class TierAssignmentScreen(QWidget):
    """
    Screen 2 — assign each item in the list to a tier.

    Two interaction modes:
      Flash-card: items are presented one at a time; clicking a tier button
                  assigns the item and advances to the next.
      Drag board: all assigned items are shown as colored pills inside their
                  tier bucket; drag a pill to a different bucket to reassign.

    On proceed, any still-unassigned items are automatically placed in the
    last tier so no item is silently excluded from ranking.
    """
    proceed = pyqtSignal(object)
    back    = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.engine: RankingEngine | None = None
        self._queue: list[str] = []
        self._buckets: dict[str, TierBucket] = {}
        self._build_ui()

    def _build_ui(self):
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(32, 32, 32, 32)
        self._root.setSpacing(16)

        header = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self.back.emit)
        title = QLabel("Tier Assignment")
        title.setStyleSheet(f"font-size:20px;font-weight:700;color:{PALETTE['text']};")
        header.addWidget(back_btn)
        header.addWidget(title)
        header.addStretch()
        self._root.addLayout(header)

        self._flash_frame = QFrame()
        self._flash_frame.setObjectName("card")
        flash_layout = QVBoxLayout(self._flash_frame)
        flash_layout.setContentsMargins(24, 20, 24, 20)

        self._flash_sub = QLabel("")
        self._flash_sub.setStyleSheet(f"color:{PALETTE['text_dim']};font-size:12px;")
        flash_layout.addWidget(self._flash_sub, alignment=Qt.AlignCenter)

        self._flash_label = QLabel("")
        self._flash_label.setAlignment(Qt.AlignCenter)
        self._flash_label.setWordWrap(True)
        self._flash_label.setStyleSheet(
            f"font-size:26px;font-weight:700;color:{PALETTE['text']};padding:10px;"
        )
        flash_layout.addWidget(self._flash_label)

        self._tier_btn_row = QHBoxLayout()
        self._tier_btn_row.setSpacing(8)
        flash_layout.addLayout(self._tier_btn_row)

        self._flash_progress = QProgressBar()
        flash_layout.addWidget(self._flash_progress)

        skip_btn = QPushButton("Skip (assign later)")
        skip_btn.clicked.connect(self._skip_item)
        flash_layout.addWidget(skip_btn, alignment=Qt.AlignRight)

        self._root.addWidget(self._flash_frame)

        self._root.addWidget(section_label("Drag items between tiers to adjust"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._board_widget = QWidget()
        self._board_layout = QVBoxLayout(self._board_widget)
        self._board_layout.setSpacing(6)
        scroll.setWidget(self._board_widget)
        scroll.setMinimumHeight(180)
        self._root.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        self._progress_lbl = QLabel("")
        self._progress_lbl.setStyleSheet(f"color:{PALETTE['text_dim']};")
        bottom.addWidget(self._progress_lbl)
        bottom.addStretch()
        go_btn = QPushButton("Start Ranking →")
        go_btn.setObjectName("accent")
        go_btn.setMinimumHeight(40)
        go_btn.clicked.connect(self._proceed)
        bottom.addWidget(go_btn)
        self._root.addLayout(bottom)

    def setup(self, engine: RankingEngine):
        self.engine = engine
        self._queue = [n for n in engine.names if engine.get_tier(n) is None]

        while self._tier_btn_row.count():
            w = self._tier_btn_row.takeAt(0).widget()
            if w:
                w.setParent(None)

        for tier in engine.tier_config.tiers:
            bg, fg = engine.tier_config.get_colors(tier)
            btn = QPushButton(tier)
            btn.setStyleSheet(
                f"background:{bg};color:{fg};border:none;"
                f"border-radius:6px;padding:6px 18px;font-weight:700;"
            )
            btn.clicked.connect(lambda _, t=tier: self._assign_tier(t))
            self._tier_btn_row.addWidget(btn)

        while self._board_layout.count():
            item = self._board_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        self._buckets = {}
        for tier in engine.tier_config.tiers:
            bg, fg = engine.tier_config.get_colors(tier)
            bucket = TierBucket(tier, bg, fg)
            bucket.item_dropped.connect(self._on_drop)
            self._buckets[tier] = bucket
            self._board_layout.addWidget(bucket)
            for name in engine.get_items_in_tier(tier):
                bucket.add_item(name)

        self._update_flash()

    def _update_flash(self):
        if not self._queue:
            self._flash_frame.setVisible(False)
            self._progress_lbl.setText("All items assigned — adjust via drag if needed.")
            return
        self._flash_frame.setVisible(True)
        item = self._queue[0]
        self._flash_label.setText(item)
        done  = len(self.engine.names) - len(self._queue)
        total = len(self.engine.names)
        self._flash_progress.setMaximum(total)
        self._flash_progress.setValue(done)
        self._flash_sub.setText(f"Assign this item to a tier  ({done}/{total})")
        self._progress_lbl.setText(f"{len(self._queue)} item(s) left to assign")

    def _assign_tier(self, tier: str):
        if not self._queue:
            return
        name = self._queue.pop(0)
        self.engine.assign_tier(name, tier)
        self._buckets[tier].add_item(name)
        self._update_flash()

    def _skip_item(self):
        if self._queue:
            self._queue.append(self._queue.pop(0))
            self._update_flash()

    def _on_drop(self, name: str, new_tier: str):
        old_tier = self.engine.get_tier(name)
        if old_tier == new_tier:
            return
        if old_tier and old_tier in self._buckets:
            self._buckets[old_tier].remove_item(name)
        self.engine.assign_tier(name, new_tier)
        self._buckets[new_tier].add_item(name)
        if name in self._queue:
            self._queue.remove(name)
        self._update_flash()

    def _proceed(self):
        """
        Move to the ranking phase.
        Any items still unassigned are automatically placed in the last tier
        so they are always included in comparisons — no items are silently dropped.
        """
        unassigned = self.engine.get_untiered_items()
        if unassigned:
            last_tier = self.engine.tier_config.tiers[-1]
            for name in unassigned:
                self.engine.assign_tier(name, last_tier)
                # Also update the drag-board bucket so the UI stays consistent
                if last_tier in self._buckets:
                    self._buckets[last_tier].add_item(name)
        self.proceed.emit(self.engine)


# ══════════════════════════════════════════════════════════════════════════════
#  SCREEN 3 — Ranking
# ══════════════════════════════════════════════════════════════════════════════

class RankingScreen(QWidget):
    """
    Screen 3 — pairwise comparison UI.

    Two items are shown side-by-side as clickable cards.  The user picks
    the better one (or draw/skip) using mouse clicks or keyboard shortcuts:
      A = left wins   D = right wins   S = draw   Z = undo   Space = skip

    The ranking list below the cards can be sorted two ways:
      Tier → Score  (default) — grouped by tier, ranked by score within tier
      Score only              — flat global score order

    Every comparison is auto-saved to the project JSON immediately.
    """
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.engine: RankingEngine | None = None
        self._project_path: Path | None   = None
        self._list_name: str              = ""
        self._created_at: str             = ""
        self.current_pair: tuple | None   = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.title_lbl = QLabel("Ranking")
        self.title_lbl.setStyleSheet(
            f"font-size:20px;font-weight:700;color:{PALETTE['text']};"
        )
        header.addWidget(self.title_lbl)
        header.addStretch()
        self.cross_tier_cb = QCheckBox("Allow cross-tier comparisons")
        self.cross_tier_cb.toggled.connect(self._toggle_cross_tier)
        header.addWidget(self.cross_tier_cb)
        back_btn = QPushButton("← Back to Tiers")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        root.addLayout(header)

        prog_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.pairs_lbl = QLabel("")
        self.pairs_lbl.setStyleSheet(
            f"color:{PALETTE['text_dim']};font-size:11px;min-width:160px;"
        )
        self.confidence_lbl = QLabel("Confidence: —")
        self.confidence_lbl.setStyleSheet(
            f"color:{PALETTE['accent2']};font-size:12px;min-width:130px;"
        )
        prog_row.addWidget(self.progress, 1)
        prog_row.addWidget(self.pairs_lbl)
        prog_row.addWidget(self.confidence_lbl)
        root.addLayout(prog_row)

        card_row = QHBoxLayout()
        card_row.setSpacing(12)
        self.card_a, self.lbl_a = self._make_compare_card("#1e3a5f", "#60a5fa", lambda: self._submit(MatchResult.A))
        draw_btn = QPushButton("Draw\n[S]")
        draw_btn.setMinimumHeight(140)
        draw_btn.setStyleSheet(
            f"background:{PALETTE['surface2']};color:{PALETTE['text_dim']};"
            f"border:1px solid {PALETTE['border']};border-radius:10px;font-size:13px;"
        )
        draw_btn.clicked.connect(lambda: self._submit(MatchResult.DRAW))
        self.card_b, self.lbl_b = self._make_compare_card("#1e3a2f", "#34d399", lambda: self._submit(MatchResult.B))
        card_row.addWidget(self.card_a, 2)
        card_row.addWidget(draw_btn, 1)
        card_row.addWidget(self.card_b, 2)
        root.addLayout(card_row)

        hint = QLabel("[A] Left wins    [S] Draw    [D] Right wins    [Z] Undo    [Space] Skip")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color:{PALETTE['text_dim']};font-size:11px;")
        root.addWidget(hint)

        ctrl = QHBoxLayout()
        for label, fn in [
            ("↩ Undo [Z]",   self._undo),
            ("Skip [Space]",  lambda: self._submit(MatchResult.SKIP)),
            ("Reset",         self._reset),
        ]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            ctrl.addWidget(b)
        root.addLayout(ctrl)

        # ── Combined ranking list with sort-mode toggle ──────
        rank_header = QHBoxLayout()
        rank_header.addWidget(section_label("Results"))
        rank_header.addStretch()
        rank_header.addWidget(QLabel("Sort by:"))

        # Radio-style toggle buttons for sort mode
        self._sort_tier_btn = QPushButton("Tier → Score")
        self._sort_tier_btn.setCheckable(True)
        self._sort_tier_btn.setChecked(True)   # default
        self._sort_score_btn = QPushButton("Score only")
        self._sort_score_btn.setCheckable(True)
        self._sort_tier_btn.setStyleSheet(
            f"QPushButton{{background:{PALETTE['accent']};color:#fff;border:none;"
            f"border-radius:4px;padding:4px 10px;font-size:11px;}}"
            f"QPushButton:!checked{{background:{PALETTE['surface2']};"
            f"color:{PALETTE['text_dim']};border:1px solid {PALETTE['border']};}}"
        )
        self._sort_score_btn.setStyleSheet(self._sort_tier_btn.styleSheet())
        self._sort_tier_btn.clicked.connect(lambda: self._set_sort("tier"))
        self._sort_score_btn.clicked.connect(lambda: self._set_sort("score"))
        rank_header.addWidget(self._sort_tier_btn)
        rank_header.addWidget(self._sort_score_btn)
        root.addLayout(rank_header)

        self.rank_list = QListWidget()
        root.addWidget(self.rank_list, 1)

        # Track current sort mode
        self._sort_mode = "tier"  # "tier" | "score"

        self.stats_lbl = QLabel("")
        self.stats_lbl.setStyleSheet(f"color:{PALETTE['text_dim']};font-size:11px;")
        root.addWidget(self.stats_lbl)

    def _make_compare_card(self, bg: str, text_color: str, callback) -> tuple:
        frame = QFrame()
        frame.setMinimumHeight(160)
        frame.setCursor(Qt.PointingHandCursor)
        frame.setStyleSheet(
            f"QFrame {{background:{bg};border:1px solid {text_color}44;border-radius:10px;}}"
            f"QFrame:hover {{border:2px solid {text_color};}}"
        )
        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel("")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color:{text_color};font-size:18px;font-weight:700;"
            f"background:transparent;border:none;padding:8px;"
        )
        layout.addWidget(lbl)
        frame.mousePressEvent = lambda e, cb=callback: cb()
        return frame, lbl

    def setup(self, engine: RankingEngine, project_path: Path,
              list_name: str, created_at: str):
        self.engine        = engine
        self._project_path = project_path
        self._list_name    = list_name
        self._created_at   = created_at
        self.title_lbl.setText(f"Ranking — {list_name}")
        self.cross_tier_cb.setChecked(engine.allow_cross_tier)
        self._load_next_pair()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_A:        self._submit(MatchResult.A)
        elif k == Qt.Key_D:      self._submit(MatchResult.B)
        elif k == Qt.Key_S:      self._submit(MatchResult.DRAW)
        elif k == Qt.Key_Z:      self._undo()
        elif k == Qt.Key_Space:  self._submit(MatchResult.SKIP)
        else: super().keyPressEvent(e)

    def _load_next_pair(self):
        if self.engine.is_finished():
            QMessageBox.information(self, "Done", "Ranking complete! 🎉")
            self._update_ui()
            return
        pair = self.engine.get_next_pair()
        if pair is None:
            QMessageBox.information(self, "Done", "All pairs have been ranked! 🎉")
            self._update_ui()
            return
        a, b = pair
        self.current_pair = (a, b)
        at = self.engine.get_tier(a) or "?"
        bt = self.engine.get_tier(b) or "?"
        self.lbl_a.setText(f"{a}\n[Tier {at}]")
        self.lbl_b.setText(f"{b}\n[Tier {bt}]")
        self._update_ui()

    def _submit(self, result: MatchResult):
        if not self.current_pair:
            return
        a, b = self.current_pair
        self.engine.submit_result(a, b, result)
        self._autosave()
        self._load_next_pair()

    def _autosave(self):
        if self._project_path:
            save_project(self._project_path, self.engine,
                         self._list_name, self._created_at)

    def _update_ui(self):
        done, total, pct = self.engine.get_progress()
        self.progress.setMaximum(100)
        self.progress.setValue(pct)
        self.progress.setFormat(f"{pct}%")
        self.pairs_lbl.setText(f"{done} / {total} pairs ranked")
        conf = self.engine.get_confidence()
        self.confidence_lbl.setText(f"Confidence: {conf:.0f}%")

        self._refresh_rank_list()

        self.stats_lbl.setText(
            f"Items: {len(self.engine.names)}  |  "
            f"History: {len(self.engine.history)}  |  "
            f"Ranked pairs: {len(self.engine.ranked_pairs)}  |  "
            f"Stable: {self.engine.stable_counter}/{self.engine.STABLE_THRESHOLD}"
        )

    def _set_sort(self, mode: str):
        """Switch between 'tier' (tier-first, then score) and 'score' (global score) sort."""
        self._sort_mode = mode
        self._sort_tier_btn.setChecked(mode == "tier")
        self._sort_score_btn.setChecked(mode == "score")
        self._refresh_rank_list()

    def _refresh_rank_list(self):
        """
        Rebuild the combined ranking list using the current sort mode.

        Modes:
          "tier"  — groups items under tier headers, sorted by tier order
                    then by descending score within each tier.
          "score" — flat list ordered purely by descending score, with
                    the tier label shown in brackets for reference.
        """
        scores  = self.engine.get_scores()
        tc      = self.engine.tier_config

        self.rank_list.clear()

        if self._sort_mode == "score":
            # Flat global ranking, pure score order
            ranking = self.engine.get_ranking()
            for i, name in enumerate(ranking, 1):
                tier = self.engine.get_tier(name) or "—"
                if tier != "—":
                    bg, fg = tc.get_colors(tier)
                else:
                    bg, fg = PALETTE["surface2"], PALETTE["text_dim"]
                item = QListWidgetItem(
                    f"{i:>3}. [{tier}]  {name}  ({scores[name]:.2f})"
                )
                item.setForeground(QColor(fg))
                item.setBackground(QColor(bg + "33"))
                self.rank_list.addItem(item)

        else:
            # Tier-first: iterate tiers in config order, within each tier
            # sort by descending score
            by_tier = self.engine.get_ranking_by_tier()
            global_rank = 1
            for tier in tc.tiers:
                items = by_tier.get(tier, [])
                if not items:
                    continue
                bg, fg = tc.get_colors(tier)

                # Tier header row
                header = QListWidgetItem(f"  {tier}  ")
                header.setBackground(QColor(bg))
                header.setForeground(QColor(fg))
                header.setTextAlignment(Qt.AlignCenter)
                header.setFlags(Qt.NoItemFlags)   # not selectable
                self.rank_list.addItem(header)

                for name in items:
                    item = QListWidgetItem(
                        f"  {global_rank:>3}. {name}  ({scores[name]:.2f})"
                    )
                    item.setForeground(QColor(fg))
                    item.setBackground(QColor(bg + "22"))
                    self.rank_list.addItem(item)
                    global_rank += 1

            # Items with no tier assignment (edge case)
            untiered = by_tier.get("(untiered)", [])
            if untiered:
                header = QListWidgetItem("  (untiered)  ")
                header.setBackground(QColor(PALETTE["surface2"]))
                header.setForeground(QColor(PALETTE["text_dim"]))
                header.setTextAlignment(Qt.AlignCenter)
                header.setFlags(Qt.NoItemFlags)
                self.rank_list.addItem(header)
                for name in untiered:
                    item = QListWidgetItem(
                        f"  {global_rank:>3}. {name}  ({scores[name]:.2f})"
                    )
                    item.setForeground(QColor(PALETTE["text_dim"]))
                    self.rank_list.addItem(item)
                    global_rank += 1

    def _toggle_cross_tier(self, checked: bool):
        if self.engine:
            self.engine.allow_cross_tier = checked

    def _undo(self):
        if self.engine:
            self.engine.undo_last()
            self._autosave()
            self._load_next_pair()

    def _reset(self):
        if QMessageBox.question(
            self, "Reset", "Reset all comparisons?",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            self.engine.reset()
            self._autosave()
            self._load_next_pair()


# ══════════════════════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ranking Tool")
        self.resize(1050, 780)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.browser_screen = ProjectBrowserScreen()
        self.list_screen    = ListManagerScreen()
        self.tier_screen    = TierAssignmentScreen()
        self.rank_screen    = RankingScreen()

        self.stack.addWidget(self.browser_screen)   # 0
        self.stack.addWidget(self.list_screen)       # 1
        self.stack.addWidget(self.tier_screen)       # 2
        self.stack.addWidget(self.rank_screen)       # 3

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._engine: RankingEngine | None = None
        self._project_path: Path | None    = None
        self._list_name: str               = ""
        self._created_at: str              = ""

        self.browser_screen.new_project.connect(self._on_new_project)
        self.browser_screen.open_project.connect(self._on_open_project)
        self.list_screen.back.connect(self._goto_browser)
        self.list_screen.proceed.connect(self._on_list_proceed)
        self.tier_screen.back.connect(self._goto_list)
        self.tier_screen.proceed.connect(self._on_tier_proceed)
        self.rank_screen.back_requested.connect(self._on_rank_back)

        self._goto_browser()

    def _goto_browser(self):
        self.browser_screen.refresh()
        self.stack.setCurrentIndex(0)
        self.status.showMessage(f"Projects: {PROJECTS_DIR}")

    def _goto_list(self):
        self.stack.setCurrentIndex(1)

    def _on_new_project(self):
        self.list_screen.name_edit.clear()
        self.list_screen.item_list.clear()
        self.list_screen.item_count_lbl.setText("0 items")
        self.list_screen._reset_tiers()
        self.list_screen.screen_title.setText("New List")
        self._project_path = None
        self.stack.setCurrentIndex(1)

    def _on_open_project(self, path: Path, data: dict):
        self._project_path = path
        self._list_name    = data.get("list_name", "Unnamed")
        self._created_at   = data.get("created_at", "")

        engine = RankingEngine([])
        engine.load_from_dict(data)
        self._engine = engine

        if engine.get_untiered_items():
            self.tier_screen.setup(engine)
            self.stack.setCurrentIndex(2)
        else:
            self.rank_screen.setup(engine, path, self._list_name, self._created_at)
            self.stack.setCurrentIndex(3)
            self.rank_screen.setFocus()

        self.status.showMessage(
            f"Loaded: {self._list_name}  |  {len(engine.names)} items  |  "
            f"{len(engine.ranked_pairs)} pairs ranked"
        )

    def _on_list_proceed(self, list_name: str, values: list[str], tier_config: TierConfig):
        # Include full timestamp so two lists with the same name are distinguishable
        created_at = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
        project_id = uuid.uuid4().hex
        path = PROJECTS_DIR / f"{project_id}.json"

        engine = RankingEngine(values, tier_config)
        self._engine       = engine
        self._project_path = path
        self._list_name    = list_name
        self._created_at   = created_at

        save_project(path, engine, list_name, created_at)

        self.tier_screen.setup(engine)
        self.stack.setCurrentIndex(2)
        self.status.showMessage(
            f"Project created: {list_name} — {created_at}  |  {len(values)} items"
        )

    def _on_tier_proceed(self, engine: RankingEngine):
        save_project(self._project_path, engine, self._list_name, self._created_at)
        self.rank_screen.setup(
            engine, self._project_path, self._list_name, self._created_at
        )
        self.stack.setCurrentIndex(3)
        self.rank_screen.setFocus()
        assigned = sum(1 for t in engine.tier_assignments.values() if t)
        self.status.showMessage(
            f"{assigned}/{len(engine.names)} items assigned to tiers"
        )

    def _on_rank_back(self):
        self.tier_screen.setup(self._engine)
        self.stack.setCurrentIndex(2)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())