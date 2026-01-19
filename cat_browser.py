import sys
import os
import csv
import random
import json
import time
import importlib.util
import inspect
import re
from datetime import datetime, timedelta
from urllib.parse import quote

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QToolBar, QTabWidget, QWidget,
    QVBoxLayout, QLabel, QTabBar, QPushButton, QStackedLayout, QFileDialog,
    QTextEdit, QHBoxLayout, QComboBox, QGridLayout, QDialog, QDialogButtonBox,
    QCheckBox, QScrollArea, QGroupBox, QFormLayout, QMessageBox, QMenu, QInputDialog,
    QGraphicsDropShadowEffect, QWidgetAction, QSizePolicy
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineDownloadRequest, QWebEngineScript, QWebEngineSettings
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QIcon, QFontDatabase, QAction, QFont,
    QColor, QLinearGradient, QBrush, QPalette, QCursor, QMouseEvent
)
from PyQt6.QtCore import (
    Qt, QUrl, QSize, QRect, QTimer, pyqtSignal as Signal, QPoint,
    QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QThread
)

try:
    from pypresence import Presence
    DISCORD_RPC_AVAILABLE = True
except ImportError:
    DISCORD_RPC_AVAILABLE = False

if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_PATH = os.path.dirname(__file__)

WELCOME_IMG = os.path.join(BASE_PATH, "welcome.png")
FONT_FILE = os.path.join(BASE_PATH, "vrc.ttf")
BG_IMG = os.path.join(BASE_PATH, "bg.png")
BG2_IMG = os.path.join(BASE_PATH, "bg2.png")
FACTS_FILE = os.path.join(BASE_PATH, "facts.txt")
LANGUAGES_FILE = os.path.join(BASE_PATH, "languages.txt")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".cat_browser")
SPLASH_VIDEO = os.path.join(BASE_PATH, "splash.mp4")
os.makedirs(DATA_DIR, exist_ok=True)

EXTENSIONS_DIR = os.path.join(DATA_DIR, "extensions")
os.makedirs(EXTENSIONS_DIR, exist_ok=True)

FAVICON_DIR = os.path.join(DATA_DIR, "favicons")
os.makedirs(FAVICON_DIR, exist_ok=True)

