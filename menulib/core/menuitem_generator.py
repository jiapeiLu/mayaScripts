# file: menulib/core/menu_item_generator.py
import os
import json
import ast
import re
from pathlib import Path
from datetime import datetime
from PySide2.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QCheckBox, QSpinBox, QPushButton, QLabel,
    QFileDialog, QMessageBox, QGroupBox, QTabWidget, QComboBox,
    QSplitter, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QDialog, QDialogButtonBox, QPlainTextEdit
)
from PySide2.QtCore import Qt, QTimer
from PySide2.QtGui import QFont, QPixmap, QIcon
import maya.cmds as cmds
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance

config =  {}  # 這裡的 config 將在後續函數中被初始化

def set_config(config_data):
    global config
    config = config_data

def _initialize_language():
    """初始化語言設定"""
    # config imports

    # language imports
    import importlib
    from menulib.languagelib import language_manager
    importlib.reload(language_manager)  # 確保載入最新版本
    TRANS = language_manager.languageManager

    language = config.get('language', 'en_us')
    TRANS.set_language(language)
    return TRANS.tr  # 簡化翻譯函數調用

# 初始化翻譯函數
tr = _initialize_language()  


def get_maya_main_window():
    """獲取 Maya 主視窗"""
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr:
        return wrapInstance(int(main_window_ptr), QMainWindow)
    return None


class DataBindingManager:
    """數據綁定管理器 - 統一處理 UI 與數據的雙向綁定"""
    
    def __init__(self):
        self.binding_map = {}
        self.validation_rules = {}
    
    def register_binding(self, key, widget, property_name, validation_func=None):
        """註冊數據綁定映射"""
        self.binding_map[key] = (widget, property_name)
        if validation_func:
            self.validation_rules[key] = validation_func
    
    def sync_data_to_widgets(self, data):
        """將數據同步到 UI 元件"""
        for key, (widget, property_name) in self.binding_map.items():
            value = data.get(key)
            if value is not None:
                self._set_widget_value(widget, property_name, value)
    
    def sync_widgets_to_data(self):
        """將 UI 元件的值同步到數據字典"""
        data = {}
        validation_errors = []
        
        for key, (widget, property_name) in self.binding_map.items():
            try:
                value = self._get_widget_value(widget, property_name)
                
                # 應用驗證規則
                if key in self.validation_rules:
                    if not self.validation_rules[key](value):
                        validation_errors.append(f"Invalid value for {key}: {value}")
                        continue
                
                data[key] = value
                
            except Exception as e:
                validation_errors.append(f"Error processing {key}: {str(e)}")
        
        return data, validation_errors
    
    def _set_widget_value(self, widget, property_name, value):
        """設置 widget 的值"""
        if property_name == 'text':
            widget.setText(str(value))
        elif property_name == 'value':
            widget.setValue(int(value))
        elif property_name == 'checked':
            widget.setChecked(bool(value))
        elif property_name == 'plainText':
            widget.setPlainText(str(value))
        elif property_name == 'currentText':
            index = widget.findText(str(value), Qt.MatchFixedString)
            if index >= 0:
                widget.setCurrentIndex(index)
        else:
            setter_name = f'set{property_name.capitalize()}'
            if hasattr(widget, setter_name):
                getattr(widget, setter_name)(value)
    
    def _get_widget_value(self, widget, property_name):
        """獲取 widget 的值"""
        if property_name == 'text':
            return widget.text()
        elif property_name == 'value':
            return widget.value()
        elif property_name == 'checked':
            return widget.isChecked()
        elif property_name == 'plainText':
            return widget.toPlainText()
        elif property_name == 'currentText':
            return widget.currentText()
        else:
            if hasattr(widget, property_name):
                return getattr(widget, property_name)()
            return None


