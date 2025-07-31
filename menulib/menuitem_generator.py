# file: menulib/menu_item_generator.py
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
    QSplitter, QListWidget, QListWidgetItem
)
from PySide2.QtCore import Qt, QTimer
from PySide2.QtGui import QFont, QPixmap, QIcon
import maya.cmds as cmds
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance


def get_maya_main_window():
    """獲取 Maya 主視窗"""
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr:
        return wrapInstance(int(main_window_ptr), QMainWindow)
    return None


class PythonFileParser:
    """解析 Python 檔案內容的輔助類別"""
    
    @staticmethod
    def parse_plugin_file(filepath):
        """
        解析已生成的插件檔案，提取設定資訊
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用 AST 解析 Python 檔案
            tree = ast.parse(content)
            
            # 初始化結果字典
            result = {
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
            
            # 查找類別定義
            plugin_class = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # 檢查是否繼承 PluginInterface
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == 'PluginInterface':
                            plugin_class = node
                            break
                    if plugin_class:
                        break
            
            if not plugin_class:
                raise ValueError("找不到繼承 PluginInterface 的類別")
            
            # 解析類別屬性
            for node in plugin_class.body:
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
                                result['widget_class'] = str(value)
                            elif attr_name == 'UI_NAME':
                                result['ui_name'] = value
            
            # 解析方法內容
            for node in plugin_class.body:
                if isinstance(node, ast.FunctionDef):
                    if node.name == 'execute':
                        result['main_command'] = PythonFileParser._extract_method_body(content, node)
                    elif node.name == '_show_options':
                        result['option_command'] = PythonFileParser._extract_method_body(content, node)
                        result['has_option'] = True
            
            # 檢查是否有 DockableUIMixin
            if plugin_class:
                for base in plugin_class.bases:
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
            
        except Exception as e:
            raise Exception(f"解析檔案失敗: {str(e)}")
    
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


class MenuItemGenerator(QMainWindow):
    """菜單項目生成工具的主視窗"""
    
    def __init__(self, parent=None):
        super().__init__(parent or get_maya_main_window())
        self.setWindowTitle("Menu Item Generator")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        # 設定輸出目錄
        self.output_dir = Path(__file__).parent.parent / "menu_items"
        self.output_dir.mkdir(exist_ok=True)
        
        # 當前編輯的檔案路徑（用於更新現有檔案）
        self.current_file_path = None
        
        # 設定 UI
        self.setup_ui()
        self.load_templates()
        
    def setup_ui(self):
        """建立使用者界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主要佈局
        main_layout = QHBoxLayout(central_widget)
        
        # 左側：表單區域
        left_panel = self.create_form_panel()
        
        # 右側：預覽和管理區域
        right_panel = self.create_preview_panel()
        
        # 使用分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        
        main_layout.addWidget(splitter)
        
    def create_form_panel(self):
        """建立左側表單面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 當前編輯狀態顯示
        self.edit_status_label = QLabel("模式: 新建檔案")
        self.edit_status_label.setStyleSheet("QLabel { color: #666; font-style: italic; padding: 4px; }")
        layout.addWidget(self.edit_status_label)
        
        # 模板選擇
        template_group = QGroupBox("選擇模板")
        template_layout = QVBoxLayout(template_group)
        
        self.template_combo = QComboBox()
        self.template_combo.currentTextChanged.connect(self.on_template_changed)
        template_layout.addWidget(self.template_combo)
        
        layout.addWidget(template_group)
        
        # 基本設定
        basic_group = QGroupBox("基本設定")
        basic_layout = QFormLayout(basic_group)
        
        # 菜單路徑
        self.menu_path_edit = QLineEdit("Tools")
        self.menu_path_edit.setPlaceholderText("例如: Tools/Rigging")
        basic_layout.addRow("菜單路徑:", self.menu_path_edit)
        
        # 按鍵名稱
        self.action_name_edit = QLineEdit()
        self.action_name_edit.setPlaceholderText("例如: Super Rigger")
        self.action_name_edit.textChanged.connect(self.update_preview)
        basic_layout.addRow("按鍵名稱:", self.action_name_edit)
        
        # 排序
        self.order_spin = QSpinBox()
        self.order_spin.setRange(0, 9999)
        self.order_spin.setValue(100)
        basic_layout.addRow("排序 (ORDER):", self.order_spin)
        
        # 分隔線
        self.separator_check = QCheckBox("在此項目後加入分隔線")
        basic_layout.addRow("", self.separator_check)
        
        layout.addWidget(basic_group)
        
        # Icon 設定
        icon_group = QGroupBox("圖示設定")
        icon_layout = QFormLayout(icon_group)
        
        icon_row = QHBoxLayout()
        self.icon_buildin_btn = QPushButton("build-in")
        self.icon_buildin_btn.clicked.connect(self.buildin_maya_icons)
        
        self.icon_path_edit = QLineEdit()
        self.icon_path_edit.setPlaceholderText("選擇圖示文件...")
        self.icon_browse_btn = QPushButton("瀏覽")
        self.icon_browse_btn.clicked.connect(self.browse_icon)

        icon_row.addWidget(self.icon_path_edit)
        icon_row.addWidget(self.icon_browse_btn)
        icon_row.addWidget(self.icon_buildin_btn)
                
        icon_layout.addRow("Icon 路徑:", icon_row)
        
        # Icon 預覽
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(32, 32)
        self.icon_preview.setStyleSheet("border: 1px solid gray; background-color: white;")
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setText("無")
        icon_layout.addRow("預覽:", self.icon_preview)
        
        layout.addWidget(icon_group)
        
        # 功能設定
        function_group = QGroupBox("功能設定")
        function_layout = QVBoxLayout(function_group)
        
        # Option Box
        self.has_option_check = QCheckBox("需要 Option Box")
        self.has_option_check.toggled.connect(self.toggle_option_ui)
        function_layout.addWidget(self.has_option_check)
        
        # Dockable UI
        self.has_dockable_check = QCheckBox("需要 Dockable 面板")
        self.has_dockable_check.setChecked(True)
        self.has_dockable_check.toggled.connect(self.toggle_dockable_ui)
        function_layout.addWidget(self.has_dockable_check)
        
        layout.addWidget(function_group)
        
        # 按鈕區域
        button_layout = QHBoxLayout()
        
        self.new_btn = QPushButton("新建檔案")
        self.new_btn.clicked.connect(self.new_file)
        self.new_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px; }")
        
        self.generate_btn = QPushButton("生成檔案")
        self.generate_btn.clicked.connect(self.generate_file)
        self.generate_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        
        self.clear_btn = QPushButton("清空表單")
        self.clear_btn.clicked.connect(self.clear_form)
        
        button_layout.addWidget(self.new_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.generate_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return panel
        
    def create_preview_panel(self):
        """建立右側預覽面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Tab Widget
        tab_widget = QTabWidget()
        
        # 代碼預覽頁
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)
        
        code_layout.addWidget(QLabel("生成的代碼預覽:"))
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(QFont("Consolas", 9))
        code_layout.addWidget(self.code_preview)
        
        tab_widget.addTab(code_tab, "代碼預覽")
        
        # 指令編輯頁
        command_tab = QWidget()
        command_layout = QVBoxLayout(command_tab)
        
        # 主要指令
        command_layout.addWidget(QLabel("主要執行指令:"))
        self.main_command_edit = QTextEdit()
        self.main_command_edit.setPlaceholderText("# 在這裡輸入 Maya Python 指令\n# 例如:\n# cmds.polyCube()")
        self.main_command_edit.textChanged.connect(self.update_preview)
        self.main_command_edit.setMaximumHeight(150)
        command_layout.addWidget(self.main_command_edit)
        
        # Option 指令區域
        self.option_widget = QWidget()
        option_layout = QVBoxLayout(self.option_widget)
        option_layout.addWidget(QLabel("Option Box 指令:"))
        self.option_command_edit = QTextEdit()
        self.option_command_edit.setPlaceholderText("# Option Box 的指令\n# 通常用來開啟設定視窗")
        self.option_command_edit.textChanged.connect(self.update_preview)
        self.option_command_edit.setMaximumHeight(100)
        option_layout.addWidget(self.option_command_edit)
        self.option_widget.setVisible(False)
        command_layout.addWidget(self.option_widget)
        
        # Dockable UI 設定
        self.dockable_widget = QWidget()
        dockable_layout = QFormLayout(self.dockable_widget)
        
        self.widget_class_edit = QLineEdit()
        self.widget_class_edit.setPlaceholderText("例如: MyToolWidget")
        self.widget_class_edit.textChanged.connect(self.update_preview)
        dockable_layout.addRow("Widget 類別名稱:", self.widget_class_edit)
        
        self.ui_name_edit = QLineEdit()
        self.ui_name_edit.setPlaceholderText("例如: myToolPanel")
        self.ui_name_edit.textChanged.connect(self.update_preview)
        dockable_layout.addRow("UI 名稱:", self.ui_name_edit)
        
        command_layout.addWidget(self.dockable_widget)
        
        command_layout.addStretch()
        tab_widget.addTab(command_tab, "指令編輯")
        
        # 已生成文件列表頁
        files_tab = QWidget()
        files_layout = QVBoxLayout(files_tab)
        
        files_layout.addWidget(QLabel("已生成的檔案:"))
        self.files_list = QListWidget()
        self.files_list.itemDoubleClicked.connect(self.load_existing_file)
        files_layout.addWidget(self.files_list)
        
        files_button_layout = QHBoxLayout()
        refresh_btn = QPushButton("重新整理")
        refresh_btn.clicked.connect(self.refresh_files_list)
        delete_btn = QPushButton("刪除選中檔案")
        delete_btn.clicked.connect(self.delete_selected_file)
        files_button_layout.addWidget(refresh_btn)
        files_button_layout.addWidget(delete_btn)
        files_layout.addLayout(files_button_layout)
        
        tab_widget.addTab(files_tab, "檔案管理")
        
        layout.addWidget(tab_widget)
        
        return panel
        
    def load_templates(self):
        """載入預設模板"""
        templates = {
            "Simple Command": {
                "description": "簡單指令執行",
                "has_option": False,
                "has_dockable": False,
                "main_command": "# 在這裡輸入 Maya Python 指令\n# 例如:\n# cmds.polyCube()"
            },
            "Dockable Tool": {
                "description": "帶 UI 面板的工具",
                "has_option": True,
                "has_dockable": True,
                "main_command": "# 顯示 UI 面板\nself.show_ui()",
                "option_command": "# 開啟選項視窗\n# 例如顯示設定對話框"
            },
            "Script Runner": {
                "description": "執行外部腳本",
                "has_option": False,
                "has_dockable": False,
                "main_command": "# 執行外部腳本文件\n# execfile('/path/to/your/script.py')"
            }
        }
        
        self.templates = templates
        self.template_combo.addItems(templates.keys())
        
    def on_template_changed(self, template_name):
        """當模板改變時"""
        # 如果正在編輯現有檔案，不要自動應用模板
        if self.current_file_path:
            return
            
        if template_name in self.templates:
            template = self.templates[template_name]
            
            # 設定 checkbox
            self.has_option_check.setChecked(template.get("has_option", False))
            self.has_dockable_check.setChecked(template.get("has_dockable", False))
            
            # 設定指令文本
            self.main_command_edit.setPlainText(template.get("main_command", ""))
            if template.get("option_command"):
                self.option_command_edit.setPlainText(template["option_command"])
                
    def toggle_option_ui(self, checked):
        """切換 Option UI 顯示"""
        self.option_widget.setVisible(checked)
        self.update_preview()
        
    def toggle_dockable_ui(self, checked):
        """切換 Dockable UI 顯示"""
        self.dockable_widget.setVisible(checked)
        if checked and not self.widget_class_edit.text():
            # 自動生成預設值
            action_name = self.action_name_edit.text()
            if action_name:
                class_name = action_name.replace(" ", "") + "Widget"
                ui_name = action_name.lower().replace(" ", "") + "Panel"
                self.widget_class_edit.setText(class_name)
                self.ui_name_edit.setText(ui_name)
        self.update_preview()

    def unzip_maya_icons(self):
        """解壓 Maya 預設 Icon 文件"""
        for item in cmds.resourceManager(nameFilter='*'):
            try:
                maya_app_dir = cmds.internalVar(userAppDir=True)
                target_icon_path = Path(maya_app_dir) / cmds.about(version=True) / "prefs" / "icons"/ item
                #Make sure the folder exists before attempting.
                cmds.resourceManager(saveAs=
                    (
                        item, 
                        target_icon_path
                    )
                )
            except Exception as e:
                #For the cases in which some files do not work for windows, name formatting wise. I'm looking at you 'http:'!
                print(f"Warning: Could not unzip {item}: {e}")

    def buildin_maya_icons(self):
        import maya.app.general.resourceBrowser as resourceBrowser
        resource_browser = resourceBrowser.resourceBrowser()
        file_path = resource_browser.run()
        prefix = ':/'
        if file_path:
            icon = prefix+file_path
            self.icon_path_edit.setText(icon)
            self.update_icon_preview(icon)

        return file_path

    def browse_icon(self):
        """瀏覽 Icon 檔案"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "選擇圖示檔案", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg *.ico)"
        )
        if file_path:
            self.icon_path_edit.setText(file_path)
            self.update_icon_preview(file_path)
            
    def update_icon_preview(self, icon_path):
        """更新 Icon 預覽"""
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.icon_preview.setPixmap(scaled_pixmap)
                self.icon_preview.setText("")
            else:
                self.icon_preview.clear()
                self.icon_preview.setText("無效")
        else:
            self.icon_preview.clear()
            self.icon_preview.setText("無")
            
    def update_preview(self):
        """更新代碼預覽"""
        QTimer.singleShot(100, self._do_update_preview)  # 延遲更新避免頻繁刷新
        
    def _do_update_preview(self):
        """實際執行預覽更新"""
        code = self.generate_code()
        self.code_preview.setPlainText(code)
        
    def generate_code(self):
        """生成 Python 代碼"""
        # 收集表單數據
        data = self.collect_form_data()
        
        # 生成代碼
        code_lines = []
        
        # 頭部註釋
        code_lines.extend([
            f"# Auto-generated menu item: {data['action_name']}",
            f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Template: {self.template_combo.currentText()}",
            ""
        ])
        
        # 導入
        imports = [
            "from menulib.plugin_interface import PluginInterface"
        ]
        
        if data['has_dockable']:
            imports.append("from menulib.ui_mixins import DockableUIMixin")
            
        imports.extend([
            "import maya.cmds as cmds",
            ""
        ])
        
        code_lines.extend(imports)
        
        # 類別定義
        class_name = self.generate_class_name(data['action_name'])
        base_classes = ["PluginInterface"]
        if data['has_dockable']:
            base_classes.append("DockableUIMixin")
            
        code_lines.append(f"class {class_name}({', '.join(base_classes)}):")
        
        # 類別屬性
        code_lines.extend([
            f'    ACTION_NAME = "{data["action_name"]}"',
            f'    MENU_PATH = "{data["menu_path"]}"',
            f'    ORDER = {data["order"]}'
        ])
        
        if data['separator_after']:
            code_lines.append('    SEPARATOR_AFTER = True')
            
        if data['icon_path']:
            code_lines.append(f'    ICON_PATH = r"{data["icon_path"]}"')
            
        if data['has_dockable']:
            code_lines.extend([
                f'    WIDGET_CLASS = {data["widget_class"]}  # TODO: Import your widget class',
                f'    UI_NAME = "{data["ui_name"]}"',
                f'    UI_LABEL = "{data["action_name"]}"'
            ])
            
        code_lines.append("")
        
        # 方法
        code_lines.extend([
            "    def get_menu_path(self) -> str:",
            "        return self.MENU_PATH",
            "",
            "    def get_action_name(self) -> str:",
            "        return self.ACTION_NAME",
            "",
            "    def execute(self, *args):"
        ])
        
        # 主要執行代碼
        main_command = data['main_command'].strip()
        if main_command:
            for line in main_command.split('\n'):
                code_lines.append(f"        {line}")
        else:
            code_lines.append("        pass  # TODO: 實作主要功能")
            
        # Option Box 方法
        if data['has_option']:
            code_lines.extend([
                "",
                "    def get_option_box_command(self):",
                "        return self._show_options",
                "",
                "    def _show_options(self):"
            ])
            
            option_command = data['option_command'].strip()
            if option_command:
                for line in option_command.split('\n'):
                    code_lines.append(f"        {line}")
            else:
                code_lines.append("        pass  # TODO: 實作選項功能")
        else:
            code_lines.extend([
                "",
                "    def get_option_box_command(self):",
                "        return None"
            ])
            
        return '\n'.join(code_lines)
        
    def collect_form_data(self):
        """收集表單數據"""
        return {
            'action_name': self.action_name_edit.text() or "Unnamed Tool",
            'menu_path': self.menu_path_edit.text() or "",
            'order': self.order_spin.value(),
            'separator_after': self.separator_check.isChecked(),
            'icon_path': self.icon_path_edit.text(),
            'has_option': self.has_option_check.isChecked(),
            'has_dockable': self.has_dockable_check.isChecked(),
            'main_command': self.main_command_edit.toPlainText(),
            'option_command': self.option_command_edit.toPlainText(),
            'widget_class': self.widget_class_edit.text(),
            'ui_name': self.ui_name_edit.text()
        }
        
    def generate_class_name(self, action_name):
        """從 action name 生成類別名稱"""
        # 移除特殊字符，轉換為 PascalCase
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', action_name)
        words = clean_name.split()
        class_name = ''.join(word.capitalize() for word in words)
        return class_name + "MenuItem" if class_name else "UnnamedMenuItem"
        
    def new_file(self):
        """開始新建檔案"""
        if self.current_file_path:
            reply = QMessageBox.question(
                self, "確認", 
                "目前正在編輯檔案，是否要開始新建？未保存的變更將遺失。",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        self.current_file_path = None
        self.clear_form()
        self.update_edit_status()
        
    def update_edit_status(self):
        """更新編輯狀態顯示"""
        if self.current_file_path:
            filename = Path(self.current_file_path).name
            self.edit_status_label.setText(f"模式: 編輯檔案 - {filename}")
            self.edit_status_label.setStyleSheet("QLabel { color: #FF9800; font-weight: bold; padding: 4px; }")
            self.generate_btn.setText("更新檔案")
        else:
            self.edit_status_label.setText("模式: 新建檔案")
            self.edit_status_label.setStyleSheet("QLabel { color: #666; font-style: italic; padding: 4px; }")
            self.generate_btn.setText("生成檔案")
        
    def load_existing_file(self, item):
        """載入現有檔案進行編輯"""
        filepath = item.data(Qt.UserRole)
        filename = item.text()
        
        try:
            # 解析檔案內容
            parsed_data = PythonFileParser.parse_plugin_file(filepath)
            
            # 設定當前編輯檔案
            self.current_file_path = filepath
            
            # 載入數據到表單
            self.load_data_to_form(parsed_data)
            
            # 更新狀態
            self.update_edit_status()
            
            QMessageBox.information(
                self, "載入成功", 
                f"檔案 {filename} 已載入到表單中，您可以進行編輯。"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, "載入失敗", 
                f"無法載入檔案 {filename}：\n{str(e)}\n\n這可能是因為檔案格式不符合預期或檔案已損壞。"
            )
            
    def load_data_to_form(self, data):
        """將解析的數據載入到表單中"""
        # 基本設定
        self.action_name_edit.setText(data.get('action_name', ''))
        self.menu_path_edit.setText(data.get('menu_path', ''))
        self.order_spin.setValue(data.get('order', 1))
        
        # 分隔線和圖示
        self.separator_check.setChecked(data.get('separator_after', False))
        icon_path = data.get('icon_path', '')
        self.icon_path_edit.setText(icon_path)
        if icon_path:
            self.update_icon_preview(icon_path)
        
        # 功能設定
        self.has_option_check.setChecked(data.get('has_option', False))
        self.has_dockable_check.setChecked(data.get('has_dockable', False))
        
        # 指令內容
        self.main_command_edit.setPlainText(data.get('main_command', ''))
        self.option_command_edit.setPlainText(data.get('option_command', ''))
        
        # Dockable UI 設定
        self.widget_class_edit.setText(data.get('widget_class', ''))
        self.ui_name_edit.setText(data.get('ui_name', ''))
        
        # 模板選擇（根據解析結果）
        template_name = data.get('template', 'Simple Command')
        index = self.template_combo.findText(template_name)
        if index >= 0:
            self.template_combo.setCurrentIndex(index)
        
        # 觸發 UI 更新
        self.toggle_option_ui(data.get('has_option', False))
        self.toggle_dockable_ui(data.get('has_dockable', False))
        self.update_preview()
        
    def generate_file(self):
        """生成檔案"""
        data = self.collect_form_data()
        
        # 驗證
        if not data['action_name'].strip():
            QMessageBox.warning(self, "錯誤", "請輸入按鍵名稱！")
            return
        
        # 確定檔案路徑
        if self.current_file_path:
            # 更新現有檔案
            filepath = Path(self.current_file_path)
            action_text = "更新"
        else:
            # 新建檔案
            safe_name = self.generate_safe_filename(data['action_name'])
            filename = f"{safe_name}.py"
            filepath = self.output_dir / filename
            action_text = "生成"
            
            # 檢查檔案是否存在
            if filepath.exists():
                reply = QMessageBox.question(
                    self, "檔案已存在", 
                    f"檔案 {filename} 已存在，是否覆蓋？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
                
        # 寫入檔案
        try:
            code = self.generate_code()
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
                
            QMessageBox.information(
                self, "成功", 
                f"檔案已{action_text}：\n{filepath}"
            )
            
            # 如果是新建檔案，設定為當前編輯檔案
            if not self.current_file_path:
                self.current_file_path = str(filepath)
                self.update_edit_status()
            
            self.refresh_files_list()
            
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"{action_text}檔案時發生錯誤：\n{str(e)}")
            
    def generate_safe_filename(self, name):
        """生成安全的檔名"""
        import re
        # 移除或替換不安全的字符
        safe_name = re.sub(r'[<>:"/\\|?*]', '', name)
        safe_name = safe_name.replace(' ', '_').lower()
        return safe_name or "unnamed_tool"
        
    def clear_form(self):
        """清空表單"""
        self.action_name_edit.clear()
        self.menu_path_edit.setText("Tools")
        self.order_spin.setValue(100)
        self.separator_check.setChecked(False)
        self.icon_path_edit.clear()
        self.has_option_check.setChecked(False)
        self.has_dockable_check.setChecked(True)
        self.main_command_edit.clear()
        self.option_command_edit.clear()
        self.widget_class_edit.clear()
        self.ui_name_edit.clear()
        self.update_icon_preview("")
        self.update_preview()
        
    def refresh_files_list(self):
        """重新整理檔案列表"""
        self.files_list.clear()
        if self.output_dir.exists():
            for filepath in self.output_dir.glob("*.py"):
                if not filepath.name.startswith("__"):
                    item = QListWidgetItem(filepath.name)
                    item.setData(Qt.UserRole, str(filepath))
                    
                    # 如果是當前編輯的檔案，標記為粗體
                    if self.current_file_path and str(filepath) == self.current_file_path:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                        item.setToolTip("當前編輯中的檔案")
                    
                    self.files_list.addItem(item)
                    
    def delete_selected_file(self):
        """刪除選中的檔案"""
        current_item = self.files_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "請先選擇要刪除的檔案。")
            return
            
        filepath = current_item.data(Qt.UserRole)
        filename = current_item.text()
        
        # 檢查是否要刪除當前編輯的檔案
        if self.current_file_path and filepath == self.current_file_path:
            reply = QMessageBox.question(
                self, "確認刪除", 
                f"檔案 {filename} 是當前編輯中的檔案，刪除後將清空表單。\n確定要刪除嗎？",
                QMessageBox.Yes | QMessageBox.No
            )
        else:
            reply = QMessageBox.question(
                self, "確認刪除", 
                f"確定要刪除檔案 {filename} 嗎？",
                QMessageBox.Yes | QMessageBox.No
            )
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(filepath)
                
                # 如果刪除的是當前編輯檔案，重置狀態
                if self.current_file_path and filepath == self.current_file_path:
                    self.current_file_path = None
                    self.clear_form()
                    self.update_edit_status()
                
                QMessageBox.information(self, "成功", f"檔案 {filename} 已刪除。")
                self.refresh_files_list()
                
            except Exception as e:
                QMessageBox.critical(self, "錯誤", f"刪除檔案時發生錯誤：\n{str(e)}")
        
    def showEvent(self, event):
        """視窗顯示時"""
        super().showEvent(event)
        self.refresh_files_list()
        self.update_preview()


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
        