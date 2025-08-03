# Auto-generated menu items: polyCube, Create Sphere
# Generated on: 2025-08-03 12:32:18
# Contains 2 menuitem(s)

from menulib.core.menuitem_interface import MenuItemInterface
from menulib.core.ui_mixins import DockableUIMixin
import maya.cmds as cmds

class PolyCubeWidget:
    """A placeholder for the actual widget class."""
    def excute(self, *args):
        # 簡單的功能示例
        result = cmds.polyCube(name="ExampleCube")
        print(f"Created cube: {result[0]}")

    def show(self):
        """選項對話框"""
        result = cmds.promptDialog(
            title='Example Tool Options',
            message='Enter cube size:',
            button=['OK', 'Cancel'],
            defaultButton='OK',
            cancelButton='Cancel',
            dismissString='Cancel',
            text='1.0'
        )
        
        if result == 'OK':
            size = cmds.promptDialog(query=True, text=True)
            try:
                size = float(size)
                cube_result = cmds.polyCube(width=size, height=size, depth=size, name="CustomCube")
                print(f"Created custom cube with size {size}: {cube_result[0]}")
            except ValueError:
                cmds.warning("Invalid size value!")


class PolycubeMenuItem(MenuItemInterface, DockableUIMixin):
    ACTION_NAME = "Poly Cube"
    MENU_PATH = "Tools/Examples"
    ORDER = 10
    SEPARATOR_AFTER = True
    ICON_PATH = r":/polyCube.png"
    WIDGET_CLASS = PolyCubeWidget  # Import your widget class
    UI_NAME = "exampleToolPanel"
    UI_LABEL = "polyCube"

    def get_menu_path(self) -> str:
        return self.MENU_PATH

    def get_action_name(self) -> str:
        return self.ACTION_NAME

    def execute(self, *args):
        """主要功能：創建一個立方體"""
        self.WIDGET_CLASS().excute(*args)

    def get_option_box_command(self):
        """反回選項方塊命令"""
        return self.WIDGET_CLASS().show


class SimpleCommandMenuItem(MenuItemInterface):
    ACTION_NAME = "Create Sphere"
    MENU_PATH = "Tools/Examples"
    ORDER = 20

    def get_menu_path(self) -> str:
        return self.MENU_PATH

    def get_action_name(self) -> str:
        return self.ACTION_NAME

    def execute(self, *args):
        """創建一個球體"""
        result = cmds.polySphere(name="ExampleSphere")
        print(f"Created sphere: {result[0]}")

    def get_option_box_command(self):
        return None