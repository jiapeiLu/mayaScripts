# Auto-generated menu items: VertexMatch
# Generated on: 2025-08-01 09:07:20
# Contains 1 menuitem(s)

from menulib.core.menuitem_interface import MenuItemInterface
import maya.cmds as cmds
import vtxMatch

class VertexmatchMenuItem(MenuItemInterface):
    ACTION_NAME = "VertexMatch"
    MENU_PATH = "Mesh"
    ORDER = 100
    ICON_PATH = r":/alignUMin.png"

    def get_menu_path(self) -> str:
        return self.MENU_PATH

    def get_action_name(self) -> str:
        return self.ACTION_NAME

    def execute(self, *args):
        vtxMatch.main()

    def get_option_box_command(self):
        return None