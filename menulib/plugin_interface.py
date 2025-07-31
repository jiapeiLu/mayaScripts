# file: plugin_interface.py
from abc import ABC, abstractmethod

class PluginInterface(ABC):
    """
    所有選單外掛都必須繼承的抽象基底類別。
    """

    @abstractmethod
    def get_menu_path(self) -> str:
        """
        回傳選單的層級路徑，用 '/' 分隔。
        例如: 'My Tools/Rigging'
        """
        pass

    @abstractmethod
    def get_action_name(self) -> str:
        """
        回傳在選單上顯示的名稱。
        例如: 'Super Cool Rigger'
        """
        pass

    @abstractmethod
    def execute(self, *args):
        """
        點擊選單項目時要執行的主要功能。
        """
        pass

    def get_option_box_command(self):
        """
        (可選) 點擊選單項目旁的選項方塊 (Option Box) 時執行的功能。
        通常用來開啟一個設定視窗。如果回傳 None，則不建立選項方塊。
        """
        return None
    
    def is_separator(self) -> bool:
        """
        (可選) 如果這是一個分隔線，回傳 True。
        通常會建立一個專門的 SeparatorPlugin 類別來實作。
        """
        return False