THEMES_DIR = os.path.join(DATA_DIR, "themes")
os.makedirs(THEMES_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
PASSWORDS_FILE = os.path.join(DATA_DIR, "passwords.csv")
SEARCH_ENGINE_FILE = os.path.join(DATA_DIR, "search_engine.json")
SHORTCUTS_FILE = os.path.join(DATA_DIR, "shortcuts.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
SETUP_FILE = os.path.join(DATA_DIR, "setup_completed.json")
SESSION_FILE = os.path.join(DATA_DIR, "session.json")
TAB_STATE_FILE = os.path.join(DATA_DIR, "tab_states.json")

DISCORD_APP_ID = "1439639890848383149"


class ThemeEngine:
    def __init__(self, browser):
        self.browser = browser
        self.current_theme_data = None
        self.theme_path = None
        self.theme_images = {}
        self.current_font = None
        self.default_font = QApplication.font()
        self.current_background = None

    def reset_all_new_tab_backgrounds(self):
        if not hasattr(self.browser, 'tabs'):
            return

        for i in range(self.browser.tabs.count()):
            tab = self.browser.tabs.widget(i)
            if hasattr(tab, 'new_tab_page') and tab.new_tab_page:
                tab.new_tab_page.set_default_background()

    def apply_theme_to_new_tab(self, new_tab_page):
        if self.current_background and hasattr(new_tab_page, 'bg_label'):
            self.apply_background_to_tab(new_tab_page, self.current_background)

    def apply_background_to_tab(self, new_tab_page, bg_image, tab_index=None):
        try:
            pixmap = QPixmap(bg_image)
            if not pixmap.isNull():
                if hasattr(new_tab_page, 'set_custom_background'):
                    new_tab_page.set_custom_background(pixmap)
                else:
                    scaled_pixmap = pixmap.scaled(
                        new_tab_page.size(),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    new_tab_page.bg_label.setPixmap(scaled_pixmap)
                    new_tab_page.bg_label.setScaledContents(False)
                if tab_index is not None:
                    print(f"theme system: applied background to new tab {tab_index}")
                else:
                    print(f"theme system: applied background to new tab")
            else:
                print(f"theme system: failed to load pixmap from {bg_image}")
        except Exception as e:
            print(f"theme system: error applying background: {e}")

    def apply_theme(self, theme_name):
        if not hasattr(self.browser, 'themes') or not self.browser.themes:
            self.apply_default_theme()
            return

        if theme_name == self.browser.translator.tr("default_theme", "Default Theme"):
            self.apply_default_theme()
            return
        if theme_name == self.browser.translator.tr("disable_themes", "Disable All Themes"):
            self.apply_default_theme()
            return

        if theme_name in self.browser.themes:
            theme_data = self.browser.themes[theme_name]
            self.current_theme_data = theme_data
            self.theme_path = theme_data.get('path', '')

            print(f"theme system: applying theme {theme_name}")
            print(f"theme system: has a theme.qss: {theme_data.get('has_qss', False)}")
            print(f"theme system: has a font: {theme_data.get('has_font', False)}")
            print(f"theme system: has images: {theme_data.get('has_images', False)}")

            try:
                self.reset_to_default_font()
                QApplication.instance().setStyleSheet("")

                self.theme_images = self.load_all_theme_images()
                print(f"  Loaded {len(self.theme_images)} image(s) from theme")

                if theme_data.get('has_qss', False) and 'css_content' in theme_data:
                    print(f"theme system: applying qss theme")
                    self.apply_qss_content(theme_data['css_content'])
                else:
                    print(f"theme system: no qss theme found")

                if theme_data.get('has_font', False):
                    font_file = os.path.join(self.theme_path, "font.ttf")
                    if os.path.exists(font_file):
                        print(f"theme system: applying font...")
                        self.apply_font_file(font_file)

                print(f"theme system: applying images from themes...")
                self.update_navigation_buttons()
                self.apply_custom_checkboxes()
                self.update_new_tab_theme()
                self.apply_custom_scrollbars()

                self.browser.style().unpolish(self.browser)
                self.browser.style().polish(self.browser)

                print(f"theme system: theme {theme_name} applied successfully")

            except Exception as e:
                print(f"theme system: error applying theme {theme_name}: {e}")
                import traceback
                traceback.print_exc()
                self.apply_default_theme()
        else:
            print(f"theme system: theme {theme_name} not found in loaded themes")
            self.apply_default_theme()

    def apply_default_theme(self):
        print(f"theme system: applying default theme")

        self.current_theme_data = None
        self.theme_path = None
        self.theme_images = {}
        self.current_background = None

        self.reset_to_default_font()

        default_css = """
        QMainWindow {
            background: #2b2b2b;
            color: white;
            border: none;
        }
        QToolBar {
            background: #2b2b2b;
            border: none;
            border-bottom: 1px solid #3c3c3c;
            spacing: 8px;
            padding: 8px;
        }
        QPushButton {
            background: #3c3c3c;
            border: 1px solid #4a4a4a;
            color: white;
            padding: 2px 4px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background: #4a5a6a;
        }
        QPushButton:pressed {
            background: #5a6a7a;
        }
        QLineEdit {
            background: #3c3c3c;
            border: 1px solid #4a4a4a;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
        }
        QLineEdit:focus {
            border: 1px solid #0078d4;
            background: #4a4a4a;
        }
        QLineEdit::placeholder {
            color: #888;
        }
        QTabWidget::pane {
            border: none;
            background: #1e1e1e;
        }
        QTabWidget::tab-bar {
            alignment: left;
        }
        QTabBar::tab {
            background: #3c3c3c;
            color: #ccc;
            padding: 8px 20px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 1px;
            font-size: 12px;
        }
        QTabBar::tab:selected {
            background: #1e1e1e;
            color: white;
            border-bottom: 2px solid #0078d4;
        }
        QTabBar::tab:hover:!selected {
            background: #4a4a4a;
        }
        QComboBox, QCheckBox, QGroupBox, QTextEdit, QScrollArea, QLabel {
            color: white;
        }
        """
        self.browser.setStyleSheet(default_css)
        QApplication.instance().setStyleSheet(default_css)

        self.reset_navigation_buttons()

        self.reset_all_new_tab_backgrounds()

    def apply_qss_content(self, qss_content):
        try:
            processed_qss = self.process_qss_variables(qss_content)
            if self.theme_images:
                processed_qss = self.replace_image_placeholders(processed_qss)
            self.browser.setStyleSheet(processed_qss)
            QApplication.instance().setStyleSheet(processed_qss)

        except Exception as e:
            print(f"theme system: error applying qss theme {e}")
            raise

    def apply_font_file(self, font_path):
        try:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    font = QFont(font_families[0])
                    self.current_font = font
                    QApplication.instance().setFont(font)

                    if hasattr(self.browser, 'url_bar'):
                        self.browser.url_bar.setFont(font)
        except Exception as e:
            print(f"theme system: error applying font {e}")

    def reset_to_default_font(self):
        self.current_font = self.default_font
        QApplication.instance().setFont(self.default_font)

        if hasattr(self.browser, 'url_bar'):
            self.browser.url_bar.setFont(self.default_font)

        for widget in self.browser.findChildren(QWidget):
            if hasattr(widget, 'setFont'):
                widget.setFont(self.default_font)

    def reset_navigation_buttons(self):
        if not hasattr(self.browser, 'nav_toolbar') or not self.browser.nav_toolbar:
            return

        button_texts = {
            "back": "◀",
            "forward": "▶",
            "reload": "↻",
            "settings": "⚙",
            "plus": "+",
            "magnify": "a"
        }

        try:
            for action in self.browser.nav_toolbar.actions():
                widget = self.browser.nav_toolbar.widgetForAction(action)
                if widget and isinstance(widget, QPushButton):
                    if not widget.icon().isNull():
                        widget.setIcon(QIcon())
                    for btn_name, text in button_texts.items():
                        if widget.text() == "":
                            widget.setText(text)
                            break
        except Exception as e:
            print(f"theme system: error resetting nav buttons {e}")

    def update_navigation_buttons(self):
        if not hasattr(self.browser, 'nav_toolbar') or not self.browser.nav_toolbar:
            return

        button_mapping = {
            "◀": "back",
            "▶": "forward",
            "↻": "reload",
            "⚙": "settings",
            "+": "plus",
            "🔍": "magnify"
        }

        try:
            for action in self.browser.nav_toolbar.actions():
                widget = self.browser.nav_toolbar.widgetForAction(action)
                if widget and isinstance(widget, QPushButton):
                    btn_text = widget.text()
                    if btn_text in button_mapping:
                        image_name = button_mapping[btn_text]
                        if image_name in self.theme_images:
                            icon = QIcon(self.theme_images[image_name])
                            widget.setIcon(icon)
                            widget.setText("")
                            widget.setIconSize(QSize(24, 24))
                            print(f"theme system: applied icon for {image_name}")
                        else:
                            if widget.icon() and not widget.icon().isNull():
                                widget.setIcon(QIcon())
                            if not widget.text():
                                widget.setText(btn_text)
        except Exception as e:
            print(f"theme system: error applying custom nav buttons {e}")

    def load_all_theme_images(self):
        images = {}
        if not self.theme_path or not os.path.exists(self.theme_path):
            return images

        image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.svg')

        for filename in os.listdir(self.theme_path):
            if filename.lower().endswith(image_extensions):
                filepath = os.path.join(self.theme_path, filename)
                key = os.path.splitext(filename)[0].lower()
                images[key] = filepath
                if key == 'bg' or key == 'background':
                    images['newtab_bg'] = filepath
                    images['background'] = filepath
                    images['bg'] = filepath

        print(f"theme system: found images: {list(images.keys())}")
        return images

    def process_qss_variables(self, qss_content):
        import re

        variables = {}
        root_pattern = r':root\s*\{([^}]+)\}'
        root_match = re.search(root_pattern, qss_content, re.DOTALL)

        if root_match:
            root_content = root_match.group(1)
            var_pattern = r'--([a-zA-Z0-9_-]+)\s*:\s*([^;]+);'
            variables = dict(re.findall(var_pattern, root_content))

            qss_content = re.sub(root_pattern, '', qss_content)

        for var_name, var_value in variables.items():
            qss_content = qss_content.replace(f'var(--{var_name})', var_value.strip())

        return qss_content

    def replace_image_placeholders(self, qss_content):
        import re

        image_pattern = r'url\(["\']?([^"\')]+)["\']?\)'

        def replace_image(match):
            filename = match.group(1)
            filename = filename.strip('"\'').strip()
            filename_no_ext = os.path.splitext(filename)[0].lower()

            if filename_no_ext in self.theme_images:
                return f'url("{self.theme_images[filename_no_ext]}")'
            else:
                for img_key, img_path in self.theme_images.items():
                    if img_key in filename_no_ext or filename_no_ext in img_key:
                        return f'url("{img_path}")'
                return match.group(0)

        return re.sub(image_pattern, replace_image, qss_content)

    def apply_custom_checkboxes(self):
        if 'checkbox_checked' in self.theme_images and 'checkbox_unchecked' in self.theme_images:
            checkbox_style = f"""
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QCheckBox::indicator:unchecked {{
                image: url("{self.theme_images['checkbox_unchecked']}");
            }}
            QCheckBox::indicator:unchecked:hover {{
                image: url("{self.theme_images.get('checkbox_unchecked_hover', self.theme_images['checkbox_unchecked'])}");
            }}
            QCheckBox::indicator:checked {{
                image: url("{self.theme_images['checkbox_checked']}");
            }}
            QCheckBox::indicator:checked:hover {{
                image: url("{self.theme_images.get('checkbox_checked_hover', self.theme_images['checkbox_checked'])}");
            }}
            """

            for widget in QApplication.allWidgets():
                if isinstance(widget, QCheckBox):
                    widget.setStyleSheet(checkbox_style)
            print(f"theme system: applied custom checkbox style")

    def apply_custom_scrollbars(self):
        scrollbar_style = ""

        if 'scroll_handle' in self.theme_images:
            scrollbar_style += """
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop: 0 rgba(255, 255, 255, 100),
                    stop: 1 rgba(255, 255, 255, 50));
                border-radius: 6px;
            }
            """

        if scrollbar_style:
            for widget in QApplication.allWidgets():
                if hasattr(widget, 'verticalScrollBar') or hasattr(widget, 'horizontalScrollBar'):
                    current_style = widget.styleSheet()
                    widget.setStyleSheet(current_style + scrollbar_style)
            print(f"theme system: applied custom scrollbar style")

    def update_new_tab_theme(self):
        if not self.theme_path or not hasattr(self.browser, 'tabs'):
            return

        bg_image = None
        bg_keys = ['newtab_bg', 'background', 'bg']

        for bg_key in bg_keys:
            if bg_key in self.theme_images:
                bg_image = self.theme_images[bg_key]
                print(f"theme system: found background image: {os.path.basename(bg_image)}")
                self.current_background = bg_image
                break

        if not bg_image:
            print(f"theme system: no background image found in theme")
            self.current_background = None
            return

        for i in range(self.browser.tabs.count()):
            tab = self.browser.tabs.widget(i)
            if hasattr(tab, 'new_tab_page') and tab.new_tab_page:
                self.apply_background_to_tab(tab.new_tab_page, bg_image, i)

class CustomNewTabPage(QWidget):
    def __init__(self, parent=None, translator=None, theme_engine=None):
        super().__init__(parent)
        self.parent_browser = parent
        self.translator = translator
        self.theme_engine = theme_engine
        self.custom_bg_applied = False
        self.original_pixmap = None

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.bg_container = QWidget()
        self.bg_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.bg_layout = QVBoxLayout(self.bg_container)
        self.bg_layout.setContentsMargins(0, 0, 0, 0)

        self.bg_label = QLabel()
        self.bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.bg_layout.addWidget(self.bg_label)

        self.main_layout.addWidget(self.bg_container)

        self.overlay = QWidget(self)
        self.overlay.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.overlay.setStyleSheet("background: transparent;")

        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.setContentsMargins(50, 50, 50, 50)

        self.title_label = QLabel(self.translator.tr("welcome_title", "cat browser (real)"))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            color:white;
            font-size:32px;
            font-weight:bold;
            margin-bottom:30px;
        """)
        overlay_layout.addWidget(self.title_label)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(self.translator.tr("search_placeholder", "search google or enter url"))
        self.search_bar.setStyleSheet("""
            background-color: rgba(0,0,0,0.8);
            border: 2px solid #1b1c1c;
            border-radius: 16px;
            padding: 12px 20px;
            font-size: 18px;
            color: white;
            min-width: 400px;
            max-width: 600px;
            margin-bottom: 40px;
        """)
        overlay_layout.addWidget(self.search_bar, 0, Qt.AlignmentFlag.AlignCenter)

        shortcuts_label = QLabel(self.translator.tr("shortcuts","Shortcuts"))
        shortcuts_label.setStyleSheet("color:white; font-size:18px; font-weight:bold; margin-bottom:20px;")
        shortcuts_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addWidget(shortcuts_label)

        self.shortcuts_container = QWidget()
        self.shortcuts_container.setStyleSheet("background: transparent;")
        self.shortcuts_layout = QGridLayout(self.shortcuts_container)
        self.shortcuts_layout.setSpacing(15)
        self.shortcuts_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.shortcuts_layout.setContentsMargins(20,10,20,10)

        self.add_shortcut_btn = QPushButton("+")
        self.add_shortcut_btn.setFixedSize(80,90)
        self.add_shortcut_btn.setStyleSheet("""
            QPushButton {
                background: rgba(60,60,60,0.8);
                border: 2px dashed #777;
                border-radius: 8px;
                color: #777;
                font-size:24px;
                font-weight:bold;
            }
            QPushButton:hover {
                background: rgba(80,80,80,0.9);
                border: 2px dashed #0078d4;
                color: #0078d4;
            }
        """)
        self.add_shortcut_btn.clicked.connect(self.add_shortcut)
        self.shortcuts_layout.addWidget(self.add_shortcut_btn, 0, 0)

        overlay_layout.addWidget(self.shortcuts_container)

        self.quote_label = QLabel()
        self.quote_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quote_label.setStyleSheet("color:#ccc; font-size:14px; font-style:italic; margin-top:30px;")
        overlay_layout.addWidget(self.quote_label)

        bottom_container = QWidget()
        bottom_container.setStyleSheet("background: transparent;")
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0,20,20,20)
        bottom_layout.addStretch()
        self.credits_btn = QPushButton(self.translator.tr("credits","Credits"))
        self.credits_btn.setFixedSize(70,25)
        self.credits_btn.setStyleSheet("""
            QPushButton {
                background: rgba(60,60,60,0.8);
                border: 1px solid #777;
                border-radius:4px;
                color:white;
                padding:4px 8px;
                font-size:11px;
                font-weight:bold;
            }
            QPushButton:hover {
                background: rgba(80,80,80,0.9);
                border:1px solid #0078d4;
            }
        """)
        self.credits_btn.clicked.connect(self.show_credits)
        bottom_layout.addWidget(self.credits_btn)
        overlay_layout.addWidget(bottom_container)

        self.shortcuts = self.load_shortcuts()
        self.display_shortcuts()
        self.load_fun_fact()

        self.search_bar.returnPressed.connect(self.perform_search)

        if self.theme_engine and getattr(self.theme_engine,"current_background",None):
            self.set_custom_background(self.theme_engine.current_background)
        else:
            self.set_default_background()

    def download_favicon(self, url):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.netloc:
                domain = parsed.netloc.replace('www.', '')
                favicon_url = f"https://{domain}/favicon.ico"

                favicon_view = QWebEngineView()
                favicon_view.loadFinished.connect(
                    lambda ok, view=favicon_view, dom=domain: self.save_favicon(view, dom, ok)
                )
                favicon_view.load(QUrl(favicon_url))

        except Exception as e:
            print(f"Error setting up favicon download: {e}")

    def save_favicon(self, view, domain, ok):
        try:
            if ok:
                icon = view.page().icon()
                if not icon.isNull():
                    pixmap = icon.pixmap(32, 32)
                    favicon_path = os.path.join(FAVICON_DIR, f"{domain}.png")
                    pixmap.save(favicon_path, "PNG")
                    self.display_shortcuts()
        except Exception as e:
            print(f"Error saving favicon: {e}")
        finally:
            view.deleteLater()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        self.overlay.setGeometry(0, 0, self.width(), self.height())

        self.update_background_scaling()

    def update_background_scaling(self):
        """Update the background scaling based on current size"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap and self.custom_bg_applied:
            scaled_pixmap = self.original_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.bg_label.setPixmap(scaled_pixmap)

    def set_default_background(self):
        pixmap_path = None
        if os.path.exists(BG2_IMG) and random.randint(1,1000)==1:
            pixmap_path = BG2_IMG
        elif os.path.exists(BG_IMG):
            pixmap_path = BG_IMG

        self.set_custom_background(pixmap_path)

    def set_custom_background(self, pixmap_or_path):
        pixmap = None
        if isinstance(pixmap_or_path, QPixmap):
            pixmap = pixmap_or_path
        elif isinstance(pixmap_or_path, str) and os.path.exists(pixmap_or_path):
            pixmap = QPixmap(pixmap_or_path)

        if pixmap and not pixmap.isNull():
            self.original_pixmap = pixmap

            scaled_pixmap = pixmap.scaled(
                self.size(),  
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            self.bg_label.setPixmap(scaled_pixmap)
            self.bg_label.setScaledContents(False)

            self.bg_label.setMinimumSize(1, 1)
            self.bg_label.setMaximumSize(16777215, 16777215)

            self.custom_bg_applied = True
        else:
            self.bg_label.setStyleSheet("background-color:#1e1e1e;")
            self.custom_bg_applied = False
            self.original_pixmap = None


    def load_fun_fact(self):
        if os.path.exists(FACTS_FILE):
            with open(FACTS_FILE, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
                if lines:
                    fact_text = random.choice(lines)
                    self.quote_label.setText(self.translator.tr("fun_fact", "{}").format(fact_text))
                    return
        self.quote_label.setText(self.translator.tr("fun_fact", "fun fact:").format(""))

    def load_shortcuts(self):
        shortcuts = []
        if os.path.exists(SHORTCUTS_FILE):
            try:
                with open(SHORTCUTS_FILE, "r", encoding="utf-8") as f:
                    shortcuts = json.load(f)
            except:
                pass
        return shortcuts

    def save_shortcuts(self):
        try:
            with open(SHORTCUTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.shortcuts, f, indent=2)
        except:
            pass

    def display_shortcuts(self):
        for i in reversed(range(self.shortcuts_layout.count())):
            widget = self.shortcuts_layout.itemAt(i).widget()
            if widget != self.add_shortcut_btn:
                widget.deleteLater()

        row, col = 0, 0
        max_cols = 8

        for shortcut in self.shortcuts:
            container = QWidget()
            container.setFixedSize(80, 90)
            container_layout = QStackedLayout(container)
            shortcut_widget = ShortcutWidget(
                shortcut['name'], shortcut['url'], self.parent_browser
            )
            container_layout.addWidget(shortcut_widget)

            remove_btn = QPushButton("x", container)
            remove_btn.setFixedSize(16, 16)
            remove_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: white;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: transparent;
                }
            """)
            remove_btn.move(container.width() - 20, 2)
            remove_btn.raise_()
            remove_btn.clicked.connect(lambda checked, url=shortcut['url']: self.remove_shortcut(url))

            self.shortcuts_layout.addWidget(container, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        self.shortcuts_layout.removeWidget(self.add_shortcut_btn)
        if len(self.shortcuts) < 24:
            self.shortcuts_layout.addWidget(self.add_shortcut_btn, row, col)
            self.add_shortcut_btn.setEnabled(len(self.shortcuts) < 24)
        else:
            self.add_shortcut_btn.setEnabled(False)

    def add_shortcut(self):
        if len(self.shortcuts) >= 24:
            return
        dialog = AddShortcutDialog(self, self.translator)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            shortcut_data = dialog.get_shortcut_data()
            if shortcut_data['name'] and shortcut_data['url']:
                url = shortcut_data['url']
                if not url.startswith(('http://','https://')):
                    url = 'https://' + url
                self.shortcuts.append({'name': shortcut_data['name'], 'url': url})
                self.save_shortcuts()
                self.display_shortcuts()
                self.download_favicon(url)

    def remove_shortcut(self, url):
        self.shortcuts = [s for s in self.shortcuts if s['url'] != url]
        self.save_shortcuts()
        self.display_shortcuts()

    def perform_search(self):
        q = self.search_bar.text().strip()
        if not q:
            return
        if self.parent_browser:
            search_url = self.parent_browser.get_search_url(q)
            self.parent_browser.add_tab(search_url)
        else:
            from urllib.parse import quote
            if '.' in q and ' ' not in q and not q.startswith(('http://','https://')):
                url = "https://"+q
            else:
                url = f"https://www.google.com/search?q={quote(q)}"
            parent = self.parent()
            while parent and not isinstance(parent, Browser):
                parent = parent.parent()
            if parent:
                parent.add_tab(url)

    def show_credits(self):
        credits_dialog = QDialog(self)
        credits_dialog.setWindowTitle(self.translator.tr("credits_title", "Cat Browser Credits"))
        credits_dialog.setFixedSize(700, 600)
        credits_dialog.setStyleSheet("""
            QDialog { background: #1a1a1a; color: white; }
            QLabel { color: white; font-size: 14px; }
            QPushButton {
                background: #0078d4; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-size: 14px; font-weight: bold; margin-top: 20px;
            }
            QPushButton:hover { background: #106ebe; }
        """)

        layout = QVBoxLayout(credits_dialog)
        title = QLabel(self.translator.tr("credits_title", "Cat Browser Credits"))
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        credits_text = QLabel()
        credits_text.setTextFormat(Qt.TextFormat.RichText)
        credits_text.setWordWrap(True)
        credits_text.setText(f"""
        <div style='text-align: center;'>
        <h3>{self.translator.tr('development_team', 'Development Team')}</h3>
        <p><b>anameless_guy - Discord</b> - {self.translator.tr('developer', 'dev')}</p>
        <h3>{self.translator.tr('translators', 'Translators')}</h3>
        <p><b>alex.ggiscool - Discord</b></p>
        <p><b>namelessperson.tar.xz - Discord</b></p>
        <p><b>bojl3l - Discord</b></p>
        <h3>{self.translator.tr('special_thanks', 'Special Thanks')}</h3>
        <p>PyQt6 Team  - {self.translator.tr('for_webengine', 'For the WebEngine')}</p>
        </div>
        """)
        credits_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(credits_text)

        close_btn = QPushButton(self.translator.tr("close", "Close"))
        close_btn.clicked.connect(credits_dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        credits_dialog.exec()


class InspectorWebPage(QWebEnginePage):
    def __init__(self, profile, parent):
        super().__init__(profile, parent)
        self.inspector_view = None
        self.parent_browser = None

    def set_parent_browser(self, browser):
        self.parent_browser = browser

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"js console: {message} (line {lineNumber})")

    def createWindow(self, type):
        if type == QWebEnginePage.WebWindowType.WebBrowserTab:
            if self.parent_browser:
                new_tab = self.parent_browser.add_tab("about:blank")
                if hasattr(new_tab, 'web_view') and new_tab.web_view:
                    return new_tab.web_view
            return InspectorWebView(self.profile())
        return super().createWindow(type)

class InspectorWebView(QWebEngineView):
    def __init__(self, profile, parent=None, browser=None):
        super().__init__(parent)
        self.parent_browser = browser
        self.inspector_page = InspectorWebPage(profile, self)
        self.inspector_page.set_parent_browser(browser)
        self.setPage(self.inspector_page)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()

        inspect_action = QAction("Inspect Element", menu)
        inspect_action.triggered.connect(self.inspect_element)
        menu.addAction(inspect_action)

        menu.exec(event.globalPos())

    def inspect_element(self):
        self.page().runJavaScript("""
            (function() {
                if (!window.__cat_inspector) {
                    window.__cat_inspector = true;
                    var style = document.createElement('style');
                    style.innerHTML = `
                        *:hover {
                            outline: 2px solid red !important;
                            outline-offset: -2px;
                            cursor: crosshair;
                        }
                    `;
                    document.head.appendChild(style);

                    document.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        var element = e.target;
                        var html = element.outerHTML.substring(0, 200);
                        var info = {
                            tag: element.tagName,
                            id: element.id,
                            className: element.className,
                            html: html,
                            xpath: getXPath(element)
                        };
                        window.__cat_last_inspected = info;

                        style.remove();
                        window.__cat_inspector = false;

                        console.log('Inspected element:', info);
                    }, true);

                    function getXPath(element) {
                        if (element.id !== '')
                            return '//*[@id="' + element.id + '"]';
                        if (element === document.body)
                            return '/html/body';
                        var ix = 0;
                        var siblings = element.parentNode.childNodes;
                        for (var i = 0; i < siblings.length; i++) {
                            var sibling = siblings[i];
                            if (sibling === element)
                                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                                ix++;
                        }
                    }
                }
            })();
        """)

        self.show_inspector_dialog()

    def show_inspector_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Element Inspector")
        dialog.setMinimumSize(600, 400)
        dialog.setStyleSheet("""
            QDialog {
                background: #2b2b2b;
                color: white;
            }
            QTextEdit {
                background: #1a1a1a;
                color: #00ff00;
                font-family: 'Monospace';
                font-size: 12px;
                border: 1px solid #444;
            }
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #106ebe;
            }
        """)

        layout = QVBoxLayout(dialog)

        self.inspector_text = QTextEdit()
        self.inspector_text.setReadOnly(True)
        layout.addWidget(self.inspector_text)

        button_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self.refresh_inspector(dialog))
        button_layout.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        self.refresh_inspector(dialog)
        dialog.exec()

    def refresh_inspector(self, dialog):
        self.page().runJavaScript("""
            (function() {
                if (window.__cat_last_inspected) {
                    return window.__cat_last_inspected;
                }
                return null;
            })();
        """, lambda result: self.display_inspector_result(result, dialog))

    def display_inspector_result(self, result, dialog):
        if result:
            text = f"Tag: {result.get('tag', 'N/A')}\n"
            text += f"ID: {result.get('id', 'N/A')}\n"
            text += f"Class: {result.get('className', 'N/A')}\n"
            text += f"XPath: {result.get('xpath', 'N/A')}\n"
            text += f"HTML Preview:\n{result.get('html', 'N/A')}..."
            self.inspector_text.setText(text)
        else:
            self.inspector_text.setText("No element inspected yet.\nClick 'Inspect Element' and then click on any element on the page.")

class Tab(QWidget):
    def __init__(self, profile, url="https://www.google.com", is_new_tab=False, browser=None, translator=None, theme_engine=None):
        super().__init__()
        self.is_new_tab = is_new_tab
        self.web_view = None
        self.profile = profile
        self.main_browser = browser
        self.translator = translator
        self.theme_engine = theme_engine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        if is_new_tab:
            self.new_tab_page = CustomNewTabPage(self.main_browser, self.translator, theme_engine)
            layout.addWidget(self.new_tab_page)
            self.web_view = None
        elif url and url.startswith("settings://"):
            label = QLabel("Invalid tab type")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            self.web_view = None
            self.new_tab_page = None
        else:
            self.web_view = InspectorWebView(profile, self, browser=self.main_browser)
            self.web_view.setUrl(QUrl(url) if url else QUrl("https://www.google.com"))

            if self.web_view.page():
                self.web_view.page().fullScreenRequested.connect(self.handle_fullscreen_request)

            layout.addWidget(self.web_view)
            self.new_tab_page = None

        self.setLayout(layout)

    def handle_fullscreen_request(self, request):
        request.accept()
        if request.toggleOn():
            self.main_browser.showFullScreen()
            if hasattr(self.main_browser, 'nav_toolbar'):
                self.main_browser.nav_toolbar.hide()
        else:
            self.main_browser.showNormal()
            if hasattr(self.main_browser, 'nav_toolbar'):
                self.main_browser.nav_toolbar.show()

class SetupWizard(QDialog):
    finished = Signal()

    def __init__(self, browser):
        super().__init__()
        print("setup: starting...")
        self.browser = browser
        self.translator = browser.translator
        self.setWindowTitle(self.translator.tr("setup_wizard", "Setup Cat Browser"))
        self.setFixedSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
                color: white;
            }
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: 500;
            }
            QComboBox, QCheckBox {
                color: white;
                font-size: 14px;
            }
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background: #106ebe;
            }
            QPushButton:pressed {
                background: #005a9e;
            }
        """)

        self.setup_steps = []
        self.current_step = 0
        self.results = {}

        self.create_steps()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.show_step(0)

    def create_steps(self):
        step1_widget = QWidget()
        step1_layout = QVBoxLayout(step1_widget)
        step1_layout.setSpacing(20)

        if os.path.exists(WELCOME_IMG):
            image_label = QLabel()
            pixmap = QPixmap(WELCOME_IMG)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(400, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                image_label.setPixmap(pixmap)
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                step1_layout.addWidget(image_label)

        self.title1 = QLabel(self.translator.tr("welcome_title", "cat browser (real)"))
        self.title1.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4;")
        self.title1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step1_layout.addWidget(self.title1)

        self.desc1 = QLabel(self.translator.tr("setup_step1_desc", "Let's set up your browser. First, choose your preferred search engine:"))
        self.desc1.setWordWrap(True)
        step1_layout.addWidget(self.desc1)

        self.search_combo = QComboBox()
        self.search_combo.setStyleSheet("""
            QComboBox {
                background: #2d2d2d;
                color: white;
                border: 2px solid #404040;
                border-radius: 8px;
                padding: 10px;
                font-size: 16px;
            }
        """)
        for engine in self.browser.search_engines.keys():
            self.search_combo.addItem(engine)
        step1_layout.addWidget(self.search_combo)

        self.setup_steps.append(step1_widget)
        step2_widget = QWidget()
        step2_layout = QVBoxLayout(step2_widget)
        step2_layout.setSpacing(20)

        self.title2 = QLabel(self.translator.tr("setup_step2_title", "Choose Language"))
        self.title2.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4;")
        self.title2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step2_layout.addWidget(self.title2)

        self.desc2 = QLabel(self.translator.tr("setup_step2_desc", "Select your preferred language for the browser interface:"))
        self.desc2.setWordWrap(True)
        step2_layout.addWidget(self.desc2)

        self.language_combo = QComboBox()
        self.language_combo.setStyleSheet("""
            QComboBox {
                background: #2d2d2d;
                color: white;
                border: 2px solid #404040;
                border-radius: 8px;
                padding: 10px;
                font-size: 16px;
            }
        """)
        for lang in self.translator.languages.keys():
            self.language_combo.addItem(lang)


        current_index = self.language_combo.findText(self.translator.current_lang)
        if current_index >= 0:
            self.language_combo.setCurrentIndex(current_index)


        self.language_combo.currentTextChanged.connect(self.update_language)

        step2_layout.addWidget(self.language_combo)
        step2_layout.addStretch()

        self.setup_steps.append(step2_widget)


        step3_widget = QWidget()
        step3_layout = QVBoxLayout(step3_widget)
        step3_layout.setSpacing(20)

        self.title3 = QLabel(self.translator.tr("setup_step3_title", "Password Import"))
        self.title3.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4;")
        self.title3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step3_layout.addWidget(self.title3)

        self.desc3 = QLabel(self.translator.tr("setup_step3_desc", "Would you like to import passwords from a CSV file?\n\nYou can skip this and do it later from Settings."))
        self.desc3.setWordWrap(True)
        step3_layout.addWidget(self.desc3)


        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        self.import_btn = QPushButton(self.translator.tr("import_csv", "Import CSV"))
        self.skip_btn = QPushButton(self.translator.tr("skip", "Skip"))

        self.import_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background: #106ebe;
            }
            QPushButton:pressed {
                background: #005a9e;
            }
        """)

        self.skip_btn.setStyleSheet("""
            QPushButton {
                background: #555;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background: #666;
            }
            QPushButton:pressed {
                background: #444;
            }
        """)

        self.import_btn.clicked.connect(self.import_passwords_dialog)
        self.skip_btn.clicked.connect(self.skip_passwords)

        button_layout.addStretch()
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.skip_btn)
        button_layout.addStretch()

        step3_layout.addLayout(button_layout)
        step3_layout.addStretch()

        self.setup_steps.append(step3_widget)


        step4_widget = QWidget()
        step4_layout = QVBoxLayout(step4_widget)
        step4_layout.setSpacing(20)

        self.title4 = QLabel(self.translator.tr("setup_step4_title", "Welcome Screen"))
        self.title4.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4;")
        self.title4.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step4_layout.addWidget(self.title4)

        self.desc4 = QLabel(self.translator.tr("setup_step4_desc", "Show welcome screen on startup?\n\nYou can change this later in Settings."))
        self.desc4.setWordWrap(True)
        step4_layout.addWidget(self.desc4)

        self.welcome_checkbox = QCheckBox(self.translator.tr("show_welcome", "Show welcome screen on startup"))
        self.welcome_checkbox.setChecked(True)
        self.welcome_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
        """)
        step4_layout.addWidget(self.welcome_checkbox)
        step4_layout.addStretch()
        self.setup_steps.append(step4_widget)


        step5_widget = QWidget()
        step5_layout = QVBoxLayout(step5_widget)
        step5_layout.setSpacing(20)

        self.title5 = QLabel(self.translator.tr("setup_complete", "Setup Complete! "))
        self.title5.setStyleSheet("font-size: 28px; font-weight: bold; color: #00cc00;")
        self.title5.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step5_layout.addWidget(self.title5)

        self.desc5 = QLabel(self.translator.tr("setup_ready", "Your browser is ready to use!\n\nEnjoy your stay with Cat Browser!"))
        self.desc5.setStyleSheet("font-size: 18px;")
        self.desc5.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc5.setWordWrap(True)
        step5_layout.addWidget(self.desc5)




        self.credits_btn = QPushButton(self.translator.tr("see_credits", "See Credits"))
        self.credits_btn.setStyleSheet("""
            QPushButton {
                background: #555;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                margin-top: 20px;
            }
            QPushButton:hover {
                background: #666;
            }
            QPushButton:pressed {
                background: #444;
            }
        """)
        self.credits_btn.clicked.connect(self.show_credits)
        step5_layout.addWidget(self.credits_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        step5_layout.addStretch()
        self.setup_steps.append(step5_widget)

    def update_language(self, lang_name):

        print(f"settings: updating language to {lang_name}")
        if self.translator.set_language(lang_name):

            self.setWindowTitle(self.translator.tr("setup_wizard", "Setup Cat Browser"))


            self.title1.setText(self.translator.tr("welcome_title", "cat browser (real)"))
            self.desc1.setText(self.translator.tr("setup_step1_desc", "Let's set up your browser. First, choose your preferred search engine:"))

            self.title2.setText(self.translator.tr("setup_step2_title", "Choose Language"))
            self.desc2.setText(self.translator.tr("setup_step2_desc", "Select your preferred language for the browser interface:"))

            self.title3.setText(self.translator.tr("setup_step3_title", "Password Import"))
            self.desc3.setText(self.translator.tr("setup_step3_desc", "Would you like to import passwords from a CSV file?\n\nYou can skip this and do it later from Settings."))
            self.import_btn.setText(self.translator.tr("import_csv", "Import CSV"))
            self.skip_btn.setText(self.translator.tr("skip", "Skip"))

            self.title4.setText(self.translator.tr("setup_step4_title", "Welcome Screen"))
            self.desc4.setText(self.translator.tr("setup_step4_desc", "Show welcome screen on startup?\n\nYou can change this later in Settings."))
            self.welcome_checkbox.setText(self.translator.tr("show_welcome", "Show welcome screen on startup"))

            self.title5.setText(self.translator.tr("setup_complete", "Setup Complete! "))
            self.desc5.setText(self.translator.tr("setup_ready", "Your browser is ready to use!\n\nEnjoy your stay with Cat Browser!"))
            self.credits_btn.setText(self.translator.tr("see_credits", "See Credits"))


            self.update_navigation_buttons()

    def update_navigation_buttons(self):

        pass

    def show_step(self, step_index):

        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                widget = child.widget()
                widget.setParent(None)


        if step_index < len(self.setup_steps):
            self.layout.addWidget(self.setup_steps[step_index])


        if step_index != 2:
            button_layout = QHBoxLayout()

            if step_index > 0:
                back_text = self.translator.tr("back", "Back")
                back_btn = QPushButton(back_text)
                back_btn.clicked.connect(lambda checked, idx=step_index-1: self.show_step(idx))
                button_layout.addWidget(back_btn)

            button_layout.addStretch()

            if step_index < len(self.setup_steps) - 1:
                if step_index < len(self.setup_steps) - 2:
                    next_text = self.translator.tr("next", "Next")
                else:
                    next_text = self.translator.tr("finish", "Finish")
                next_btn = QPushButton(next_text)
                next_btn.clicked.connect(lambda checked, idx=step_index: self.next_step(idx))
                button_layout.addWidget(next_btn)
            else:
                finish_text = self.translator.tr("start_browsing", "Start Browsing!")
                finish_btn = QPushButton(finish_text)
                finish_btn.clicked.connect(self.finish_setup)
                button_layout.addWidget(finish_btn)

            self.layout.addLayout(button_layout)

        self.current_step = step_index

    def next_step(self, current_step):
        if current_step == 0:
            self.results['search_engine'] = self.search_combo.currentText()
        elif current_step == 1:

            selected_lang = self.language_combo.currentText()
            self.results['language'] = selected_lang
        elif current_step == 3:
            self.results['show_welcome'] = self.welcome_checkbox.isChecked()

        if current_step != 2:
            self.show_step(current_step + 1)

    def skip_passwords(self):

        self.show_step(3)

    def show_credits(self):

        credits_dialog = QDialog(self)
        credits_dialog.setWindowTitle(self.translator.tr("credits_title", "Cat Browser Credits"))
        credits_dialog.setFixedSize(700, 600)
        credits_dialog.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
                color: white;
            }
            QLabel {
                color: white;
                font-size: 14px;
            }
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                margin-top: 20px;
            }
            QPushButton:hover {
                background: #106ebe;
            }
        """)

        layout = QVBoxLayout(credits_dialog)

        title = QLabel(self.translator.tr("credits_title", "Cat Browser Credits"))
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)


        credits_text = QLabel()
        credits_text.setTextFormat(Qt.TextFormat.RichText)
        credits_text.setWordWrap(True)
        credits_text.setText(f"""
        <div style='text-align: center;'>
        <h3>{self.translator.tr('development_team', 'Development Team')}</h3>
        <p><b>anameless_guy - Discord</b> - {self.translator.tr('developer', 'dev')}</p>
        <h3>{self.translator.tr('translators', 'Translators')}</h3>
        <p><b>alex.ggiscool - Discord</b></p>
        <p><b>namelessperson.tar.xz - Discord</b></p>
        <p><b>bojl3l - Discord</b></p>

        <h3>{self.translator.tr('special_thanks', 'Special Thanks')}</h3>
        <p>PyQt6 Team  - {self.translator.tr('for_webengine', 'For the WebEngine')}</p>

        </div>
        """)
        credits_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(credits_text)

        close_text = self.translator.tr("close", "Close")
        close_btn = QPushButton(close_text)
        close_btn.clicked.connect(credits_dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        credits_dialog.exec()

    def finish_setup(self):

        if 'search_engine' in self.results:
            self.browser.set_search_engine(self.results['search_engine'])

        if 'language' in self.results:
            self.browser.translator.set_language(self.results['language'])
            self.browser.settings['language'] = self.results['language']

        if 'show_welcome' in self.results:
            self.browser.settings['show_welcome_screen'] = self.results['show_welcome']

        self.browser.save_settings()


        with open(SETUP_FILE, 'w') as f:
            json.dump({'completed': True}, f)

        self.finished.emit()
        self.accept()

    def import_passwords_dialog(self):
        title = self.translator.tr("import_passwords", "Import Passwords")
        file_filter = self.translator.tr("csv_files", "CSV Files (*.csv)")
        path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)

        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if "name" in row and "username" in row and "password" in row:
                            self.browser.passwords[row["name"]] = {
                                "user": row["username"],
                                "pass": row["password"]
                            }
                self.browser.save_passwords()
                success_title = self.translator.tr("success", "Success")
                success_msg = self.translator.tr("passwords_imported", "Passwords imported successfully!")
                QMessageBox.information(self, success_title, success_msg)
            except Exception as e:
                error_title = self.translator.tr("error", "Error")
                error_msg = self.translator.tr("import_failed", "Failed to import passwords: {}").format(str(e))
                QMessageBox.warning(self, error_title, error_msg)


        self.show_step(3)

class Translator:
    def __init__(self):
        self.languages = {}
        self.current_lang = "English"
        self.load_languages()

    def load_languages(self):
        if os.path.exists(LANGUAGES_FILE):
            try:
                with open(LANGUAGES_FILE, 'r', encoding='utf-8') as f:
                    current_lang = None
                    current_dict = {}

                    for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith('[') and line.endswith(']'):
                            if current_lang and current_dict:
                                self.languages[current_lang] = current_dict
                            current_lang = line[1:-1]
                            current_dict = {}
                        elif '=' in line:
                            key, value = line.split('=', 1)
                            current_dict[key.strip()] = value.strip()

                    if current_lang and current_dict:
                        self.languages[current_lang] = current_dict

            except Exception as e:
                print(f"settings: error loading languages: {e}")

    def set_language(self, lang):
        if lang in self.languages:
            self.current_lang = lang
            return True
        return False

    def get(self, key, default=None):
        if self.current_lang in self.languages:
            return self.languages[self.current_lang].get(key, default)
        return default

    def tr(self, key, *args):
        text = self.get(key, key)
        if args:
            try:
                text = text.format(*args)
            except:
                pass
        return text

class AddShortcutDialog(QDialog):
    def __init__(self, parent=None, translator=None):
        super().__init__(parent)
        self.translator = translator or Translator()
        self.setWindowTitle(self.translator.tr("add_shortcut", "Add Shortcut"))
        self.setFixedSize(400, 200)
        self.setStyleSheet("""
            QDialog { background: #2b2b2b; color: white; }
            QLabel { color: white; font-size: 14px; }
            QLineEdit {
                background: #3c3c3c;
                border: 1px solid #555;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #0078d4; }
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #106ebe; }
            QPushButton:pressed { background: #005a9e; }
            QPushButton:disabled {
                background: #555;
                color: #888;
            }
        """)

        layout = QVBoxLayout(self)

        name_layout = QVBoxLayout()
        name_label = QLabel(self.translator.tr("shortcut_name", "Shortcut Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(self.translator.tr("enter_name", "Enter shortcut name..."))
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        url_layout = QVBoxLayout()
        url_label = QLabel(self.translator.tr("url", "URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(self.translator.tr("enter_url", "https://example.com"))
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton(self.translator.tr("add_shortcut", "Add Shortcut"))
        self.cancel_button = QPushButton(self.translator.tr("cancel", "Cancel"))

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.name_input.textChanged.connect(self.validate_inputs)
        self.url_input.textChanged.connect(self.validate_inputs)
        self.validate_inputs()

    def validate_inputs(self):
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        self.ok_button.setEnabled(bool(name) and bool(url))

    def get_shortcut_data(self):
        return {
            'name': self.name_input.text().strip(),
            'url': self.url_input.text().strip()
        }

class ShortcutWidget(QWidget):
    def __init__(self, name, url, browser, parent=None):
        super().__init__(parent)
        self.name = name
        self.url = url
        self.browser = browser
        self.setFixedSize(80, 90)
        self.setStyleSheet("""
            ShortcutWidget {
                background: rgba(60, 60, 60, 150);
                border: 1px solid #555;
                border-radius: 8px;
            }
            ShortcutWidget:hover {
                background: rgba(80, 80, 80, 150);
                border: 1px solid #0078d4;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border-radius: 6px;
            }
        """)

        self.load_favicon()

        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("color: white; font-size: 11px;")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumWidth(70)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label)

    def load_favicon(self):
        domain = self.extract_domain(self.url)
        if domain:
            favicon_path = os.path.join(FAVICON_DIR, f"{domain}.png")
            if os.path.exists(favicon_path):
                pixmap = QPixmap(favicon_path)
                if not pixmap.isNull():
                    self.icon_label.setPixmap(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    return

        fallback_text = self.name[0].upper() if self.name else "?"
        self.icon_label.setText(fallback_text)
        self.icon_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                background: #0078d4;
                border-radius: 16px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
        """)

    def extract_domain(self, url):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.netloc:
                return parsed.netloc.replace('www.', '')
        except:
            pass
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.url:
                self.browser.add_tab(self.url)
        super().mousePressEvent(event)

class ModernTabBar(QTabBar):
    def __init__(self):
        super().__init__()
        self.setDrawBase(False)
        self.setExpanding(False)

    def tabSizeHint(self, index):
        return QSize(200, 35)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for index in range(self.count()):
            rect = self.tabRect(index)
            close_rect = QRect(rect.right() - 20, rect.center().y() - 6, 12, 12)
            if close_rect.contains(self.mapFromGlobal(self.cursor().pos())):
                painter.setBrush(Qt.GlobalColor.red)
                painter.setPen(Qt.GlobalColor.red)
                painter.drawEllipse(close_rect)
                painter.setPen(QPen(Qt.GlobalColor.white, 2))
            else:
                painter.setPen(QPen(Qt.GlobalColor.white, 1.5))
            painter.drawLine(close_rect.topLeft(), close_rect.bottomRight())
            painter.drawLine(close_rect.topRight(), close_rect.bottomLeft())

    def mousePressEvent(self, event):
        for index in range(self.count()):
            rect = self.tabRect(index)
            close_rect = QRect(rect.right() - 20, rect.center().y() - 6, 12, 12)
            if close_rect.contains(event.pos()):
                self.tabCloseRequested.emit(index)
                return
        super().mousePressEvent(event)

class WelcomeScreen(QWidget):
    finished = Signal()

    def __init__(self, duration=3000):
        super().__init__()
        print("splash screen: starting...")

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #000000;")
        self.setFixedSize(659, 460)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.video_widget = QVideoWidget()
        self.video_widget.setFixedSize(659, 460)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        video_path = os.path.join(BASE_PATH, "splash.mp4")
        print(f"splash screen: looking for video at {video_path}")
        if os.path.exists(video_path):
            print("splash screen: video found")
            self.media_player.setSource(QUrl.fromLocalFile(video_path))
            self.media_player.setVideoOutput(self.video_widget)
            self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
            self.media_player.play()
            print("splash screen: video playing")
        else:
            print(f"splash screen: error playing video {video_path}")
            self.finished.emit()
            QTimer.singleShot(100, self.close)
            return

        layout.addWidget(self.video_widget)
        self.setLayout(layout)
        self.duration = duration

        self.close_timer = QTimer()
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close_splash)
        self.close_timer.start(duration)


    def on_media_status_changed(self, status):
        from PyQt6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()
            self.close_splash()

    def close_splash(self):

        print("splash screen:: video ended")
        if hasattr(self, 'close_timer'):
            self.close_timer.stop()
        if hasattr(self, 'media_player'):
            self.media_player.stop()
        self.finished.emit()
        self.close()

    def closeEvent(self, event):


        self.close_splash()
        event.accept()

class SettingsTab(QWidget):
    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.translator = browser.translator

        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(10,10,10,10)
        self.main_layout.setSpacing(15)

        title = QLabel(self.translator.tr("settings", "Settings"))
        title.setStyleSheet("color:white;font-size:24px;font-weight:bold;")
        self.main_layout.addWidget(title)

        tab_count_label = QLabel(self.translator.tr("tabs_count", "{}").format(self.browser.tabs.count()))
        tab_count_label.setStyleSheet("color:white;font-size:16px;")
        self.main_layout.addWidget(tab_count_label)

        general_group = QGroupBox(self.translator.tr("general", "General Settings"))
        general_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        general_layout = QFormLayout(general_group)

        language_label = QLabel(self.translator.tr("language", "Language:"))
        self.language_combo = QComboBox()
        self.language_combo.setStyleSheet("""
            QComboBox {
                background: #3c3c3c;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background: #3c3c3c;
                color: white;
                border: 1px solid #555;
                selection-background-color: #0078d4;
            }
        """)

        for lang in self.translator.languages.keys():
            self.language_combo.addItem(lang)

        current_index = self.language_combo.findText(self.translator.current_lang)
        if current_index >= 0:
            self.language_combo.setCurrentIndex(current_index)

        self.language_combo.currentTextChanged.connect(self.on_language_changed)
        general_layout.addRow(language_label, self.language_combo)

        search_label = QLabel(self.translator.tr("search_engine", "Search Engine:"))
        self.search_combo = QComboBox()
        self.search_combo.setStyleSheet(self.language_combo.styleSheet())

        for engine_name in self.browser.search_engines.keys():
            self.search_combo.addItem(engine_name)

        current_engine = self.browser.current_search_engine
        engine_index = self.search_combo.findText(current_engine)
        if engine_index >= 0:
            self.search_combo.setCurrentIndex(engine_index)

        self.search_combo.currentTextChanged.connect(self.on_search_engine_changed)
        general_layout.addRow(search_label, self.search_combo)

        theme_label = QLabel(self.translator.tr("theme", "Theme:"))
        theme_container = QWidget()
        theme_container_layout = QVBoxLayout(theme_container)
        theme_container_layout.setContentsMargins(0,0,0,0)
        theme_container_layout.setSpacing(5)

        self.theme_combo = QComboBox()
        self.theme_combo.setStyleSheet(self.language_combo.styleSheet())
        self.theme_combo.addItem(self.translator.tr("default_theme", "Default Theme"))

        for theme_name in self.browser.themes.keys():
            self.theme_combo.addItem(theme_name)

        current_theme = self.browser.settings.get("theme", self.translator.tr("default_theme", "Default Theme"))
        theme_index = self.theme_combo.findText(current_theme)
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)

        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        theme_container_layout.addWidget(self.theme_combo)


        general_layout.addRow(theme_label, theme_container)
        self.main_layout.addWidget(general_group)

        startup_group = QGroupBox(self.translator.tr("startup_settings", "Startup Settings"))
        startup_group.setStyleSheet(general_group.styleSheet())
        startup_layout = QVBoxLayout(startup_group)

        self.welcome_checkbox = QCheckBox(self.translator.tr("show_welcome", "Show welcome screen on startup"))
        self.welcome_checkbox.setChecked(self.browser.settings.get("show_welcome_screen", True))
        self.welcome_checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
                font-size: 14px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555;
                border-radius: 3px;
                background: #3c3c3c;
            }
            QCheckBox::indicator:checked {
                background: #0078d4;
                border: 2px solid #0078d4;
            }
            QCheckBox::indicator:checked:hover {
                background: #106ebe;
                border: 2px solid #106ebe;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #777;
            }
        """)
        self.welcome_checkbox.stateChanged.connect(self.on_welcome_setting_changed)
        startup_layout.addWidget(self.welcome_checkbox)

        self.restore_session_checkbox = QCheckBox(self.translator.tr("restore_session", "Restore tabs from previous session"))
        self.restore_session_checkbox.setChecked(self.browser.settings.get("restore_session", True))
        self.restore_session_checkbox.setStyleSheet(self.welcome_checkbox.styleSheet())
        self.restore_session_checkbox.stateChanged.connect(self.on_restore_session_changed)
        startup_layout.addWidget(self.restore_session_checkbox)

        self.main_layout.addWidget(startup_group)

        memory_group = QGroupBox(self.translator.tr("memory_settings", "Memory Settings"))
        memory_group.setStyleSheet(general_group.styleSheet())
        memory_layout = QVBoxLayout(memory_group)

        self.memory_saver_checkbox = QCheckBox(self.translator.tr("memory_saver", "Memory Saver (unloads inactive tabs after 5 minutes)"))
        self.memory_saver_checkbox.setChecked(self.browser.settings.get("memory_saver", False))
        self.memory_saver_checkbox.setStyleSheet(self.welcome_checkbox.styleSheet())
        self.memory_saver_checkbox.stateChanged.connect(self.on_memory_saver_changed)
        memory_layout.addWidget(self.memory_saver_checkbox)

        self.main_layout.addWidget(memory_group)

        extensions_group = QGroupBox(self.translator.tr("extensions", "Extensions"))
        extensions_group.setStyleSheet(general_group.styleSheet())
        extensions_layout = QVBoxLayout(extensions_group)

        self.ext_text = QTextEdit()
        self.ext_text.setReadOnly(True)
        self.ext_text.setMaximumHeight(150)
        self.ext_text.setStyleSheet("""
            QTextEdit {
                background: #2b2b2b;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
        """)
        extensions_layout.addWidget(self.ext_text)
        self.update_extensions_view()
        self.main_layout.addWidget(extensions_group)

        passwords_group = QGroupBox(self.translator.tr("passwords", "Passwords"))
        passwords_group.setStyleSheet(general_group.styleSheet())
        passwords_layout = QVBoxLayout(passwords_group)

        pw_buttons_layout = QHBoxLayout()
        self.import_btn = QPushButton(self.translator.tr("import_csv", "Import CSV"))
        self.export_btn = QPushButton(self.translator.tr("export_csv", "Export CSV"))

        self.import_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #106ebe; }
            QPushButton:pressed { background: #005a9e; }
        """)
        self.export_btn.setStyleSheet(self.import_btn.styleSheet())

        self.import_btn.clicked.connect(self.import_csv)
        self.export_btn.clicked.connect(self.export_csv)

        pw_buttons_layout.addWidget(self.import_btn)
        pw_buttons_layout.addWidget(self.export_btn)
        passwords_layout.addLayout(pw_buttons_layout)

        self.pw_text = QTextEdit()
        self.pw_text.setReadOnly(True)
        self.pw_text.setMaximumHeight(150)
        self.pw_text.setStyleSheet(self.ext_text.styleSheet())
        passwords_layout.addWidget(self.pw_text)
        self.update_pw_view()
        self.main_layout.addWidget(passwords_group)

        history_group = QGroupBox(self.translator.tr("history", "History"))
        history_group.setStyleSheet(general_group.styleSheet())
        history_layout = QVBoxLayout(history_group)

        self.hist_text = QTextEdit()
        self.hist_text.setReadOnly(True)
        self.hist_text.setMaximumHeight(150)
        self.hist_text.setStyleSheet(self.ext_text.styleSheet())
        history_layout.addWidget(self.hist_text)
        self.update_history_view()
        self.main_layout.addWidget(history_group)

        self.main_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.main_widget)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        self.setLayout(main_layout)

    def on_language_changed(self, lang):
        if self.translator.set_language(lang):
            self.browser.save_settings()
            self.browser.update_language()

    def on_welcome_setting_changed(self, state):
        self.browser.settings["show_welcome_screen"] = (state == Qt.CheckState.Checked.value)
        self.browser.save_settings()

    def on_search_engine_changed(self, engine_name):
        self.browser.set_search_engine(engine_name)

    def on_theme_changed(self, theme_name):
        self.browser.set_theme(theme_name)

    def on_memory_saver_changed(self, state):
        self.browser.settings["memory_saver"] = (state == Qt.CheckState.Checked.value)
        self.browser.save_settings()
        self.browser.enable_memory_saver(state == Qt.CheckState.Checked.value)

    def on_restore_session_changed(self, state):
        self.browser.settings["restore_session"] = (state == Qt.CheckState.Checked.value)
        self.browser.save_settings()

    def update_extensions_view(self):
        if not self.browser.extensions:
            self.ext_text.setText(self.translator.tr("no_extensions", "No extensions loaded."))
        else:
            ext_info = self.translator.tr("loaded_extensions", "Loaded Extensions:\n\n")
            for ext_name, ext_data in self.browser.extensions.items():
                ext_info += f"• {ext_name}\n"
                ext_info += self.translator.tr("description", "  Description: {}").format(ext_data.get('description', 'No description')) + "\n"
                ext_info += self.translator.tr("version", "  Version: {}").format(ext_data.get('version', '1.0')) + "\n"
                ext_info += f"  Script: {ext_data.get('script', 'No script')}\n\n"
            self.ext_text.setText(ext_info)

    def update_pw_view(self):
        s = ""
        for site,info in self.browser.passwords.items():
            s += f"{site} - {info['user']} / {info['pass']}\n"
        self.pw_text.setText(s)

    def update_history_view(self):
        self.hist_text.setText("\n".join(self.browser.history))

    def import_csv(self):
        path,_ = QFileDialog.getOpenFileName(self,
            self.translator.tr("import_passwords", "Import Passwords"),
            "",
            self.translator.tr("csv_files", "CSV Files (*.csv)"))
        if path:
            with open(path,"r",encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.browser.passwords[row["name"]] = {"user":row["username"], "pass":row["password"]}
            self.update_pw_view()

    def export_csv(self):
        path,_ = QFileDialog.getSaveFileName(self,
            self.translator.tr("export_passwords", "Export Passwords"),
            "",
            self.translator.tr("csv_files", "CSV Files (*.csv)"))
        if path:
            with open(path,"w",newline="",encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["name","url","username","password","note"])
                for name,info in self.browser.passwords.items():
                    writer.writerow([name,"",info["user"],info["pass"],""])
            self.update_pw_view()

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cat browser")
        self.resize(1280,800)
        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self.check_browser_health)
        self.watchdog_timer.start(30000)
        self.translator = Translator()
        self.search_engines = {
            "Google": "https://www.google.com/search?q={}",
            "Bing": "https://www.bing.com/search?q={}",
            "DuckDuckGo": "https://duckduckgo.com/?q={}",
            "Yahoo": "https://search.yahoo.com/search?p={}"
        }

        self.themes = {}
        self.passwords = self.load_passwords()
        self.history = self.load_history()
        self.extensions = {}
        self.current_theme = None
        self.current_search_engine = self.load_search_engine()
        self.settings = self.load_settings()

        lang = self.settings.get("language", "English")
        self.translator.set_language(lang)

        self.rpc = None
        self.init_discord_rpc()

        self.profile = QWebEngineProfile("cat_profile")
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.setPersistentStoragePath(DATA_DIR)
        self.profile.downloadRequested.connect(self.on_download)
        default_settings = self.profile.settings()
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, True)
        default_settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, False)

        default_settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)

        self.memory_saver_enabled = self.settings.get("memory_saver", False)
        self.tab_last_accessed = {}
        self.memory_saver_timer = QTimer()
        if self.memory_saver_enabled:
            self.memory_saver_timer.timeout.connect(self.cleanup_inactive_tabs)
            self.memory_saver_timer.start(60000)

        self.themes = {}
        self.load_themes()
        self.theme_engine = ThemeEngine(self)
        self.load_extensions()
        self.inject_extensions_into_profile()

        self.setup_ui()
        self.apply_current_theme()

        if self.settings.get("restore_session", True):
            self.restore_session()
        else:
            self.add_tab(is_new_tab=True)

    def check_browser_health(self):
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            if memory_mb > 2000:
                print(f"browser: high memory usage {memory_mb:.2f} mb, cleaning up...")
                self.force_cleanup_tabs()

        except ImportError:
            pass
        except Exception as e:
            print(f"watchdog error: {e}")

    def force_cleanup_tabs(self):
        current_time = datetime.now()

        for i in range(self.tabs.count()):
            if i == self.tabs.currentIndex():
                continue

            tab = self.tabs.widget(i)
            if hasattr(tab, 'browser') and tab.browser:
                tab_id = id(tab)
                last_access = self.tab_last_accessed.get(tab_id)

                if last_access and (current_time - last_access).seconds > 60:
                    self.unload_tab_content(i)

    def cleanup_inactive_tabs(self):
        if not self.memory_saver_enabled:
            return

        current_time = datetime.now()
        inactive_threshold = timedelta(minutes=5)

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)

            if hasattr(tab, 'web_view') and tab.web_view:
                tab_id = id(tab)
                last_access = self.tab_last_accessed.get(tab_id)

                if last_access:
                    if current_time - last_access > inactive_threshold:
                        if self.tabs.currentIndex() != i:
                            self.unload_tab_content(i)
                else:
                    self.tab_last_accessed[tab_id] = current_time


    def setup_webengine_crash_handler(self):
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu-compositing --enable-gpu-rasterization --disable-software-rasterizer"

        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] += " --max_old_space_size=4096"

        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] += " --disable-features=UseChromeOSDirectVideoDecoder"

        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] += " --enable-vulkan"

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabBar(ModernTabBar())
        self.tabs.setTabsClosable(True)
        self.tabs.setStyleSheet("QTabBar::close-button {width:0;height:0;image:none;}")
        self.tabs.tabCloseRequested.connect(self.close_tab_with_checks)
        self.tabs.currentChanged.connect(self.update_url_bar)
        main_layout.addWidget(self.tabs)

        self.nav_toolbar = QToolBar()
        self.nav_toolbar.setMovable(False)
        main_layout.insertWidget(0, self.nav_toolbar)

        for text,func in [("◀",lambda: self.current_browser().back() if self.current_browser() else None),
                        ("▶",lambda: self.current_browser().forward() if self.current_browser() else None),
                        ("↻",lambda: self.current_browser().reload() if self.current_browser() else None),
                        ("⚙", self.open_settings_tab),
                        ("+",lambda: self.add_tab(is_new_tab=True))]:
            btn = QPushButton(text)
            btn.setFixedSize(32,32)
            btn.clicked.connect(func)
            self.nav_toolbar.addWidget(btn)

        self.url_bar = QLineEdit()
        self.update_url_bar_placeholder()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.nav_toolbar.addWidget(self.url_bar)

        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

    def load_themes(self):
        print(f"theme system: loading themes")
        print(f"themes directory: {THEMES_DIR}")

        if not os.path.exists(THEMES_DIR):
            print("theme system: themes directory doesnt exist")
            return
        try:
            if hasattr(self, 'theme_engine'):
                self.theme_engine.update_new_tab_theme()
        except Exception as e:
            print(f"theme system: could not update new tab for the theme: {e}")


        for theme_folder in os.listdir(THEMES_DIR):
            theme_path = os.path.join(THEMES_DIR, theme_folder)
            if os.path.isdir(theme_path):
                manifest_path = os.path.join(theme_path, "manifest.json")

                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)

                        theme_name = manifest.get('name', theme_folder)
                        theme_type = manifest.get('type', 'full')
                        theme_file = manifest.get('theme_file', 'theme.qss')

                        qss_path = os.path.join(theme_path, theme_file)
                        has_qss = os.path.exists(qss_path)

                        font_path = os.path.join(theme_path, "font.ttf")
                        has_font = os.path.exists(font_path)

                        has_images = False
                        image_files = ['back.png', 'forward.png', 'reload.png', 'settings.png',
                                    'plus.png', 'magnify.png', 'checkbox_checked.png',
                                    'checkbox_unchecked.png']
                        for img in image_files:
                            if os.path.exists(os.path.join(theme_path, img)):
                                has_images = True
                                break

                        theme_data = {
                            'name': theme_name,
                            'path': theme_path,
                            'has_qss': has_qss,
                            'has_font': has_font,
                            'has_images': has_images,
                            'type': theme_type,
                            'theme_file': theme_file
                        }

                        if has_qss:
                            try:
                                with open(qss_path, 'r', encoding='utf-8') as f:
                                    theme_data['css_content'] = f.read()
                                print(f"theme system: loaded theme {theme_name} (QSS: {has_qss}, Font: {has_font}, Images: {has_images})")
                            except Exception as e:
                                theme_data['has_qss'] = False
                        else:
                            print(f"theme system: theme {theme_name} has no qss file at: {qss_path}")

                        self.themes[theme_name] = theme_data

                    except Exception as e:
                        print(f"theme system: error loading theme {theme_folder}: {e}")

        print(f"theme system: themes loaded: {len(self.themes)}")
        print(f"theme system: theme names: {list(self.themes.keys())}")

    def enable_memory_saver(self, enabled):
        self.memory_saver_enabled = enabled
        self.settings["memory_saver"] = enabled
        self.save_settings()

        if enabled:
            if not self.memory_saver_timer.isActive():
                self.memory_saver_timer.timeout.connect(self.cleanup_inactive_tabs)
                self.memory_saver_timer.start(60000)
        else:
            self.memory_saver_timer.stop()

    def close_tab_with_checks(self, i):
        tab = self.tabs.widget(i)

        if isinstance(tab, SettingsTab):
            if self.tabs.count() <= 1:
                self.add_tab(is_new_tab=True)

            self.tabs.removeTab(i)
        else:
            self.close_tab(i)

    def cleanup_inactive_tabs(self):
        if not self.memory_saver_enabled:
            return

        current_time = datetime.now()
        inactive_threshold = timedelta(minutes=5)

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)

            if hasattr(tab, 'browser') and tab.browser:
                tab_id = id(tab)
                last_access = self.tab_last_accessed.get(tab_id)

                if last_access:
                    if current_time - last_access > inactive_threshold:
                        if self.tabs.currentIndex() != i:
                            self.unload_tab_content(i)
                else:
                    self.tab_last_accessed[tab_id] = current_time

    def unload_tab_content(self, tab_index):
        tab = self.tabs.widget(tab_index)
        if hasattr(tab, 'web_view') and tab.web_view:
            try:
                url = ""
                if hasattr(tab.web_view, 'url'):
                    url_obj = tab.web_view.url()
                    if url_obj:
                        url = url_obj.toString()

                title = self.tabs.tabText(tab_index)

                if url:
                    self.save_tab_state(tab_index, url, title)

                try:
                    if hasattr(tab.web_view, 'page') and tab.web_view.page():
                        tab.web_view.page().runJavaScript("""
                            (function() {
                                var audios = document.getElementsByTagName('audio');
                                for (var i = 0; i < audios.length; i++) {
                                    audios[i].pause();
                                    audios[i].currentTime = 0;
                                }

                                var videos = document.getElementsByTagName('video');
                                for (var i = 0; i < videos.length; i++) {
                                    videos[i].pause();
                                    videos[i].currentTime = 0;
                                }
                            })();
                        """)
                except:
                    pass

                layout = tab.layout()
                if layout:
                    for i in reversed(range(layout.count())):
                        widget = layout.itemAt(i).widget()
                        if widget:
                            widget.deleteLater()

                    placeholder_text = "Tab unloaded to save memory"
                    if url:
                        placeholder_text += f"\n\nURL: {url}\nClick anywhere to reload"

                    placeholder = QLabel(placeholder_text)
                    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder.setStyleSheet("""
                        QLabel {
                            color: white;
                            background: #2b2b2b;
                            font-size: 14px;
                            padding: 40px;
                            border: 1px solid #444;
                            border-radius: 8px;
                        }
                    """)

                    placeholder.mousePressEvent = lambda event, idx=tab_index: self.restore_tab_content(idx)
                    layout.addWidget(placeholder)

                tab.web_view.deleteLater()
                tab.web_view = None

            except Exception as e:
                print(f"browser: error unloading tab {tab_index}: {e}")


    def restore_tab_content(self, tab_index):
        tab = self.tabs.widget(tab_index)
        if not hasattr(tab, 'web_view') or tab.web_view is None:
            tab_states = self.load_tab_states()
            if str(tab_index) in tab_states:
                state = tab_states[str(tab_index)]

                layout = tab.layout()
                if layout:
                    for i in reversed(range(layout.count())):
                        widget = layout.itemAt(i).widget()
                        if widget:
                            widget.deleteLater()

                try:
                    tab.web_view = InspectorWebView(self.profile, tab, browser=self)
                    if state['url']:
                        tab.web_view.setUrl(QUrl(state['url']))
                    else:
                        tab.web_view.setUrl(QUrl("about:blank"))

                    tab.web_view.urlChanged.connect(lambda u, t=tab: self.on_url_change(t))
                    tab.web_view.titleChanged.connect(lambda t, i=tab_index: self.on_title_change(t, i))
                    tab.web_view.iconChanged.connect(lambda icon, i=tab_index: self.on_icon_change(icon, i))

                    layout.addWidget(tab.web_view)
                    self.tab_last_accessed[id(tab)] = datetime.now()

                    self.remove_tab_state(tab_index)

                except Exception as e:
                    print(f"browser: error restoring tab {tab_index}: {e}")
                    layout.addWidget(QLabel("failed to restore tab"))

    def save_tab_state(self, tab_index, url, title):
        try:
            tab_states = {}
            if os.path.exists(TAB_STATE_FILE):
                with open(TAB_STATE_FILE, 'r', encoding='utf-8') as f:
                    tab_states = json.load(f)

            tab_states[str(tab_index)] = {
                'url': url,
                'title': title,
                'timestamp': datetime.now().isoformat()
            }

            with open(TAB_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(tab_states, f, indent=2)
        except:
            pass

    def load_tab_states(self):
        try:
            if os.path.exists(TAB_STATE_FILE):
                with open(TAB_STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_session(self):
        try:
            session_data = {
                'tabs': [],
                'current_tab': self.tabs.currentIndex(),
                'timestamp': datetime.now().isoformat()
            }

            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)

                if isinstance(tab, SettingsTab):
                    session_data['tabs'].append({
                        'type': 'settings',
                        'title': self.translator.tr("settings", "Settings")
                    })
                elif hasattr(tab, 'new_tab_page') and tab.new_tab_page:
                    session_data['tabs'].append({
                        'type': 'newtab',
                        'title': self.translator.tr("new_tab", "New Tab")
                    })
                elif hasattr(tab, 'browser') and tab.browser:
                    url = tab.browser.url().toString()
                    title = self.tabs.tabText(i)
                    session_data['tabs'].append({
                        'type': 'web',
                        'url': url,
                        'title': title
                    })

            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            print(f"browser: error saving session {e}")

    def restore_session(self):
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)

                while self.tabs.count() > 0:
                    self.tabs.removeTab(0)

                restored_count = 0
                for tab_data in session_data['tabs']:
                    if tab_data.get('type') == 'settings':
                        st = SettingsTab(self)
                        i = self.tabs.addTab(st, self.translator.tr("settings", "Settings"))
                        restored_count += 1
                    elif tab_data.get('type') == 'newtab':
                        self.add_tab(is_new_tab=True)
                        restored_count += 1
                    elif tab_data.get('url'):
                        self.add_tab(tab_data['url'])
                        restored_count += 1

                if restored_count == 0:
                    self.add_tab(is_new_tab=True)

                if 'current_tab' in session_data:
                    current_index = min(session_data['current_tab'], self.tabs.count() - 1)
                    if current_index >= 0:
                        self.tabs.setCurrentIndex(current_index)
            else:
                self.add_tab(is_new_tab=True)
        except Exception as e:
            print(f"browser: error restoring session {e}")
            self.add_tab(is_new_tab=True)

    def close_tab(self, i):
        if self.tabs.count() > 1:
            tab = self.tabs.widget(i)
            if hasattr(tab, 'web_view') and tab.web_view:
                try:
                    if hasattr(tab.web_view, 'page') and tab.web_view.page():
                        tab.web_view.page().runJavaScript("""
                            (function() {
                                var audios = document.getElementsByTagName('audio');
                                for (var i = 0; i < audios.length; i++) {
                                    audios[i].pause();
                                    audios[i].currentTime = 0;
                                }

                                var videos = document.getElementsByTagName('video');
                                for (var i = 0; i < videos.length; i++) {
                                    videos[i].pause();
                                    videos[i].currentTime = 0;
                                }
                            })();
                        """)
                except Exception as e:
                    print(f"browser: error stopping media: {e}")

                try:
                    if hasattr(tab.web_view, 'setHtml'):
                        tab.web_view.setHtml("")
                except:
                    pass

                tab.web_view.deleteLater()
                tab.web_view = None

            tab_id = id(tab)
            if tab_id in self.tab_last_accessed:
                del self.tab_last_accessed[tab_id]

            self.remove_tab_state(i)
            self.tabs.removeTab(i)


    def add_tab(self, url=None, is_new_tab=False):
        if is_new_tab:
            new_tab = Tab(self.profile, url, is_new_tab, self, self.translator, self.theme_engine)
            i = self.tabs.addTab(new_tab, self.translator.tr("new_tab", "New Tab"))
            self.tabs.setCurrentIndex(i)

            if hasattr(self.theme_engine, 'apply_theme_to_new_tab') and new_tab.new_tab_page:
                self.theme_engine.apply_theme_to_new_tab(new_tab.new_tab_page)

            return new_tab
        elif url and url.startswith("settings://"):
            self.open_settings_tab()
            return None
        else:
            new_tab = Tab(self.profile, url, is_new_tab, self, self.translator, self.theme_engine)
            i = self.tabs.addTab(new_tab, self.translator.tr("loading", "Loading..."))
            self.tabs.setCurrentIndex(i)

            if new_tab.web_view:
                new_tab.web_view.parent_browser = self
                new_tab.web_view.urlChanged.connect(lambda u, t=new_tab: self.on_url_change(t))
                new_tab.web_view.titleChanged.connect(lambda t, i=i: self.on_title_change(t, i))
                new_tab.web_view.iconChanged.connect(lambda icon, i=i: self.on_icon_change(icon, i))
                new_tab.web_view.urlChanged.connect(lambda u: self.history.append(new_tab.web_view.url().toString()))

                self.tab_last_accessed[id(new_tab)] = datetime.now()

            return new_tab

    def remove_tab_state(self, tab_index):
        try:
            if os.path.exists(TAB_STATE_FILE):
                with open(TAB_STATE_FILE, 'r', encoding='utf-8') as f:
                    tab_states = json.load(f)

                if str(tab_index) in tab_states:
                    del tab_states[str(tab_index)]

                    new_states = {}
                    for key, value in tab_states.items():
                        old_index = int(key)
                        if old_index > tab_index:
                            new_states[str(old_index - 1)] = value
                        else:
                            new_states[key] = value

                    with open(TAB_STATE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(new_states, f, indent=2)
        except:
            pass

    def apply_current_theme(self):
        theme_name = self.settings.get("theme", self.translator.tr("default_theme", "Default Theme"))
        self.theme_engine.apply_theme(theme_name)

    def load_settings(self):
        settings = {
            "show_welcome_screen": True,
            "language": "English",
            "theme": self.translator.tr("default_theme", "Default Theme"),
            "memory_saver": False,
            "restore_session": True
        }
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
            except Exception as e:
                print(f"settings: error loading user settings {e}")
        return settings

    def save_settings(self):
        self.settings["language"] = self.translator.current_lang
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"settings: error saving user settings {e}")

    def update_language(self):
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, SettingsTab):
                self.tabs.setTabText(i, self.translator.tr("settings", "Settings"))
                widget.update_extensions_view()
            elif hasattr(widget, 'new_tab_page') and widget.new_tab_page:
                widget.new_tab_page.search_bar.setPlaceholderText(
                    self.translator.tr("search_placeholder", "search google or enter url")
                )

        self.update_url_bar_placeholder()

    def init_discord_rpc(self):
        if DISCORD_RPC_AVAILABLE:
            try:
                self.rpc = Presence(DISCORD_APP_ID)
                self.rpc.connect()
                self.rpc.update(state="browsing the web", details="made by anameless_guy on discord")
                print("discord rpc: connected")

            except Exception as e:
                print(f"discord rpc: failed {e}")
                self.rpc = None

    def update_url_bar_placeholder(self):
        self.url_bar.setPlaceholderText(
            self.translator.tr("search_placeholder", "Search {} or type a URL").format(self.current_search_engine)
        )

    def get_search_url(self, query):
        from urllib.parse import quote
        if '.' in query and ' ' not in query and not query.startswith(('http://','https://')):
            return "https://" + query
        else:
            search_template = self.search_engines.get(self.current_search_engine, "https://www.google.com/search?q={}")
            return search_template.format(quote(query))

    def set_search_engine(self, engine_name):
        if engine_name in self.search_engines:
            self.current_search_engine = engine_name
            self.update_url_bar_placeholder()
            self.save_search_engine()
            print(f"settings: search engine changed to {engine_name}")

    def load_search_engine(self):
        if os.path.exists(SEARCH_ENGINE_FILE):
            try:
                with open(SEARCH_ENGINE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    engine = data.get("engine", "Google")
                    if engine in self.search_engines:
                        return engine
            except Exception as e:
                print(f"settings: error loading search engine {e}")
        return "Google"

    def save_search_engine(self):
        try:
            with open(SEARCH_ENGINE_FILE, "w", encoding="utf-8") as f:
                json.dump({"engine": self.current_search_engine}, f, indent=2)
        except Exception as e:
            print(f"settings: error saving search engine {e}")

    def set_theme(self, theme_name):
        self.settings["theme"] = theme_name
        self.save_settings()
        previous_font = self.theme_engine.current_font
        self.theme_engine.apply_theme(theme_name)
        self.style().unpolish(self)
        self.style().polish(self)

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, 'new_tab_page') and tab.new_tab_page:
                tab.new_tab_page.set_default_background()

    def load_extensions(self):
        if not os.path.exists(EXTENSIONS_DIR):
            return

        for ext_folder in os.listdir(EXTENSIONS_DIR):
            ext_path = os.path.join(EXTENSIONS_DIR, ext_folder)
            if os.path.isdir(ext_path):
                manifest_path = os.path.join(ext_path, "manifest.json")
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)

                        ext_name = manifest.get('name', ext_folder)
                        ext_description = manifest.get('description', 'No description provided')
                        ext_version = manifest.get('version', '1.0')
                        script_file = manifest.get('script', 'script.js')

                        script_path = os.path.join(ext_path, script_file)
                        if os.path.exists(script_path):
                            with open(script_path, 'r', encoding='utf-8') as f:
                                script_content = f.read()

                            self.extensions[ext_name] = {
                                'name': ext_name,
                                'description': ext_description,
                                'version': ext_version,
                                'script': script_file,
                                'script_content': script_content,
                                'folder': ext_folder
                            }

                            print(f"extension engine: loaded extension {ext_name} v{ext_version}")

                    except Exception as e:
                        print(f"extension engine: error loading extension {ext_folder}: {e}")

    def inject_extensions_into_profile(self):
        for ext_name, ext_data in self.extensions.items():
            script_content = ext_data.get('script_content', '')
            if script_content:
                script = QWebEngineScript()
                script.setSourceCode(script_content)
                script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
                script.setRunsOnSubFrames(True)
                self.profile.scripts().insert(script)

    def load_passwords(self):
        passwords = {}
        if os.path.exists(PASSWORDS_FILE):
            try:
                with open(PASSWORDS_FILE, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if "name" in row and "username" in row and "password" in row:
                            passwords[row["name"]] = {"user": row["username"], "pass": row["password"]}
            except Exception as e:
                print(f"settings: error loading passwords {e}")
        return passwords

    def save_passwords(self):
        try:
            with open(PASSWORDS_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["name", "username", "password"])
                for name, info in self.passwords.items():
                    writer.writerow([name, info["user"], info["pass"]])
        except Exception as e:
            print(f"settings: error saving passwords: {e}")

    def load_history(self):
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception as e:
                print(f"settings: error loading history {e}")
        return history

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"settings: error saving history {e}")

    def create_tab_view(self):
        web_view = InspectorWebView(self.profile, browser=self)
        return web_view

    def add_tab(self, url=None, is_new_tab=False):
        new_tab = Tab(self.profile, url, is_new_tab, self, self.translator, self.theme_engine)
        i = self.tabs.addTab(new_tab,
            self.translator.tr("new_tab", "New Tab") if is_new_tab else self.translator.tr("loading", "Loading..."))
        self.tabs.setCurrentIndex(i)

        if not is_new_tab and hasattr(new_tab, 'web_view') and new_tab.web_view:
            new_tab.web_view.urlChanged.connect(lambda u, t=new_tab: self.on_url_change(t))
            new_tab.web_view.titleChanged.connect(lambda t, i=i: self.on_title_change(t, i))
            new_tab.web_view.iconChanged.connect(lambda icon, i=i: self.on_icon_change(icon, i))
            new_tab.web_view.urlChanged.connect(lambda u: self.history.append(new_tab.web_view.url().toString()))

            self.tab_last_accessed[id(new_tab)] = datetime.now()

        return new_tab

    def on_title_change(self, title, index):
        tab_text = title[:20] + "..." if len(title) > 23 else title
        self.tabs.setTabText(index, tab_text if title else self.translator.tr("new_tab", "New Tab"))

    def on_icon_change(self, icon, index):
        if not icon.isNull():
            self.tabs.setTabIcon(index, icon)
        else:
            self.tabs.setTabIcon(index, QIcon())

    def open_settings_tab(self):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, SettingsTab):
                self.tabs.setCurrentIndex(i)
                w.update_extensions_view()
                return

        st = SettingsTab(self)
        i = self.tabs.addTab(st, self.translator.tr("settings", "Settings"))
        self.tabs.setCurrentIndex(i)

    def current_browser(self):
        tab = self.tabs.currentWidget()
        if hasattr(tab,"web_view") and tab.web_view:
            return tab.web_view
        return None

    def inspect_current_page(self):
        browser = self.current_browser()
        if browser and hasattr(browser, 'inspect_element'):
            browser.inspect_element()
        else:
            QMessageBox.information(self, "Inspect Element", "No web page to inspect.")

    def navigate_to_url(self):
        url = self.url_bar.text().strip()
        if not url:
            return
        if not url.startswith(("http://","https://")):
            url = self.get_search_url(url)
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl(url))
        else:
            self.add_tab(url)

    def on_url_change(self, tab):
        if self.tabs.currentWidget() == tab and hasattr(tab, 'web_view') and tab.web_view:
            self.url_bar.setText(tab.web_view.url().toString())

        tab_id = id(tab)
        self.tab_last_accessed[tab_id] = datetime.now()

    def update_url_bar(self, *args):
        tab = self.tabs.currentWidget()
        if hasattr(tab, "browser") and isinstance(tab.browser, QWebEngineView):
            self.url_bar.setText(tab.browser.url().toString())
        else:
            self.url_bar.setText("")

    def on_download(self,item:QWebEngineDownloadRequest):
        path,_ = QFileDialog.getSaveFileName(self,
            self.translator.tr("save_as", "Save File As"),
            item.suggestedFileName())
        if path:
            item.setDownloadDirectory(os.path.dirname(path))
            item.setDownloadFileName(os.path.basename(path))
            item.accept()

    def closeEvent(self, event):
        print(f"cat browser closing (plz use it again)")
        self.save_passwords()
        self.save_history()
        self.save_search_engine()
        self.save_settings()

        if self.settings.get("restore_session", True):
            self.save_session()

        if os.path.exists(TAB_STATE_FILE):
            try:
                os.remove(TAB_STATE_FILE)
            except:
                pass

        if self.rpc:
            try:
                self.rpc.close()
            except:
                pass

        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = Browser()

    if not os.path.exists(SETUP_FILE):
        splash = WelcomeScreen(3000)
        splash.show()

        class SetupController:
            def __init__(self):
                self.setup_shown = False
                self.timer = QTimer()
                self.timer.setSingleShot(True)
                self.timer.timeout.connect(self.show_setup)

            def show_setup(self):
                if not self.setup_shown:
                    self.setup_shown = True
                    setup_wizard = SetupWizard(main_window)
                    setup_wizard.finished.connect(main_window.show)
                    setup_wizard.exec()

            def start_timer(self):
                self.timer.start(3500)

        controller = SetupController()
        splash.finished.connect(controller.show_setup)
        controller.start_timer()

    else:
        if main_window.settings.get("show_welcome_screen", True):
            splash = WelcomeScreen(3000)
            splash.show()
            splash.finished.connect(main_window.show)
            QTimer.singleShot(3500, main_window.show)
        else:
            main_window.show()

    sys.exit(app.exec())