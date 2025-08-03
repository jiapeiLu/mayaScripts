# mayaScripts
Some handy scripts, I wrote for myself or my colleague.
# vtxMatch.py
This is a Maya script that can match the vertices of two vertex sets by the nearest distance and can also copy the normals.

[Demo Video](https://youtu.be/J2RodFLoYMM)

Please place the file in the `maya\scripts` folder within the Documents directory.

It requires `numpy`. To install `numpy`, navigate to the Maya application directory (which looks like “C:\Program Files\Autodesk\Maya2023\bin”).

Inside the folder, shift and right-click the mouse. Choose 'Open PowerShell window here', then type:

`shell`
```shell
mayapy.exe -m pip install --user numpy
```

or try

```shell
.\mayapy.exe -m pip install --user numpy
```
if you have target project script folder
```shell
.\mayapy.exe -m pip install numpy --target "path\to\project\scripts"
```

Maya Usage:

`Python`
```python
import vtxMatch
vtxMatch.main()
```

# menulib 系統提供了以下功能：
- 自動掃描和載入菜單
- 支援自定義及內建 Icon
- 分離按鈕（主功能 + Option Box）
- Dockable UI 支援
- 視覺化的菜單項目生成器

## 目錄結構

```
menulib/
├── config.json              # 配置文件（可選）
├── core/                    # 核心庫
│   ├── __init__.py
│   ├── menu_manager.py         # 主要管理器
│   ├── menu_item_generator.py  # 生成器工具
│   ├── menuitem_interface.py   # 插件接口
│   └── ui_mixins.py            # UI 混合類
│ 
├── languagelib/             
│   └── language.py             # UI 語言包
│   └── language_manager.py     # 翻譯器
│ 
└── menuitems/             
    └── example_tool.py    # 手動編寫的插件範例
    └── vtxMatch.py        # 生成器產出的插件範例
```

## 快速開始

### 1. 初始化菜單

在 Maya Script Editor 中執行：

```python
# 導入並初始化菜單
sys.path.append(r"maya\scripts") #the dir where the menulib goes to.
import menulib
menulib.initialize_menu()
#menulib.teardown_menu() # remove menu
```

### 2. 使用生成器創建菜單項目
```python
# 啟動菜單項目生成器
menulib.show_menu_generator()
```

## 使用生成器

### 模板選擇
系統提供三種預設模板：
1. **Simple Command**: 執行簡單的 Maya 指令
2. **Dockable Tool**: 帶 UI 面板的工具
3. **Script Runner**: 執行外部腳本文件

### 基本設定
1. **菜單路徑**: 定義菜單的位置，例如 `"Tools/Rigging"`
2. **按鍵名稱**: 顯示在菜單上的名稱
3. **排序**: 控制菜單項目的順序 (越小越前面)
4. **Icon**: 可選，支援 PNG, JPG, SVG 等格式

### 功能選項
- **Option Box**: 勾選後可定義額外的選項功能
- **Dockable 面板**: 勾選後工具會創建可停靠的 UI 面板

### 指令編輯
在 "指令編輯" 頁面中：
- **主要執行指令**: 點擊菜單項目時執行的 Maya Python 代碼
- **Option Box 指令**: 點擊選項按鈕時執行的代碼

## 手動創建插件

如果需要更複雜的功能，可以手動創建插件：

```python
# file: menu_plugins/my_tool.py
from menulib.plugin_interface import PluginInterface
import maya.cmds as cmds

class MyToolPlugin(PluginInterface):
    # 元數據
    ACTION_NAME = "My Amazing Tool"
    MENU_PATH = "Tools/Custom"
    ORDER = 100
    ICON_PATH = r"C:\path\to\icon.png"  # 可選
    
    def get_menu_path(self) -> str:
        return self.MENU_PATH
        
    def get_action_name(self) -> str:
        return self.ACTION_NAME
        
    def execute(self, *args):
        # 主要功能
        cmds.polyCube()
        
    def get_option_box_command(self):
        return self._show_options  # 如果需要選項
        
    def _show_options(self):
        # 選項功能
        pass
```

## 高級功能

### 1. Dockable UI

使用 `DockableUIMixin` 創建可停靠的工具面板：

```python
from menulib.ui_mixins import DockableUIMixin

class MyDockableToolPlugin(PluginInterface, DockableUIMixin):
    # UI 設定
    WIDGET_CLASS = MyCustomWidget  # 你的 QWidget 類別
    UI_NAME = "myToolPanel"
    UI_LABEL = "My Tool"
    
    def execute(self, *args):
        self.show_ui()  # 顯示可停靠面板
```

### 2. 自定義 Icon

支援的格式：PNG, JPG, JPEG, BMP, GIF, SVG, ICO

```python
class MyIconToolPlugin(PluginInterface):
    ICON_PATH = r"C:\icons\my_tool.png"
    # ... 其他設定
```

### 3. 菜單分隔線

```python
class MyToolPlugin(PluginInterface):
    SEPARATOR_AFTER = True  # 在此項目後加入分隔線
    # ... 其他設定
```

## 配置文件
 `config.json` 自定義設定：

```json
{
  "main_menu_title": "Menu Tools",
  "log_modes": ["DEBUG", "INFO", "WARNING", "ERROR"],
  "log_level": "ERROR" ,
  "languages_modes":["zh_tw","en_us"], 
  "language": "en_us"
}
```

## 常見問題

### Q: 生成的文件在哪裡？
A: 在 `menulib/menu_items/` 目錄中

### Q: 如何刪除菜單？
A: 執行 `menu_manager.teardown_menu()`

### Q: Icon 不顯示怎麼辦？
A: 檢查文件路徑是否正確，支援的格式，以及文件權限

## 最佳實踐

1. **命名規範**: 使用描述性的類別名稱和文件名
2. **排序規劃**: 為相關工具使用相近的 ORDER 值
3. **Icon 標準**: 使用 16x16 或 24x24 像素的 Icon
4. **錯誤處理**: 在 execute 方法中加入適當的錯誤處理
5. **文檔註釋**: 為複雜的插件添加詳細註釋

## 範例文件

參考 `menu_plugins/example_tool.py` 來了解完整的插件實現。
