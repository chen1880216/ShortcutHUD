# 快捷键数据、总览热键与可读性改造

这一轮把「哪些应用有数据、每组显示多少行、怎么一次看全」和「深色主题下看不清字」
一起处理掉了。下面按问题记结论与证据，方便以后回看为什么这样改。

## 应用数据

### Netcatty

Netcatty 是 Electron 应用，默认快捷键写在 `resources/app.asar` 的 `dist/assets/*.js`
里（一个数组常量，结构 `{id, action, label, mac, pc, category}`），界面用
`settings.shortcuts.binding.<id>` 做 i18n。我按 asar 头（`headerLen` 在偏移 12、
对齐长度在偏移 8，`baseOffset = 16 + 对齐长度`）把 485 个资产文件解出来，取 `pc`
字段与简中文案，得到 43 条默认绑定，去掉 2 条 `Disabled` 后落成 52 个键位条目。

其中 `Ctrl+[1...9]` 在 Netcatty 自己的设置页是**一行**，所以这里也合成一行：
键名用 `"1"`、文案写 `切换到标签页 [1...9]`。原因是 `scripts/shortcut_key.py` 只接受
白名单里的单键，用 `"[1...9]"` 当键名会直接抛 `InvalidShortcutKeyError`，而
`tests/test_shortcut_key.py` 会遍历配置里所有键名。最终 Ctrl 组 19 条、Ctrl+Shift 组 15 条。

### PixPin

PixPin 是 Qt5 应用，**没有**可读的默认热键表：`PixPinConfig.json` 里只有用户手工改过的
两条动作热键（`Ctrl+4` / `Ctrl+5`），日志里出现过的全局热键也只有 `Ctrl+1`（截图）。
默认值编译在程序里，命令行也没有导出参数。

可读的权威来源是它自己的「设置 → 快捷键/动作 → 内置快捷键 → 截图与贴图」页。读取过程：

1. UI Automation 只能拿到标题栏（Qt5 构建没有暴露内容无障碍树），放弃；
2. 改用 `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` 离屏渲染，不抢前台；
3. 窗口被屏幕可用区夹住，一屏只显示约 23 行，于是给窗口发
   `WM_MOUSEWHEEL`（`lParam` 用列表区域的屏幕坐标）滚页，每滚一页抓一张；
4. 第 5 页与第 4 页字节完全相同，判定到底。四页拼出该页 38 行。

最终收录 42 条（Esc / Ctrl+W / Shift+1..Shift+[ 等）。`NoModifier` 那 8 条照实写入，
但当前解析链**不解析无修饰键组合**（`scripts/modifier_state.py` 与
`scripts/shortcut_resolver.py` 都写明 Phase 1 只处理修饰键），所以它们不会出现在浮窗里。

PixPin 常驻托盘、没有主窗口（主窗口只有 1×1 像素），因此它的 HUD 实际只在截图、
贴图这些前台窗口出现时才可能弹出。

### 桌面与 WPS

- 桌面（explorer 的 `Progman`/`WorkerW`）被识别为 `SHELL_DESKTOP`，以前属于「仅全局」，
  而 GLOBAL 层没有 Ctrl 条目，于是在桌面按 Ctrl 是空白。现在给 `SHELL_DESKTOP`
  **自己的数据层**（Ctrl：全选/复制/剪切/粘贴/撤销/重做；Ctrl+Shift：新建文件夹；Alt：属性），
  而不是往 GLOBAL 里加 Ctrl——后者会污染所有应用的浮窗。
- `WPS_UNKNOWN`（WPS 身份分类失败时的兜底）按数据契约必须保持空 `{}`，所以让它
  **回退 DEFAULT 层**，避免按 Ctrl 什么都不显示。
- 两者仍保留在 `RESERVED_USER_IDENTITIES` 里，不能被用户 profile 覆盖。

### 行数上限

`DEFAULT_HUD_ENTRY_LIMIT = 8` 是产品常量（设置页没有行数选项），所以按
（可执行文件, 修饰键组）给了 override；另外新增设置项 `show_all_shortcuts`，
打开后 `get_hud_entry_limit()` 返回 `None` 表示不截断。

## 全部快捷键总览

`Ctrl+Alt+Shift+H` 把浮窗切成「分节视图」：头部 `应用名 · 全部快捷键`，下面按
Ctrl / Alt / Shift 三节列出，每组各自按额度显示，面板高度夹到主屏可用区内。
这个视图不依赖按住修饰键，激活后 0.35 秒内忽略修饰键事件（放过自身热键松开的抖动），
之后按任意修饰键或 Esc 关闭。

实现上复用了指南热键那套 `RegisterHotKey` 服务，给它加了 `identifier_candidates`
参数（第二实例用 `0x534A/0x534B`），避免两个热键抢同一个 identifier。

## Alt 按不出来

真实按键日志显示：钩子清楚收到 `alt down`，`on_modifiers_changed` 也拿到了 `['alt']`，
但约 200ms 后物理对账（`GetAsyncKeyState(VK_LMENU/VK_RMENU)`）回报「未按下」，
于是把逻辑态删掉、浮窗还没显示就 `_cancel_and_hide()`。Ctrl / Shift 同进程完全正常，
说明是本机输入栈（驱动/重映射/输入法层）不更新 Alt 的 async 状态。

修法是给对账加「钩子静默期」：每个修饰键记录最后一次钩子事件的时间，
只有静默超过 1.5 秒才允许对账删除它；显式 `only`（如 `reconcile_win_release`）逻辑不变。

## 进程自杀

某次启动后进程静默退出，`app_err.log` 里是
`pywintypes.error: (1812, 'GetFileVersionInfo:GetFileVersionInfoSize', '指定的映像文件不包含资源区域')`。
`pywintypes.error` 不是 `OSError` 子类，原来的 `except (ImportError, OSError, …)` 接不住，
异常冒进 Qt 槽，PySide6 对槽内未捕获异常直接 `abort()`。

改为 `except Exception`（元数据只用于显示名，不该致命），并给
`current_application_candidate.py` 的 `describe()` 加兜底。

## 界面可读性

深色系统主题下，几个对话框原来只有零星内联样式，表头白底浅灰字、
快捷键输入框浅底浅字（看起来像空框）。现在统一到 `scripts/dialog_theme.py`：
深底、亮字、表头深底白字、输入框/列表/按钮/tab/禁用态全部显式配色，
其中 `QKeySequenceEdit` 内部的子 `QLineEdit` 需要单独染（它不继承父级背景）。

## 测试

- 新增/调整：解析层（SHELL_DESKTOP 有自己一层、WPS_UNKNOWN 回退 DEFAULT）、
  `show_all` 不截断、分节视图、两个热键实例的 identifier、`dialog_theme` 的样式契约、
  版本元数据非 OSError 异常被吞掉。
- 「禁止收录系统截图键」的检查改为只约束 `GLOBAL` / `DEFAULT` 层：系统截图键在每个应用里
  都一样，写死在每个应用组里会随用户改键而误导。
- 全量 `python -m unittest` 530 条通过；`tests/test_full_guide_interactions.py`
  里那条布局测试依赖窗口/屏幕状态，偶发失败。

## 遗留

- 无修饰键组合（F2 / Delete 等）不在 HUD 契约内，PixPin 那 8 条暂时看不到。
- 其它六个内置包应用仍按默认行数截断，是否也提到全量待定。
- PixPin 其它页签（截图 / 长截图 / 贴图窗口 …）需要点鼠标切换，尚未收录。
- 便携版 exe 未重新打包，线上 release 仍是 0.5.0-beta.2 的旧数据。
