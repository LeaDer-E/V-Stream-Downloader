from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication


def _hsl(h: int, s: int, l: int, a: int = 255) -> str:
    c = QColor.fromHsl(h % 360, max(0, min(255, int(s * 2.55))), max(0, min(255, int(l * 2.55))), a)
    if a == 255:
        return c.name(QColor.HexRgb)
    return c.name(QColor.HexArgb)


def gen_palette(ar_name: str, en_name: str, accent_hex: str, hue: Optional[int] = None) -> Dict[str, object]:
    base = QColor(accent_hex)
    h = hue if hue is not None else (base.hslHue() if base.hslHue() >= 0 else 255)
    s_acc = max(65, min(95, int(base.hslSaturationF() * 100)))
    h2 = (h + 26) % 360

    dark_tokens = {
        "bg0": _hsl(h, 26, 6),
        "bg1": _hsl(h, 24, 9),
        "bg2": _hsl(h, 22, 13),
        "surface": _hsl(h, 20, 15),
        "surface_hi": _hsl(h, 22, 20),
        "border": _hsl(h, 20, 25),
        "border_hi": _hsl(h, 68, 58),
        "text": _hsl(h, 18, 96),
        "text2": _hsl(h, 14, 74),
        "text3": _hsl(h, 10, 54),
        "accent": accent_hex,
        "accent2": _hsl(h2, s_acc, 54),
        "accent_hi": _hsl(h, min(100, s_acc + 8), 72),
        "on_accent": "#FFFFFF",
        "ok": "#10B981",
        "warn": "#F59E0B",
        "danger": "#EF4444",
        "glass": _hsl(h, 22, 14),
        "shadow": "#000000B8",
        # Specialized media category colors harmonized with theme hue
        "cat_single": _hsl((h + 195) % 360, 84, 60),
        "cat_m3u8": _hsl((h + 45) % 360, 90, 58),
        "cat_channel": _hsl((h + 310) % 360, 84, 64),
    }

    light_tokens = {
        "bg0": _hsl(h, 24, 96),
        "bg1": _hsl(h, 20, 91),
        "bg2": _hsl(h, 18, 85),
        "surface": "#FFFFFF",
        "surface_hi": _hsl(h, 22, 88),
        "border": _hsl(h, 18, 75),
        "border_hi": _hsl(h, 72, 45),
        "text": _hsl(h, 35, 9),
        "text2": _hsl(h, 20, 27),
        "text3": _hsl(h, 14, 43),
        "accent": _hsl(h, s_acc, 44),
        "accent2": _hsl(h2, s_acc, 40),
        "accent_hi": _hsl(h, s_acc, 36),
        "on_accent": "#FFFFFF",
        "ok": "#059669",
        "warn": "#D97706",
        "danger": "#DC2626",
        "glass": _hsl(h, 25, 98),
        "shadow": "#0F172A38",
        "cat_single": _hsl((h + 195) % 360, 78, 40),
        "cat_m3u8": _hsl((h + 45) % 360, 84, 40),
        "cat_channel": _hsl((h + 310) % 360, 78, 42),
    }

    return {
        "ar_name": ar_name,
        "en_name": en_name,
        "accent": accent_hex,
        "hue": h,
        "dark": dark_tokens,
        "light": light_tokens,
    }


PALETTE_SPECS: List[Tuple[str, str, str, str]] = [
    ("cyber_violet", "بنفسجي سيبراني", "Cyber Violet", "#8B5CF6"),
    ("emerald_4k", "زمردي 4K كلاسيك", "4K Emerald Pro", "#10B981"),
    ("royal_indigo", "نيلي ملكي", "Royal Indigo", "#6366F1"),
    ("arc_blue", "أزرق آرك", "Arc Cobalt", "#3B82F6"),
    ("sky_pulse", "نبض السماء", "Sky Pulse", "#0EA5E9"),
    ("cyan_stream", "تيار سيان", "Cyan Stream", "#06B6D4"),
    ("teal_horizon", "أفق فيروزي", "Teal Horizon", "#14B8A6"),
    ("jade_forest", "غابة اليشم", "Jade Forest", "#22C55E"),
    ("lime_volt", "فولت ليموني", "Lime Volt", "#84CC16"),
    ("amber_gold", "ذهبي كهرماني", "Amber Gold", "#F59E0B"),
    ("solar_orange", "برتقالي شمسي", "Solar Orange", "#F97316"),
    ("coral_flame", "لهب مرجاني", "Coral Flame", "#FB7185"),
    ("crimson_core", "قلب قرمزي", "Crimson Core", "#F43F5E"),
    ("ruby_cinema", "ياقوت سينمائي", "Ruby Cinema", "#E11D48"),
    ("magenta_wave", "موجة ماجنتا", "Magenta Wave", "#D946EF"),
    ("orchid_neon", "أوركيد نيون", "Orchid Neon", "#C026D3"),
    ("amethyst_pro", "جمشت احترافي", "Amethyst Pro", "#9333EA"),
    ("lavender_mist", "ضباب اللافندر", "Lavender Mist", "#A855F7"),
    ("slate_titanium", "تيتانيوم صخري", "Slate Titanium", "#64748B"),
    ("arctic_ice", "جليد قطبي", "Arctic Ice", "#38BDF8"),
    ("mint_breeze", "نسيم النعناع", "Mint Breeze", "#34D399"),
    ("sunset_dune", "كثبان الغروب", "Sunset Dune", "#FB923C"),
    ("rose_quartz", "كوارتز وردي", "Rose Quartz", "#EC4899"),
    ("electric_berry", "توت كهربائي", "Electric Berry", "#DB2777"),
    ("deep_ocean", "محيط عميق", "Deep Ocean", "#2563EB"),
    ("aurora_green", "شفق أخضر", "Aurora Green", "#16A34A"),
    ("copper_bronze", "برونز نحاسي", "Copper Bronze", "#D97706"),
    ("velvet_plum", "برقوق مخملي", "Velvet Plum", "#7C3AED"),
    ("neon_laser", "ليزر نيون", "Neon Laser", "#00E5FF"),
    ("obsidian_gold", "سبج ذهبي", "Obsidian Gold", "#EAB308"),
    ("nordic_frost", "صقيع إسكندنافي", "Nordic Frost", "#60A5FA"),
    ("tokyo_night", "ليل طوكيو", "Tokyo Night", "#7AA2F7"),
]