class MenuItemGenerator(QMainWindow):
    """菜單項目生成工具的主視窗"""
    
    def __init__(self, parent=None):
        super().__init__(parent or get_maya_main_window())
        self.setWindowTitle(tr("window_title"))
        self.setMinimumSize(900, 700)
        self.resize(1200, 800)
        
        self.output_dir = Path(__file__).parent.parent / "menuitems"
        self.output_dir.mkdir(exist_ok=True)
        self.data_binding = DataBindingManager()
        
        self.setup_ui()
        self.setup_data_binding()

        self._init_from()
    
    def _init_from(self):
        self.current_file_path = None
        self.current_file_data = None
        self.current_menuitem_index = 0
        self._clear_form()
        self.load_templates()
        self.setup_data_binding_signals()
        self.add_new_menuitem()
        self.on_template_changed(self.template_combo.currentText())

    def setup_ui(self):
        """建立使用者界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        left_panel = self.create_form_panel()
        right_panel = self.create_preview_panel()
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter)

    def create_form_panel(self):
        """建立左側表單面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.edit_status_label = QLabel(tr("edit_status_label"))
        self.edit_status_label.setStyleSheet("QLabel { color: #666; font-style: italic; padding: 4px; }")
        layout.addWidget(self.edit_status_label)
        self.menuitem_selector_group = QGroupBox(tr("menuitem_selector_group"))
        menuitem_grp_layout = QVBoxLayout(self.menuitem_selector_group)
        menuitem_selector_layout = QHBoxLayout(self.menuitem_selector_group)
        self.menuitem_combo = QComboBox()
        self.menuitem_combo.setMinimumContentsLength(20)
        self.menuitem_combo.currentIndexChanged.connect(self.on_menuitem_changed)
        menuitem_selector_layout.addWidget(self.menuitem_combo)
        self.add_menuitem_btn = QPushButton(QIcon(":/addClip.png"), "")
        self.add_menuitem_btn.setToolTip(tr("add_new_menuitem_tooltip"))
        self.add_menuitem_btn.clicked.connect(self.add_new_menuitem)
        self.add_menuitem_btn.setFixedWidth(30)
        self.add_menuitem_btn.setStyleSheet("QPushButton { padding: 0px 0px; }")
        menuitem_selector_layout.addWidget(self.add_menuitem_btn)
        self.remove_menuitem_btn = QPushButton(QIcon(":/deleteClip.png"), "")
        self.remove_menuitem_btn.setToolTip(tr("remove_menuitem_tooltip"))
        self.remove_menuitem_btn.clicked.connect(self.remove_current_menuitem)
        self.remove_menuitem_btn.setFixedWidth(30)
        self.remove_menuitem_btn.setStyleSheet("QPushButton { padding: 0px 0px; }")
        menuitem_selector_layout.addWidget(self.remove_menuitem_btn)
        menuitem_grp_layout.addLayout(menuitem_selector_layout)
        help_label = QLabel(tr("help_label"))
        help_label.setStyleSheet("QLabel { color: #F5F5F5; font-size: 11px; font-style: italic; }")
        menuitem_grp_layout.addWidget(help_label)
        layout.addWidget(self.menuitem_selector_group)
        template_group = QGroupBox(tr("template_group"))
        template_layout = QVBoxLayout(template_group)
        self.template_combo = QComboBox()
        self.template_combo.currentTextChanged.connect(self.on_template_changed)
        template_layout.addWidget(self.template_combo)
        layout.addWidget(template_group)
        basic_group = QGroupBox(tr("basic_group"))
        basic_layout = QFormLayout(basic_group)
        self.menu_path_edit = QLineEdit()
        self.menu_path_edit.setPlaceholderText(tr("menu_path_edit_setplaceholdertext"))
        basic_layout.addRow(tr('menu_path_edit_lable'), self.menu_path_edit)
        self.action_name_edit = QLineEdit()
        self.action_name_edit.setPlaceholderText(tr("action_name_edit_setplaceholdertext"))
        basic_layout.addRow(tr('action_name_edit_label'), self.action_name_edit)
        self.order_spin = QSpinBox()
        self.order_spin.setRange(0, 9999)
        self.order_spin.setValue(100)
        basic_layout.addRow(tr('order_spin_label'), self.order_spin)
        self.separator_check = QCheckBox(tr("separator_check"))
        basic_layout.addRow("", self.separator_check)
        layout.addWidget(basic_group)
        icon_group = QGroupBox(tr("icon_group"))
        icon_layout = QFormLayout(icon_group)
        icon_row = QHBoxLayout()
        icon_layout.addRow(tr("icon_row_lable"), icon_row)
        self.icon_path_edit = QLineEdit()
        self.icon_path_edit.setPlaceholderText(tr("icon_path_edit_setplaceholdertext"))
        self.icon_browse_btn = QPushButton(tr("icon_browse_btn"))
        self.icon_browse_btn.clicked.connect(self.browse_icon)
        self.icon_buildin_btn = QPushButton(tr("icon_buildin_btn"))
        self.icon_buildin_btn.clicked.connect(self.buildin_maya_icons)
        icon_row.addWidget(self.icon_path_edit)
        icon_row.addWidget(self.icon_browse_btn)
        icon_row.addWidget(self.icon_buildin_btn)
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(32, 32)
        self.icon_preview.setStyleSheet("border: 1px solid gray; background-color: #FFFAFA;")
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setText(tr("icon_preview_settext"))
        icon_layout.addRow(tr('icon_preview_lable'), self.icon_preview)
        layout.addWidget(icon_group)
        function_group = QGroupBox(tr("function_group"))
        function_layout = QVBoxLayout(function_group)
        self.has_option_check = QCheckBox(tr("has_option_check"))
        self.has_option_check.toggled.connect(self.toggle_option_ui)
        function_layout.addWidget(self.has_option_check)
        self.has_dockable_check = QCheckBox(tr("has_dockable_check"))
        self.has_dockable_check.setChecked(True)
        self.has_dockable_check.toggled.connect(self.toggle_dockable_ui)
        function_layout.addWidget(self.has_dockable_check)
        layout.addWidget(function_group)
        button_layout = QHBoxLayout()
        self.new_btn = QPushButton(tr("new_btn"))
        self.new_btn.clicked.connect(self.new_file)
        self.new_btn.setStyleSheet("QPushButton { background-color: #4682B4; color: #FFFAFA; padding: 4px; }")
        self.generate_btn = QPushButton(tr("generate_btn"))
        self.generate_btn.clicked.connect(self.generate_file)
        self.generate_btn.setStyleSheet("QPushButton { background-color: #6B8E23; color: #FFFAFA; padding: 4px; }")
        button_layout.addWidget(self.new_btn)
        button_layout.addWidget(self.generate_btn)
        layout.addLayout(button_layout)
        layout.addStretch()
        return panel

    def create_preview_panel(self):
        """建立右側預覽面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        tab_widget = QTabWidget()
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)
        import_button_layout = QHBoxLayout()
        code_layout.addWidget(QLabel(tr("code_preview_label")))
        self.edit_imports_btn = QPushButton(tr("edit_imports_btn"))
        self.edit_imports_btn.clicked.connect(self.edit_imports)
        self.edit_imports_btn.setStyleSheet("QPushButton { background-color: #666666; color: #FFFAFA; padding: 4px 8px; }")
        import_button_layout.addWidget(self.edit_imports_btn)
        code_layout.addLayout(import_button_layout)
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(QFont("Consolas", 9))
        code_layout.addWidget(self.code_preview)
        tab_widget.addTab(code_tab, tr("code_preview_tab"))
        command_tab = QWidget()
        command_layout = QVBoxLayout(command_tab)
        command_layout.addWidget(QLabel(tr("main_command_label")))
        self.main_command_edit = QTextEdit()
        self.main_command_edit.setPlaceholderText(tr("main_command_placeholder"))
        self.main_command_edit.setMaximumHeight(150)
        command_layout.addWidget(self.main_command_edit)
        self.option_widget = QWidget()
        option_layout = QVBoxLayout(self.option_widget)
        option_layout.addWidget(QLabel(tr("option_command_label")))
        self.option_command_edit = QTextEdit()
        self.option_command_edit.setPlaceholderText(tr("option_command_placeholder"))
        self.option_command_edit.setMaximumHeight(100)
        option_layout.addWidget(self.option_command_edit)
        self.option_widget.setVisible(False)
        command_layout.addWidget(self.option_widget)
        self.dockable_widget = QWidget()
        dockable_layout = QFormLayout(self.dockable_widget)
        self.widget_class_edit = QLineEdit()
        self.widget_class_edit.setPlaceholderText(tr("widget_class_placeholder"))
        dockable_layout.addRow(tr("widget_class_label"), self.widget_class_edit)
        self.ui_name_edit = QLineEdit()
        self.ui_name_edit.setPlaceholderText(tr("ui_name_placeholder"))
        dockable_layout.addRow(tr("ui_name_label"), self.ui_name_edit)
        command_layout.addWidget(self.dockable_widget)
        command_layout.addStretch()
        tab_widget.addTab(command_tab, tr("command_tab"))
        files_tab = QWidget()
        files_layout = QVBoxLayout(files_tab)
        files_layout.addWidget(QLabel(tr("generated_files_label")))
        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels(tr("files_tree_headers"))
        self.files_tree.itemDoubleClicked.connect(self.load_existing_file)
        self.files_tree.setColumnWidth(0, 260)
        files_layout.addWidget(self.files_tree)
        files_button_layout = QHBoxLayout()
        refresh_btn = QPushButton(tr("refresh_btn"))
        refresh_btn.clicked.connect(self.refresh_files_list)
        delete_btn = QPushButton(tr("delete_selected_btn"))
        delete_btn.clicked.connect(self.delete_selected_file)
        files_button_layout.addWidget(refresh_btn)
        files_button_layout.addWidget(delete_btn)
        files_layout.addLayout(files_button_layout)
        tab_widget.addTab(files_tab, tr("files_tab"))
        layout.addWidget(tab_widget)
        return panel
        
    def setup_data_binding(self):
        """設置數據綁定映射"""
        self.data_binding.register_binding('action_name', self.action_name_edit, 'text')
        self.data_binding.register_binding('menu_path', self.menu_path_edit, 'text')
        self.data_binding.register_binding('order', self.order_spin, 'value')
        self.data_binding.register_binding('separator_after', self.separator_check, 'checked')
        self.data_binding.register_binding('icon_path', self.icon_path_edit, 'text')
        self.data_binding.register_binding('has_option', self.has_option_check, 'checked')
        self.data_binding.register_binding('has_dockable', self.has_dockable_check, 'checked')
        self.data_binding.register_binding('main_command', self.main_command_edit, 'plainText')
        self.data_binding.register_binding('option_command', self.option_command_edit, 'plainText')
        self.data_binding.register_binding('widget_class', self.widget_class_edit, 'text')
        self.data_binding.register_binding('ui_name', self.ui_name_edit, 'text')
        self.data_binding.register_binding('template', self.template_combo, 'currentText')

    def setup_data_binding_signals(self):
        """設置數據綁定相關的信號連接"""
        for widget in [self.action_name_edit, self.menu_path_edit, self.icon_path_edit, 
                       self.widget_class_edit, self.ui_name_edit]:
            widget.textChanged.connect(self.on_data_changed)
            
        for widget in [self.main_command_edit, self.option_command_edit]:
            widget.textChanged.connect(self.on_data_changed)

        for widget in [self.separator_check, self.has_option_check, self.has_dockable_check]:
            widget.toggled.connect(self.on_data_changed)
            
        self.order_spin.valueChanged.connect(self.on_data_changed)

    def on_data_changed(self):
        """當數據改變時的回調"""
        QTimer.singleShot(100, self.update_preview)

    def sync_data_to_form(self, data):
        """將給定的資料字典內容同步到 UI 表單"""
        self.data_binding.sync_data_to_widgets(data)
        
        self.update_icon_preview(data.get('icon_path', ''))
        self.toggle_option_ui(data.get('has_option', False))
        self.toggle_dockable_ui(data.get('has_dockable', False))
        
        self.update_preview()

    def sync_form_to_data(self):
        """將 UI 表單的內容同步回一個新的資料字典"""
        data, validation_errors = self.data_binding.sync_widgets_to_data()
        
        if validation_errors:
            error_msg = "\n".join(validation_errors)
            QMessageBox.warning(self, tr("validation_error_title"), error_msg)
            return None
        
        # 自動生成 class_name
        data['class_name'] = self.generate_class_name(data.get('action_name', 'Unnamed'))
        return data

    def get_default_menuitem_data(self):
        """獲取預設的 menuitem 數據"""
        return {
            'class_name': 'NewMenuItem',
            'action_name': '',
            'menu_path': 'Tools',
            'order': 100,
            'separator_after': False,
            'icon_path': '',
            'has_option': False,
            'has_dockable': True,
            'main_command': '# Enter the main function here\npass',
            'option_command': '',
            'widget_class': '',
            'ui_name': '',
            'template': 'Simple Command'
        }
        
    def load_templates(self):
        """載入預設模板"""
        templates = {
            "Simple Command": {
                "description": tr("Simple_Command_description"),
                "has_option": False, "has_dockable": False,
                "main_command": tr("simple_command_template")
            },
            "Dockable Tool": {
                "description": tr("Dockable_Tool_description"),
                "has_option": True, "has_dockable": True,
                "main_command": tr("dockable_tool_main"), "option_command": tr("dockable_tool_option")
            },
            "Script Runner": {
                "description": tr("Script_Runner_description"),
                "has_option": False, "has_dockable": False,
                "main_command": tr("script_runner_template")
            }
        }
        self.templates = templates
        self.template_combo.addItems(templates.keys())
        
    def on_template_changed(self, template_name):
        """當模板改變時"""
        if self.current_file_path and self.current_file_data and len(self.current_file_data.get('menuitem', [])) > 1:
            return
            
        if template_name in self.templates:
            template = self.templates[template_name]
            current_data = self.sync_form_to_data()
            if not current_data: return # 數據無效則不繼續
            
            current_data.update({
                "has_option": template.get("has_option", False),
                "has_dockable": template.get("has_dockable", False),
                "main_command": template.get("main_command", ""),
                "option_command": template.get("option_command", "")
            })
            self.sync_data_to_form(current_data)
    
    def on_menuitem_changed(self, index):
        """當選擇的 menuitem 改變時"""
        if not self.current_file_data or index < 0 or self.current_menuitem_index == index:
            return
        
        current_data = self.sync_form_to_data()
        if current_data:
            self.current_file_data['menuitem'][self.current_menuitem_index] = current_data
        
        self.current_menuitem_index = index
        if index < len(self.current_file_data['menuitem']):
            menuitem_data = self.current_file_data['menuitem'][index]
            self.load_menuitem_data_to_form(menuitem_data)
    
    def add_new_menuitem(self):
        """添加新的 MenuItem"""
        if not self.current_file_data:
            current_form_data = self.sync_form_to_data()
            if current_form_data and current_form_data.get('action_name', '').strip():
                self.current_file_data = {
                    'imports': ["from menulib.menuitem_interface import MenuItemInterface", "import maya.cmds as cmds"],
                    'menuitem': [current_form_data]
                }
                self.current_menuitem_index = 0
            else:
                self.current_file_data = {'imports': ["from menulib.menuitem_interface import MenuItemInterface", "import maya.cmds as cmds"], 'menuitem': []}
        else:
            if self.current_menuitem_index < len(self.current_file_data['menuitem']):
                current_data = self.sync_form_to_data()
                if current_data:
                    self.current_file_data['menuitem'][self.current_menuitem_index] = current_data
        
        new_menuitem = self.get_default_menuitem_data()
        item_count = len(self.current_file_data['menuitem'])
        new_menuitem.update({
            'action_name': f'Unname {item_count + 1}',
            'class_name': f"NewMenuItem{item_count + 1}",
            'order': 100 + (item_count * 10),
        })
        
        self.current_file_data['menuitem'].append(new_menuitem)
        self.current_menuitem_index = item_count
        
        self.load_menuitem_data_to_form(new_menuitem)
        self.template_combo.setCurrentText("Simple Command")
        self.update_menuitem_selector()
        self.update_edit_status()
    
    def remove_current_menuitem(self):
        """移除當前 MenuItem"""
        if not self.current_file_data or not self.current_file_data['menuitem']:
            return
            
        if len(self.current_file_data['menuitem']) <= 1:
            QMessageBox.warning(self, tr("warning_title"), tr("min_menuitem_warning"))
            return
            
        menuitem_name = self.current_file_data['menuitem'][self.current_menuitem_index].get('action_name', 'Unknown')
        reply = QMessageBox.question(self, tr("confirm_delete_title"), tr("confirm_delete_menuitem").format(menuitem_name), QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.current_file_data['menuitem'].pop(self.current_menuitem_index)
            if self.current_menuitem_index >= len(self.current_file_data['menuitem']):
                self.current_menuitem_index = len(self.current_file_data['menuitem']) - 1
            
            self.update_menuitem_selector()
            if self.current_file_data['menuitem']:
                self.load_menuitem_data_to_form(self.current_file_data['menuitem'][self.current_menuitem_index])
        
        self.update_edit_status()    
    
    def update_menuitem_selector(self):
        """更新 menuitem 選擇器"""
        self.menuitem_combo.blockSignals(True)
        self.menuitem_combo.clear()
        if self.current_file_data and self.current_file_data['menuitem']:
            for i, menuitem in enumerate(self.current_file_data['menuitem']):
                name = menuitem.get('action_name', f'menuitem {i+1}')
                self.menuitem_combo.addItem(f"{i+1}. {name}")
            self.menuitem_combo.setCurrentIndex(self.current_menuitem_index)
        self.menuitem_combo.blockSignals(False)
    
    # Kept for backward compatibility if any external call relies on it
    def collect_current_menuitem_data(self):
        """收集當前表單的 menuitem 數據"""
        return self.sync_form_to_data()
    
    def edit_imports(self):
        """編輯 import 項目"""
        """
        if not self.current_file_data:
            self.current_file_data = {
                'imports': ["from menulib.menuitem_interface import MenuItemInterface", 
                            "import maya.cmds as cmds"],
                'menuitem': []
            }
        """
        dialog = ImportEditorDialog(self.current_file_data.get('imports', []), self)
        if dialog.exec_() == QDialog.Accepted:
            self.current_file_data['imports'] = dialog.get_imports()
            self.update_preview()
            
    def toggle_option_ui(self, checked):
        """切換 Option UI 顯示"""
        self.option_widget.setVisible(checked)
        # code checking
        
    def toggle_dockable_ui(self, checked):
        """切換 Dockable UI 顯示"""
        self.dockable_widget.setVisible(checked)
        if checked and not self.widget_class_edit.text():
            action_name = self.action_name_edit.text()
            if action_name:
                class_name = action_name.replace(" ", "") + "Widget"
                ui_name = action_name.lower().replace(" ", "") + "Panel"
                self.widget_class_edit.setText(class_name)
                self.ui_name_edit.setText(ui_name)
        
    def browse_icon(self):
        """瀏覽 Icon 檔案"""
        file_path, _ = QFileDialog.getOpenFileName(self, tr("icon_browse_btn"), "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg *.ico)")
        if file_path:
            self.icon_path_edit.setText(file_path)
            self.update_icon_preview(file_path)
    
    def set_builtin_icon(self, file_path):
        """用於接收 resourceBrowser 回傳值的回呼函數"""
        if file_path:
            icon = f":/{file_path}"
            self.icon_path_edit.setText(icon)
            self.update_icon_preview(icon)

    def buildin_maya_icons(self):
        """使用 Maya 內建 Icon 瀏覽器（兼容新舊版本）"""
        import maya.app.general.resourceBrowser as resourceBrowser

        try:
            # 嘗試新版本 Maya (約 2022+) 的非同步回呼方式。
            # 視窗會立即打開，當使用者選擇圖示後，Maya會自動呼叫 self.set_builtin_icon。
            resourceBrowser.resourceBrowser(callback=self.set_builtin_icon)
        except Exception:
            # 如果上方代碼出錯 (例如，在舊版Maya中)，則回溯到原始的同步方法。
            try:
                # 腳本會在此暫停，直到使用者操作完畢。
                browser = resourceBrowser.resourceBrowser()
                file_path = browser.run()
                # 因為 .run() 是同步的，所以我們在這裡直接處理回傳的結果。
                self.set_builtin_icon(file_path)
            except Exception as e:
                # 如果兩種方法都失敗，彈出錯誤提示。
                QMessageBox.critical(self, "Error", f"Failed to open Maya's Resource Browser.\n{e}")
            
    def update_icon_preview(self, icon_path):
        """更新 Icon 預覽"""
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_preview.setPixmap(scaled_pixmap)
            self.icon_preview.setText("")
        elif os.path.exists(icon_path):
             self.icon_preview.clear()
             self.icon_preview.setText(tr("invalid_icon"))
        else:
            self.icon_preview.clear()
            self.icon_preview.setText(tr("no_icon"))
            
    def update_preview(self):
        """更新代碼預覽"""
        QTimer.singleShot(100, self._do_update_preview)
        
    def _do_update_preview(self):
        """實際執行預覽更新"""
        code = self.generate_code()
        self.code_preview.setPlainText(code)
        
    def generate_code(self):
        """生成 Python 代碼"""
        if self.current_file_data and self.current_menuitem_index < len(self.current_file_data.get('menuitem', [])):
            current_data = self.sync_form_to_data()
            if not current_data: return "# Code generation paused due to validation errors."
            self.current_file_data['menuitem'][self.current_menuitem_index] = current_data

        needs_dockable = any(menuitem.get('has_dockable', False) for menuitem in self.current_file_data['menuitem'])
        if needs_dockable:
            dockable_import = "from menulib.ui_mixins import DockableUIMixin"
            if dockable_import not in self.current_file_data['imports']:
                self.current_file_data['imports'].insert(1, dockable_import)
        
        menuitem_names = [menuitem.get('action_name', 'Unknown') for menuitem in self.current_file_data['menuitem']]
        code_lines = [
            f"# Auto-generated menu items: {', '.join(menuitem_names)}",
            f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Contains {len(self.current_file_data['menuitem'])} menuitem(s)",
            "",
            *self.current_file_data.get('imports', []),
            ""
        ]
        
        for i, menuitem_data in enumerate(self.current_file_data['menuitem']):
            if i > 0: code_lines.append("")
            code_lines.extend(self._generate_menuitem_class(menuitem_data))
            
        return '\n'.join(code_lines)
    
    def _generate_menuitem_class(self, menuitem_data):
        """生成單個 menuitem 類別的代碼"""
        class_name = menuitem_data.get('class_name', 'Unnamedmenuitem')
        base_classes = ["MenuItemInterface"]
        if menuitem_data.get('has_dockable', False):
            base_classes.append("DockableUIMixin")
            
        code_lines = [f"class {class_name}({', '.join(base_classes)}):"]
        
        attrs = {
            'ACTION_NAME': f'"{menuitem_data.get("action_name", "Unnamed Tool")}"',
            'MENU_PATH': f'"{menuitem_data.get("menu_path", "")}"',
            'ORDER': f'{menuitem_data.get("order", 100)}'
        }
        if menuitem_data.get('separator_after', False): attrs['SEPARATOR_AFTER'] = 'True'
        if menuitem_data.get('icon_path', ''): attrs['ICON_PATH'] = f'r"{menuitem_data["icon_path"]}"'

        for name, value in attrs.items():
            code_lines.append(f'    {name} = {value}')

        if menuitem_data.get('has_dockable', False):
            widget_class = menuitem_data.get('widget_class', 'None')
            code_lines.extend([
                f'    WIDGET_CLASS = {widget_class}  # TODO: Import your widget class',
                f'    UI_NAME = "{menuitem_data.get("ui_name", "yourPanel")}"',
                f'    UI_LABEL = "{menuitem_data.get("action_name", "Your Tool")}"'
            ])
            
        code_lines.extend([
            "", "    def get_menu_path(self) -> str:", "        return self.MENU_PATH",
            "", "    def get_action_name(self) -> str:", "        return self.ACTION_NAME",
            "", "    def execute(self, *args):"
        ])
        
        main_command = menuitem_data.get('main_command', '').strip()
        code_lines.extend([f"        {line}" for line in main_command.split('\n')] if main_command else ["        pass  # TODO: Implement main function"])
            
        code_lines.extend(["", "    def get_option_box_command(self):"])
        if menuitem_data.get('has_option', False):
            code_lines.extend(["        return self._show_options", "", "    def _show_options(self):"])
            option_command = menuitem_data.get('option_command', '').strip()
            code_lines.extend([f"        {line}" for line in option_command.split('\n')] if option_command else ["        pass  # TODO: Implement option function"])
        else:
            code_lines.append("        return None")
            
        return code_lines
        
    def generate_class_name(self, action_name):
        """從 action name 生成類別名稱"""
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', action_name)
        words = clean_name.split()
        class_name = ''.join(word.capitalize() for word in words)
        return class_name + "MenuItem" if class_name else "UnnamedMenuItem"
        
    def new_file(self):
        """開始新建檔案"""
        has_changes = (self.current_file_path or (self.current_file_data and self.current_file_data.get('menuitem')))
        if has_changes:
            reply = QMessageBox.question(self, tr("confirm_title"), tr("confirm_new_file"), QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes: return
        
        self._init_from()
        """
        self.current_file_path = None  
        self.current_file_data = None
        self.current_menuitem_index = 0
        #self.clear_form()
        
        self.update_menuitem_selector()
        self.update_edit_status()
        self.on_template_changed(self.template_combo.currentText())
        """
        QMessageBox.information(self, tr("new_file_title"), tr("new_file_info"))
        
    def update_edit_status(self):
        """更新編輯狀態顯示"""
        if self.current_file_path:
            filename = Path(self.current_file_path).name
            status_text = tr("edit_mode_status").format(filename)
            self.edit_status_label.setText(status_text)
            self.edit_status_label.setStyleSheet("QLabel { color: #6B8E23; font-weight: bold; padding: 4px; }")
            self.generate_btn.setText(tr("update_btn_text"))
        elif self.current_file_data and self.current_file_data.get('menuitem'):
            menuitem_count = len(self.current_file_data['menuitem'])            
            status_text = tr("new_mode_status").format(menuitem_count)
            self.edit_status_label.setText(status_text)
            self.edit_status_label.setStyleSheet("QLabel { color: #6B8E23; font-weight: bold; padding: 4px; }")
            self.generate_btn.setText(tr("generate_btn"))
        else:
            self.edit_status_label.setText(tr("new_mode_simple"))
            self.edit_status_label.setStyleSheet("QLabel { color: #666; font-style: italic; padding: 4px; }")
            self.generate_btn.setText(tr("generate_btn"))
        
    def load_existing_file(self, item):
        """載入現有檔案進行編輯"""
        file_item = item.parent() if item.parent() else item
        menuitem_index = file_item.indexOfChild(item) if item.parent() else 0
        
        filepath = file_item.data(0, Qt.UserRole)
        filename = file_item.text(0)
        
        try:
            parsed_data = PythonFileParser.parse_menuitem_file(filepath)
            self.current_file_path = filepath
            self.current_file_data = parsed_data
            self.current_menuitem_index = menuitem_index
            
            if parsed_data['menuitem']:
                self.load_menuitem_data_to_form(parsed_data['menuitem'][menuitem_index])
            self.update_menuitem_selector()
            self.update_edit_status()
            
            menuitem_info = ""
            if len(parsed_data['menuitem']) > 1:
                current_menuitem = parsed_data['menuitem'][menuitem_index].get('action_name', 'Unknown')
                menuitem_info = tr("current_editing_info").format(current_menuitem)
            
            QMessageBox.information(self, tr("load_success_title"), tr("load_file_success").format(filename, menuitem_info))
            
        except Exception as e:
            QMessageBox.critical(self, tr("load_failed_title"), tr("load_file_error").format(filename, str(e)))
            
    def load_menuitem_data_to_form(self, menuitem_data):
        """將 menuitem 數據載入到表單中"""
        self.sync_data_to_form(menuitem_data)
        
    def generate_file(self):
        """生成檔案"""
        if self.current_file_data and self.current_menuitem_index < len(self.current_file_data.get('menuitem', [])):
            current_data = self.sync_form_to_data()
            if not current_data: return
            self.current_file_data['menuitem'][self.current_menuitem_index] = current_data
        
        current_menuitem = self.sync_form_to_data()
        if not current_menuitem: return

        if not current_menuitem['action_name'].strip():
            QMessageBox.warning(self, tr("warning_title"), tr("action_name_required"))
            return
        
        if self.current_file_path:
            filepath = Path(self.current_file_path)
            action_text = tr("action_update")
        else:
            safe_name = self.generate_safe_filename(current_menuitem['action_name'])
            filename = f"{safe_name}.py"
            filepath = self.output_dir / filename
            action_text = tr("action_generate")
            if filepath.exists():
                reply = QMessageBox.question(self, tr("warning_title"), tr("file_exists_warning").format(filename), QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes: return
                
        try:
            code = self.generate_code()
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
                
            menuitem_count = len(self.current_file_data['menuitem']) if self.current_file_data else 1
            QMessageBox.information(self, tr("success_title"), tr("file_generated_success").format(action_text, filepath, menuitem_count))
            
            self.refresh_files_list()
            
        except Exception as e:
            QMessageBox.critical(self, tr("error_title"), tr("file_error").format(action_text, str(e)))
            
    def generate_safe_filename(self, name):
        """生成安全的檔名"""
        filePreffix = 'mi_'
        safe_name = re.sub(r'[<>:"/\\|?*]', '', name)
        safe_name = safe_name.replace(' ', '_').lower()
        return filePreffix + (safe_name or "unnamedTool")
        
    def _clear_form(self):
        """清空表單"""
        self.sync_data_to_form(self.get_default_menuitem_data())
        
    def refresh_files_list(self):
        """重新整理檔案列表"""
        self.files_tree.clear()
        if not self.output_dir.exists(): return

        for filepath in self.output_dir.glob("*.py"):
            if not filepath.name.startswith("__"):
                try:
                    # 解析檔案以獲取 menuitem 資訊
                    parsed_data = PythonFileParser.parse_menuitem_file(filepath)
                    menuitem_count = len(parsed_data['menuitem'])
                    
                    # 建立檔案項目
                    file_item = QTreeWidgetItem([filepath.name, str(menuitem_count)])
                    file_item.setData(0, Qt.UserRole, str(filepath))
                    
                    # 如果是當前編輯的檔案，標記為粗體
                    if self.current_file_path and str(filepath) == self.current_file_path:
                        font = file_item.font(0)
                        font.setBold(True)
                        file_item.setFont(0, font)
                        file_item.setToolTip(0, tr("current_editing_file"))
                    
                    # 添加 menuitem 子項目
                    for i, menuitem in enumerate(parsed_data['menuitem']):
                        menuitem_name = menuitem.get('action_name', f'menuitem {i+1}')
                        menuitem_item = QTreeWidgetItem([f"  {menuitem_name}", ""])
                        
                        # 如果是當前編輯的 menuitem，標記
                        if (self.current_file_path and str(filepath) == self.current_file_path and 
                            i == self.current_menuitem_index):
                            font = menuitem_item.font(0)
                            font.setItalic(True)
                            menuitem_item.setFont(0, font)
                            menuitem_item.setToolTip(0, tr("current_editing_menuitem"))
                        
                        file_item.addChild(menuitem_item)
                    
                    self.files_tree.addTopLevelItem(file_item)
                    
                    # 如果是當前編輯的檔案且有多個 menuitem，展開它
                    if (self.current_file_path and str(filepath) == self.current_file_path and 
                        menuitem_count > 1):
                        file_item.setExpanded(True)
                        
                except Exception as e:
                    # 如果解析失敗，仍然顯示檔案但標記為錯誤
                    file_item = QTreeWidgetItem([filepath.name + tr("parse_error"), "?"])
                    file_item.setData(0, Qt.UserRole, str(filepath))
                    file_item.setToolTip(0, tr("parse_error_tooltip").format(str(e)))
                    self.files_tree.addTopLevelItem(file_item)
                    
    def delete_selected_file(self):
        """刪除選中的檔案"""
        current_item = self.files_tree.currentItem()
        if not current_item:
            QMessageBox.information(self, tr("info_title"), tr("select_file_to_delete"))
            return
        
        file_item = current_item.parent() or current_item
        filepath = file_item.data(0, Qt.UserRole)
        filename = file_item.text(0)
        
        msg_key = "confirm_delete_current_file" if self.current_file_path and filepath == self.current_file_path else "confirm_delete_file"
        reply = QMessageBox.question(self, tr("confirm_delete_title"), tr(msg_key).format(filename), QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(filepath)
                
                # 如果刪除的是當前編輯檔案，重置狀態
                if self.current_file_path and filepath == self.current_file_path:
                    self._init_from()
                
                QMessageBox.information(self, tr("success_title"), tr("file_deleted_success").format(filename))
                self.refresh_files_list()
                
            except Exception as e:
                QMessageBox.critical(self, tr("error_title"), tr("delete_file_error").format(str(e)))
        
    def showEvent(self, event):
        """視窗顯示時"""
        super().showEvent(event)
        self.refresh_files_list()
        self.update_preview()
class ImportEditorDialog(QDialog):
    """Import 編輯對話框"""
    def __init__(self, imports_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("import_editor_title"))
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        self.imports_list = imports_list[:]
        self.setup_ui()
        self.load_imports()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("import_editor_info")))
        self.imports_edit = QPlainTextEdit()
        self.imports_edit.setFont(QFont("Consolas", 10))
        self.imports_edit.setPlaceholderText(tr("import_editor_placeholder"))
        layout.addWidget(self.imports_edit)
        quick_group = QGroupBox(tr("common_imports_group"))
        quick_layout = QVBoxLayout(quick_group)
        common_imports = [
            "import maya.cmds as cmds", "import maya.mel as mel", 
            "from PySide2.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel",
            "from PySide2.QtCore import Qt", "import os", "import json", "from pathlib import Path"
        ]
        buttons_layout = QHBoxLayout()
        for i, imp in enumerate(common_imports):
            if i > 0 and i % 2 == 0:
                quick_layout.addLayout(buttons_layout)
                buttons_layout = QHBoxLayout()
            btn_text = imp.split()[1] if 'import' in imp else imp.split('import')[0].strip()[:20] + '...'
            btn = QPushButton(btn_text); btn.setToolTip(imp)
            btn.clicked.connect(lambda checked, import_str=imp: self.add_import(import_str))
            buttons_layout.addWidget(btn)
        quick_layout.addLayout(buttons_layout)
        layout.addWidget(quick_group)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def load_imports(self):
        self.imports_edit.setPlainText('\n'.join(self.imports_list))
        
    def add_import(self, import_str):
        current_text = self.imports_edit.toPlainText()
        if import_str not in current_text:
            self.imports_edit.setPlainText(f"{current_text}\n{import_str}" if current_text else import_str)
                
    def get_imports(self):
        text = self.imports_edit.toPlainText().strip()
        return [line.strip() for line in text.split('\n') if line.strip()] if text else []


class PythonFileParser:
    """解析 Python 檔案內容的輔助類別"""
    
    @staticmethod
    def parse_menuitem_file(filepath):
        """
        解析已生成的插件檔案，提取設定資訊
        現在支援多個 menuitem 類別
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用 AST 解析 Python 檔案
            tree = ast.parse(content)
            
            # 提取 import 語句
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname:
                            imports.append(f"import {alias.name} as {alias.asname}")
                        else:
                            imports.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = []
                    for alias in node.names:
                        if alias.asname:
                            names.append(f"{alias.name} as {alias.asname}")
                        else:
                            names.append(alias.name)
                    imports.append(f"from {module} import {', '.join(names)}")
            
            # 查找所有繼承 MenuItemInterface 的類別
            menuitem_classes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # 檢查是否繼承 MenuItemInterface
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == 'MenuItemInterface':
                            menuitem_classes.append(node)
                            break
            
            if not menuitem_classes:
                raise ValueError("找不到繼承 MenuItemInterface 的類別")
            
            # 解析每個 menuitem 類別
            menuitem_data = []
            for menuitem_class in menuitem_classes:
                single_menuitem_data = PythonFileParser._parse_single_menuitem(content, menuitem_class)
                menuitem_data.append(single_menuitem_data)
            
            return {
                'imports': imports,
                'menuitem': menuitem_data
            }
            
        except Exception as e:
            raise Exception(f"解析檔案失敗: {str(e)}")
    
    @staticmethod
    def _parse_single_menuitem(content, menuitem_class):
        """解析單個 menuitem 類別"""
        result = {
            'class_name': menuitem_class.name,
            'action_name': '',
            'menu_path': '',
            'order': 100,
            'separator_after': False,
            'icon_path': '',
            'has_option': False,
            'has_dockable': False,
            'main_command': '',
            'option_command': '',
            'widget_class': '',
            'ui_name': '',
            'template': 'Simple Command'
        }
        
        # 解析類別屬性
        for node in menuitem_class.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id
                        value = PythonFileParser._get_ast_value(node.value)
                        
                        if attr_name == 'ACTION_NAME':
                            result['action_name'] = value
                        elif attr_name == 'MENU_PATH':
                            result['menu_path'] = value
                        elif attr_name == 'ORDER':
                            result['order'] = int(value) if value is not None else 100
                        elif attr_name == 'SEPARATOR_AFTER':
                            result['separator_after'] = bool(value)
                        elif attr_name == 'ICON_PATH':
                            result['icon_path'] = value or ''
                        elif attr_name == 'WIDGET_CLASS':
                            result['widget_class'] = str(value) if value else ''
                        elif attr_name == 'UI_NAME':
                            result['ui_name'] = value
        
        # 解析方法內容
        for node in menuitem_class.body:
            if isinstance(node, ast.FunctionDef):
                if node.name == 'execute':
                    result['main_command'] = PythonFileParser._extract_method_body(content, node)
                elif node.name == '_show_options':
                    result['option_command'] = PythonFileParser._extract_method_body(content, node)
                    result['has_option'] = True
        
        # 檢查是否有 DockableUIMixin
        for base in menuitem_class.bases:
            if isinstance(base, ast.Name) and base.id == 'DockableUIMixin':
                result['has_dockable'] = True
                break
        
        # 根據特徵判斷模板類型
        if result['has_dockable'] and result['has_option']:
            result['template'] = 'Dockable Tool'
        elif 'execfile' in result['main_command'] or 'exec(open(' in result['main_command']:
            result['template'] = 'Script Runner'
        else:
            result['template'] = 'Simple Command'
            
        return result
    
    @staticmethod
    def _get_ast_value(node):
        """從 AST 節點提取值"""
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        elif isinstance(node, ast.Num):  # Python < 3.8
            return node.n
        elif isinstance(node, ast.NameConstant):  # Boolean/None
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        return None
    
    @staticmethod
    def _extract_method_body(content, method_node):
        """提取方法體的內容（排除定義行）"""
        lines = content.split('\n')
        start_line = method_node.lineno  # 方法定義行
        
        # 找到方法結束行
        end_line = len(lines)
        if hasattr(method_node, 'end_lineno'):
            end_line = method_node.end_lineno
        else:
            # 對於較舊的 Python 版本，尋找下一個同級別的定義
            method_indent = len(lines[start_line - 1]) - len(lines[start_line - 1].lstrip())
            for i in range(start_line, len(lines)):
                line = lines[i]
                if line.strip() and len(line) - len(line.lstrip()) <= method_indent:
                    if not line.strip().startswith('#'):  # 忽略註釋
                        end_line = i
                        break
        
        # 提取方法體內容（跳過定義行）
        method_lines = []
        for i in range(start_line, end_line):
            if i < len(lines):
                line = lines[i]
                # 移除一層縮排
                if line.startswith('        '):  # 8個空格
                    method_lines.append(line[8:])
                elif line.strip() == '':  # 空行
                    method_lines.append('')
                else:
                    method_lines.append(line.lstrip())
        
        # 移除開頭和結尾的空行
        while method_lines and not method_lines[0].strip():
            method_lines.pop(0)
        while method_lines and not method_lines[-1].strip():
            method_lines.pop()
        
        # 過濾掉 pass 語句和 TODO 註釋
        filtered_lines = []
        for line in method_lines:
            stripped = line.strip()
            if stripped == 'pass' or stripped.startswith('pass  # TODO'):
                continue
            if stripped.startswith('# TODO:'):
                continue
            filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
# 全域實例
generator_instance = None

def show_menu_item_generator():
    """顯示菜單項目生成器"""
    global generator_instance
    if generator_instance is None:
        generator_instance = MenuItemGenerator()
    generator_instance.show()
    generator_instance.raise_()
    generator_instance.activateWindow()
    return generator_instance

# 測試用
if __name__ == "__main__":
    show_menu_item_generator()