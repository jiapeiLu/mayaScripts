import importlib
import json
from pathlib import Path
import menulib.core.menu_manager as menuMG


menu_manager_instance = None
config = menuMG.load_config(__file__)

def reload():
    """Reload the menu manager module."""
    importlib.reload(menuMG)


def initialize_menu():
    """Run this function in Maya to build or rebuild your custom menu."""
    global menu_manager_instance
    
    # 根據設定，初始化日誌系統
    menuMG.setup_menu_logging(config)
    
    # 3. 繼續原本的流程
    menuMG.logger.info("Initializing Custom Menu...")
    menu_title = config.get("main_menu_title", "Default Tools")

    if 'menu_manager_instance' in globals() and menu_manager_instance:
        try: menu_manager_instance.remove_existing_menu()
        except: pass
        
    menu_manager_instance = menuMG.MenuBarManager(menu_title=menu_title, config=config)
    menu_manager_instance.build_menu()
    menuMG.logger.info("Menu initialization complete.")


def teardown_menu():
    global menu_manager_instance
    if 'menu_manager_instance' in globals() and menu_manager_instance:
        menu_manager_instance.remove_existing_menu()
        menu_manager_instance = None


def show_menu_generator():
    """顯示菜單項目生成器"""
    try:
        from menulib.core import menuitem_generator
        importlib.reload(menuitem_generator)  # 確保載入最新版本
        menuitem_generator.set_config(config)
        return menuitem_generator.show_menu_item_generator()
    
    except ImportError as e:
        menuMG.logger.error(f"Failed to import menu generator: {e}")
        return None