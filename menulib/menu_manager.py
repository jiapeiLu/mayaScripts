
""" Usage:
import menulib.menu_manager as menu_manager
menu_manager.initialize_menu()
menu_manager.show_generator()  
menu_manager.teardown_menu()  

"""

__author__ = "Jiapei Lu & Claude Sonnet 4"
__version__ = "1.0.0-alpha1" 

import logging
import json
from pathlib import Path

import sys
import os
import importlib
from pathlib import Path
import functools # [新增] 匯入 functools 來使用 partial

from PySide2.QtWidgets import QMainWindow, QWidget, QMenu, QAction, QLabel, QPushButton, QHBoxLayout, QSizePolicy, QWidgetAction
from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon, QPixmap  # [新增] 支援 Icon
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance

from menulib.plugin_interface import PluginInterface


logger = logging.getLogger("MenuFramework")

def setup_menu_logging(config):
    """
    根據設定檔，設定 MenuFramework logger 的等級和 handler。
    """
    # 1. 從設定檔取得日誌等級，預設為 'INFO'
    log_level_str = config.get("log_level", "INFO").upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    level = level_map.get(log_level_str, logging.INFO)
    logger.setLevel(level)

    # [修正] 停止將訊息傳播到根 logger，避免重複輸出
    logger.propagate = False

    # 2. 防止在 Maya 中重複執行時，重複加入 handler
    if logger.hasHandlers():
        logger.handlers.clear()

    # 3. 建立 handler 和 formatter
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    
    # 4. 將 handler 加入 logger
    logger.addHandler(handler)
    logger.info(f"Logger initialized with level: {log_level_str}")


def load_config():
    """
    載入設定檔 config.json，並提供安全的預設值。
    """
    # 預設設定
    default_config = {
        "main_menu_title": "Default Tools",
        "show_warnings_on_load": False
    }

    try:
        # 設定檔路徑與 menu_manager.py 相同
        config_path = Path(__file__).parent / "config.json"
        
        if not config_path.exists():
            logger.info("config.json not found. Using default settings.")
            return default_config

        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
            # 將使用者的設定覆蓋到預設設定上，這樣即使使用者只設定了一項，其他項也有預設值
            default_config.update(user_config)
            return default_config

    except json.JSONDecodeError:
        logger.error("Failed to decode config.json. File might be corrupted. Using default settings.")
        return default_config
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading config: {e}. Using default settings.")
        return default_config


# [新增] Icon 載入輔助函數
def load_icon(icon_path):
    """
    載入 Icon，如果失敗則返回 None
    """
    # maya build-in icon
    if icon_path.startswith(':/'):
        return QIcon(icon_path)

    if not icon_path or not os.path.exists(icon_path):
        return None
    
    try:

        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            logger.warning(f"Failed to load icon: {icon_path}")
            return None
        return QIcon(pixmap)
        
    except Exception as e:
        logger.warning(f"Error loading icon {icon_path}: {e}")
        return None


# --- Constants ---
MENU_ITEMS_DIR = Path(__file__).parent.parent / "menu_items"  # [新增] 生成器產出的插件目錄
MAIN_MENU_OBJECT_NAME = "MyCustomToolsMainMenu"


