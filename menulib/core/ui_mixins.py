# file: ui_mixins.py (這是一個新檔案，和 menu_manager.py 平級)

import maya.cmds as cmds
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance
from PySide2.QtWidgets import QWidget

class DockableUIMixin:
    """
    一個提供「可停靠 UI」功能的 Mixin。
    任何繼承此 Mixin 的類別，將自動獲得 show_ui 方法。

    繼承者必須定義以下 Class 屬性：
    - WIDGET_CLASS: 要顯示的 UI Widget 類別 (例如 MySuperToolWidget)
    - UI_NAME: Maya workspaceControl 的唯一名稱 (例如 "mySuperToolPanel")
    - UI_LABEL: UI 面板顯示的標題 (例如 "Super Tool")
    """
    
    ui_instance = None # 用來保存 UI 實例的參考

    def show_ui(self):
        """
        管理 UI 生命週期的核心方法。
        負責建立、顯示或聚焦可停靠面板。
        """
        print(f"Mixin: Trying to show UI: {self.UI_LABEL}")
        
        if cmds.workspaceControl(self.UI_NAME, exists=True):
            cmds.workspaceControl(self.UI_NAME, edit=True, restore=True, visible=True)
            print("Mixin: UI already exists. Restoring it.")
            return

        # 建立 UI，並將 UI 實例保存在 self.ui_instance 中
        # uiScript: 當 Maya 重新載入工作區時，用來重建 UI 的指令
        # 我們讓它呼叫外掛的 execute 方法，從而再次觸發 show_ui，形成一個完美的閉環。
        # 注意：需要完整的模組路徑和類別名稱
        full_class_path = f"{self.__class__.__module__}.{self.__class__.__name__}"
        ui_script_command = (
            f"from {full_class_path} import {self.__class__.__name__}; "
            f"temp_instance = {self.__class__.__name__}(); temp_instance.execute();"
        )
        
        control_ptr = omui.MQtUtil.findControl(
            cmds.workspaceControl(
                self.UI_NAME, 
                label=self.UI_LABEL,
                uiScript=ui_script_command
            )
        )
        
        if not control_ptr:
            print(f"Error: Failed to create workspaceControl: {self.UI_NAME}")
            return
            
        control_widget = wrapInstance(int(control_ptr), QWidget)
        control_layout = control_widget.layout()
        
        # 繼承者必須提供 WIDGET_CLASS 這個屬性
        self.ui_instance = self.WIDGET_CLASS()
        control_layout.addWidget(self.ui_instance)
        print("Mixin: New UI created.")