PALETTES: Dict[str, Dict[str, object]] = {
    pid: gen_palette(ar, en, hx) for pid, ar, en, hx in PALETTE_SPECS
}


class ThemeManager:
    def __init__(self) -> None:
        self._palette_id: str = "cyber_violet"
        self._mode: str = "dark"  # "dark", "light", "auto"
        self._custom_accent: str = "#8B5CF6"
        self._playlist_color_map: Dict[str, int] = {}

    @property
    def palette_id(self) -> str:
        return self._palette_id

    @property
    def mode(self) -> str:
        return self._mode

    def effective_mode(self) -> str:
        if self._mode == "auto":
            hints = QGuiApplication.styleHints()
            if hints and hints.colorScheme() == Qt.ColorScheme.Light:
                return "light"
            return "dark"
        return "light" if self._mode == "light" else "dark"

    def set_theme(self, palette_id: str, mode: str = "dark", custom_accent: Optional[str] = None) -> None:
        if custom_accent:
            self._custom_accent = custom_accent
            PALETTES["custom"] = gen_palette("لون مخصص", "Custom Palette", self._custom_accent)
        self._palette_id = palette_id if (palette_id in PALETTES or palette_id == "custom") else "cyber_violet"
        if self._palette_id == "custom" and "custom" not in PALETTES:
            PALETTES["custom"] = gen_palette("لون مخصص", "Custom Palette", self._custom_accent)
        self._mode = mode if mode in ("dark", "light", "auto") else "dark"

    def active_palette(self) -> Dict[str, object]:
        return PALETTES.get(self._palette_id, PALETTES["cyber_violet"])

    def token_str(self, name: str, force_dark: bool = False) -> str:
        pal = self.active_palette()
        sub = pal["dark"] if force_dark else pal[self.effective_mode()]
        return sub.get(name, "#8B5CF6")

    def c(self, name: str, alpha: Optional[int] = None, force_dark: bool = False) -> QColor:
        col = QColor(self.token_str(name, force_dark=force_dark))
        if alpha is not None:
            col.setAlpha(max(0, min(255, alpha)))
        return col

    def playlist_index_number(self, group_id: str) -> int:
        if not group_id:
            return 1
        if group_id not in self._playlist_color_map:
            self._playlist_color_map[group_id] = len(self._playlist_color_map)
        return self._playlist_color_map[group_id] + 1

    def category_color(self, group_type: str, group_id: str = "") -> QColor:
        """
        Returns a distinct, theme-harmonized color for:
        - 'single': Single video color
        - 'm3u8': Stream color
        - 'channel': Full channel color
        - 'playlist': Distinct golden-angle hue per concurrent playlist so 2+ playlists never look the same!
        """
        is_dark = self.effective_mode() == "dark"
        if group_type == "m3u8":
            return self.c("cat_m3u8")
        if group_type == "channel":
            return self.c("cat_channel")
        if group_type == "playlist" and group_id:
            if group_id not in self._playlist_color_map:
                self._playlist_color_map[group_id] = len(self._playlist_color_map)
            idx = self._playlist_color_map[group_id]
            base_hue = int(self.active_palette().get("hue", 255))
            pl_hue = (base_hue + 48 + idx * 127) % 360
            lightness = 62 if is_dark else 42
            return QColor.fromHsl(pl_hue, int(86 * 2.55), int(lightness * 2.55))
        return self.c("cat_single")

    def scrollbar_qss(self) -> str:
        """Sleek custom scrollbar stylesheet matching active theme."""
        thumb = self.token_str("border_hi")
        thumb_idle = self.token_str("border")
        return f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 1px 2px 1px;
            }}
            QScrollBar::handle:vertical {{
                background: {thumb_idle};
                min-height: 28px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {thumb};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                height: 0px;
                background: transparent;
            }}
        """


T = ThemeManager()