# ==============================================================================
#  SplitButtonAction (修正了樣式和懸停效果, 增加 Icon 支援)
# ==============================================================================
class SplitButtonAction(QWidgetAction):
    def __init__(self, plugin_id: int, manager, parent: QWidget):
        super().__init__(parent)
        # [修改] 不再直接保存 plugin，而是保存它的 ID 和 manager 的參考
        self.plugin_id = plugin_id
        self.manager = manager
        self.plugin = manager._plugin_instances[plugin_id]
        
        # [修改] 連接到 manager 的分派器
        self.triggered.connect(functools.partial(self.manager.trigger_plugin_execute, self.plugin_id))

    def createWidget(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # 修改：減少間距以獲得更一致的外觀

        main_button = QPushButton(self.plugin.get_action_name())
        main_button.setFlat(True)
        main_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # [修正] 改善樣式，添加懸停效果和選中效果
        main_button.setStyleSheet("""
            QPushButton {
                border: none;
                text-align: left;
                padding-left: 24px;
                padding-top: 4px;
                padding-bottom: 4px;
                padding-right: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgb(80, 130, 166);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        # [新增] 設定 Icon
        icon = self.plugin.get_icon() if hasattr(self.plugin, 'get_icon') else None
        if icon:
            main_button.setIcon(icon)
            main_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    text-align: left;
                    padding-left:4px;
                    padding-top: 4px;
                    padding-bottom: 4px;
                    padding-right: 4px;
                    background-color: transparent;
                }
                QPushButton:hover {
                    background-color: rgb(80, 130, 166);
                }
                QPushButton:pressed {
                    background-color: rgba(255, 255, 255, 0.2);
                }
            """)
            
        
        # [修改] 按鈕點擊時，觸發這個 QWidgetAction 自己的 triggered 信號
        main_button.clicked.connect(self.trigger)

        option_button = QPushButton("☐")
        option_button.setFlat(True)
        option_button.setFixedSize(20, 20)  # 修改：稍微調小尺寸
        option_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        # [修正] 改善選項按鈕的樣式和懸停效果
        option_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 0px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 2px;
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.25);
                border-radius: 2px;
            }
        """)
        
        # [修改] 連接到 manager 的選項分派器
        option_button.clicked.connect(functools.partial(self.manager.trigger_plugin_option_box, self.plugin_id))
        
        layout.addWidget(main_button)
        layout.addWidget(option_button)

        # [新增] 為整個容器設置樣式，確保懸停效果正確
        container.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
            QWidget:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)

        return container


def get_maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr:
        return wrapInstance(int(main_window_ptr), QMainWindow)
    return None

class MenuBarManager:
    # [修改] __init__ 方法現在接收一個 config 字典
    def __init__(self, menu_title="My Tools", config=None):
        self._menu_title = menu_title
        # [修改] 保存 config，如果傳入的是 None，就用一個空字典代替以確保安全
        self.config = config if config is not None else {}
        self._maya_main_window = get_maya_main_window()
        self._main_menu = None
        self._menus_cache = {}
        self._actions_cache = []
        self._plugin_instances = []

    # [新增] 中央分派器方法
    def trigger_plugin_execute(self, plugin_id: int):
        logger.debug(f"Dispatcher: Triggering execute for plugin #{plugin_id}")
        if 0 <= plugin_id < len(self._plugin_instances):
            plugin = self._plugin_instances[plugin_id]
            plugin.execute()
        else:
            logger.error(f"Invalid plugin_id {plugin_id}")

    # [新增] 選項方塊的中央分派器方法
    def trigger_plugin_option_box(self, plugin_id: int):
        logger.debug(f"Dispatcher: Triggering option_box for plugin #{plugin_id}")
        if 0 <= plugin_id < len(self._plugin_instances):
            plugin = self._plugin_instances[plugin_id]
            # 找到並關閉選單
            active_menu = self._actions_cache[plugin_id].parent()
            if active_menu and isinstance(active_menu, QMenu):
                active_menu.hide()

            option_command = plugin.get_option_box_command()
            if option_command:
                option_command()
        else:
            logger.error(f"Invalid plugin_id {plugin_id}")


    def remove_existing_menu(self):
        if not self._maya_main_window: return
        found_menus = self._maya_main_window.findChildren(QMenu, MAIN_MENU_OBJECT_NAME)
        for menu in found_menus:
            menu.deleteLater()
        self._main_menu = None
        self._menus_cache = {}
        self._actions_cache = []
        self._plugin_instances = []
        logger.debug(f"Removed existing menu: '{self._menu_title}'")

    def build_menu(self):
        if not self._maya_main_window: return
        self.remove_existing_menu()

        self._main_menu = QMenu(self._menu_title, self._maya_main_window)
        self._main_menu.setObjectName(MAIN_MENU_OBJECT_NAME)
        self._main_menu.setTearOffEnabled(True)
        self._main_menu.setProperty("menuManagerInstance", self)
        self._maya_main_window.menuBar().addMenu(self._main_menu)
        self._load_plugins()

    def _load_plugins(self):
        """
        [最終版] 透過自動探索、讀取元資料、排序、再建立的混合模式來載入外掛。
        現在支援從兩個目錄載入：menu_plugins 和 menu_items
        """
        logger.debug("--- Scanning for plugins ---")
        
        # 載入目錄列表
        plugin_dirs = []

        if MENU_ITEMS_DIR.is_dir():
            plugin_dirs.append(("menu_items", MENU_ITEMS_DIR))
            
        if not plugin_dirs:
            logger.warning("No plugin directories found")
            return

        plugin_root = str(Path(__file__).parent)
        if plugin_root not in sys.path:
            sys.path.insert(0, plugin_root)

        # 1. 探索階段：
        discovered_plugins = []
        seen_orders = set() # 用於檢測重複

        for dir_name, dir_path in plugin_dirs:
            logger.debug(f"--- Scanning directory: {dir_path} ---")
            
            for filename in sorted(os.listdir(dir_path)):
                if filename.endswith(".py") and not filename.startswith("__"):
                    module_name = f"{dir_name}.{filename[:-3]}"
                    try:
                        module = importlib.import_module(module_name)
                        importlib.reload(module)
                        for item_name in dir(module):
                            plugin_class = getattr(module, item_name)
                            if (isinstance(plugin_class, type) and
                                    issubclass(plugin_class, PluginInterface) and
                                    plugin_class is not PluginInterface):
                                
                                path = getattr(plugin_class, "MENU_PATH", "")
                                order = getattr(plugin_class, "ORDER", 9999)
                                action_name = getattr(plugin_class, "ACTION_NAME", plugin_class.__name__)
                                icon_path = getattr(plugin_class, "ICON_PATH", None)  # [新增] Icon 支援

                                # 檢查 ORDER 是否重複
                                order_key = (path, order)
                                if order_key in seen_orders:
                                    logger.warning(
                                        f"WARNING: Duplicate ORDER detected! "
                                        f"Path='{path}', Order={order}. "
                                        f"Plugin '{action_name}' may have unpredictable ordering."
                                    )
                                seen_orders.add(order_key)

                                metadata = {
                                    "class": plugin_class,
                                    "path": path,
                                    "action_name": action_name,
                                    "order": order,
                                    "icon_path": icon_path,  # [新增]
                                    "separator_after": getattr(plugin_class, "SEPARATOR_AFTER", False)
                                }
                                discovered_plugins.append(metadata)
                    except Exception as e:
                        logger.debug(f"    ! Failed to load plugin from {filename}: {e}")

        # 2. 排序階段：
        # 使用三層排序，確保結果 100% 可預測
        sorted_plugins = sorted(discovered_plugins, key=lambda p: (p["path"], p["order"], p["action_name"]))

        # 3. 建立階段：
        if not sorted_plugins:
            logger.debug("--- No valid plugins were discovered. ---")
            return
            
        logger.debug("--- Registering discovered plugins in sorted order ---")
        for metadata in sorted_plugins:
            plugin_class = metadata["class"]
            logger.debug(f"  > Registering: {metadata['action_name']} (Path: {metadata['path']}, Order: {metadata['order']})")
            
            instance = plugin_class()
            
            # [新增] 如果有 Icon 路徑，添加 get_icon 方法
            if metadata['icon_path']:
                icon = load_icon(metadata['icon_path'])
                if icon:
                    instance.get_icon = lambda: icon
                    logger.debug(f"  > {' '*len('Registering')}: Add Icon to {instance.get_action_name()}")
                    
                    
            self._plugin_instances.append(instance)
            self._register_plugin(instance)


    def _find_or_create_submenu(self, path: str) -> QMenu:
        if not path: return self._main_menu
        parts = path.strip('/').split('/')
        parent_menu = self._main_menu
        for i, part in enumerate(parts):
            current_path = "/".join(parts[:i + 1])
            if current_path in self._menus_cache:
                parent_menu = self._menus_cache[current_path]
            else:
                new_menu = QMenu(part, parent_menu)
                new_menu.setTearOffEnabled(True)
                parent_menu.addMenu(new_menu)
                self._menus_cache[current_path] = new_menu
                parent_menu = new_menu
        return parent_menu

    def _register_plugin(self, plugin: PluginInterface):
        target_menu = self._find_or_create_submenu(plugin.get_menu_path())

        # [修改] 使用 plugin 在列表中的索引作為它的唯一 ID
        plugin_id = self._plugin_instances.index(plugin)
        option_box_command = plugin.get_option_box_command()

        if option_box_command:
            action = SplitButtonAction(plugin_id, self, self._maya_main_window)
        else:
            action = QAction(plugin.get_action_name(), self._maya_main_window)
            
            # [新增] 設定 Icon
            if hasattr(plugin, 'get_icon'):
                icon = plugin.get_icon()
                action.setIcon(icon)

            
            # [修改] 連接到分派器，並傳入 plugin_id
            action.triggered.connect(functools.partial(self.trigger_plugin_execute, plugin_id))

        target_menu.addAction(action)
        self._actions_cache.append(action)
        
        if getattr(plugin, "SEPARATOR_AFTER", False) :
            target_menu.addSeparator()


# --- Entry Points for Maya ---
menu_manager_instance = None

def initialize_menu():
    """Run this function in Maya to build or rebuild your custom menu."""
    global menu_manager_instance
    
    # [修改] 流程調整
    # 1. 載入設定
    config = load_config()
    
    # 2. 根據設定，初始化日誌系統
    setup_menu_logging(config)
    
    # 3. 繼續原本的流程
    logger.info("Initializing Custom Menu...")
    menu_title = config.get("main_menu_title", "Default Tools")

    if 'menu_manager_instance' in globals() and menu_manager_instance:
        try: menu_manager_instance.remove_existing_menu()
        except: pass
        
    menu_manager_instance = MenuBarManager(menu_title=menu_title, config=config)
    menu_manager_instance.build_menu()
    logger.info("Menu initialization complete.")


def teardown_menu():
    global menu_manager_instance
    if 'menu_manager_instance' in globals() and menu_manager_instance:
        menu_manager_instance.remove_existing_menu()
        menu_manager_instance = None


# [新增] 啟動生成器的便捷函數
def show_generator():
    """顯示菜單項目生成器"""
    try:
        from menulib import menuitem_generator
        importlib.reload(menuitem_generator)  # 確保載入最新版本
        show_menu_item_generator = menuitem_generator.show_menu_item_generator

        return show_menu_item_generator()
    except ImportError as e:
        logger.error(f"Failed to import menu generator: {e}")
        return None
        
