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

## 打包版启动即崩（ICU 顶替）

出 release 时第一次跑 `scripts/build_windows.py` 很顺利（229 files / 153.8 MiB），
但 `dist/ShortcutHUD/ShortcutHUD.exe` 一启动就退出：

```
ImportError: DLL load failed while importing QtWidgets: 找不到指定的程序。
```

`_internal/PySide6/Qt6Core.dll` 与 venv 里同名文件 SHA256 完全一致，`shiboken6.abi3.dll`、
`python313.dll` 都能加载，唯独 `Qt6Core/Gui/Widgets` 与 `pyside6.abi3.dll` 报 127
（`ERROR_PROC_NOT_FOUND`，不是「找不到文件」）。把 `api-ms-win-*` 与根目录的
`VCRUNTIME140*.dll` 移走仍报 127，可以先排除 CRT 版本问题。

写了个极简 PE 导入表解析器逐条比对导出符号，才看到真正缺的是：

```
[dll] icuuc.dll: MISSING 20 -> ['ucnv_open', 'ucnv_close', 'UCNV_FROM_U_CALLBACK_SUBSTITUTE', ...]
```

PySide6 的 Qt6Core 在 Windows 上链接的是**系统 ICU**（`C:\Windows\System32\icuuc.dll`，
符号无版本后缀）。构建机的 `PATH` 里有 conda，PyInstaller 顺手把
`miniconda3\Library\bin\icuuc.dll` + `icudt73.dll` 收进了包根目录；那是带 `_73` 后缀的
发行版，导不出 `ucnv_open`，于是 Qt6Core 加载失败。跑源码没事，是因为此时
Windows ICU 从 System32 解析到了。

修法在 `packaging/ShortcutHUD.spec`：进 `COLLECT` 前过滤掉 `icu*.dll`
（`_drop_bundled_icu`），让打包版也用系统 ICU。重建后 227 files / 120.6 MiB，
exe 启动正常；解压 zip 再跑一遍同样正常。

顺带把发布脚本收窄了：`dist/config` 只带 `shortcuts.json` + `shortcut_packs`，
`settings.json` 只写 `{"language":"zh_CN"}`，其余键首启合并默认值——不再把开发机的
窗口位置、`.bak-*` 一起发出去。

## 重复启动会起多个进程

0.6.0-beta.1 发出去后，双击快捷方式几次就会看到任务管理器里挂着好几个 `ShortcutHUD.exe`：
每一份都会装自己的键盘钩子、试着注册全局热键（后起的注册失败但仍在跑）、各自弹浮窗，
行为完全无法预期。

修法是 `scripts/single_instance.py` 里的 `SingleInstanceGuard`：创建命名内核互斥体
`Local\ShortcutHUD.SingleInstance`，`CreateMutexW` 之后如果 `GetLastError()` 是
`ERROR_ALREADY_EXISTS(183)`，就说明已经有实例占着，直接退出。`main()` 在构造
`QApplication` 之前就判断，所以第二个进程不会碰键盘钩子和热键。

选择命名互斥体而不是「找窗口/找进程」的理由：

- 互斥体是内核对象，进程崩溃时由系统自动释放，不会像 lock 文件那样留下死锁；
- 不需要枚举进程（沙箱里枚举进程本身就可能被限制）；
- `Local\` 前缀表示「当前登录会话」，同一台机器多个用户各自开一个实例是合理的。

代价：暂时只做到「第二个实例安静退出」，还没有把已有窗口唤到前台（托盘程序本来也没有主窗口）。

## 按住显示延迟

浮窗原来固定 150ms 出现（仅 Win 时 300ms），两个值都是
`scripts/shortcut_hud_controller.py` 里的类常量，用户改不了。现在做成设置项：

- 新增 `scripts/hud_show_delay.py`：设置键 `show_delay_ms`、默认 150、范围 0–5000 毫秒。
  `normalize_show_delay_ms()` 对 bool / 非数字 / NaN / inf 一律回退默认值——坏配置不能抛异常
  把 Qt 槽炸掉；`resolve_show_delay_ms(..., win_only=True)` 负责 Win 的单独下限。
- Win 仍保留 ≥300ms 下限的原因：`scripts/win_discovery_proxy.py` 只在「Win 按住超过发现阈值」
  之后才 arm，arm 之前所有按键都透传；把 Win 延迟调到 0 会让它过早拦截系统原生 Win 组合键。
  其余修饰键完全按用户设定生效，设成 0 就是按下即显示。
- 控制器每次启动计时器时**实时读配置**：`_configured_show_delay_ms()` 先
  `get_setting(SHOW_DELAY_SETTING, None)`，配置缺失（测试里的 fake config）时回退构造参数，
  其余交给 `resolve_show_delay_ms()` 决定 interval。所以设置改完立刻生效，不用重启。
- 设置对话框在「不透明度」下面新增「按住显示」组：`QDoubleSpinBox` 0.00–5.00 秒、步进 0.05、
  `suffix " s"`。`setKeyboardTracking(False)` 是关键——否则输入 1.5 时会在敲到 `1` 时先应用一次
  1.0 秒。提示文案用 `%1` 占位而不是 f-string，否则 `lupdate` 提取不到可翻译串。
- 只影响「按住修饰键自动出现」的浮窗；托盘菜单和 `Ctrl+Alt+Shift+H` 总览是显式命令，不走延迟。
- 值落在 `config/settings.json` 的 `show_delay_ms`（毫秒），可以直接手改。

i18n 手工往 `i18n/shortcut_overlay_zh_CN.ts` 补了 3 条中文。重编 `.qm` 踩了个坑：
`.venv\Scripts\pyside6-lrelease.exe` 静默 `exit 1`（不打印任何原因），改用
`.venv\Lib\site-packages\PySide6\lrelease.exe` 才成功（`Generated 254 translation(s)`）。

## 测试

- 新增/调整：解析层（SHELL_DESKTOP 有自己一层、WPS_UNKNOWN 回退 DEFAULT）、
  `show_all` 不截断、分节视图、两个热键实例的 identifier、`dialog_theme` 的样式契约、
  单实例互斥体（第二个实例被拒 / 释放后可重新占用 / 非 Windows 放行）、
  版本元数据非 OSError 异常被吞掉。
- 「禁止收录系统截图键」的检查改为只约束 `GLOBAL` / `DEFAULT` 层：系统截图键在每个应用里
  都一样，写死在每个应用组里会随用户改键而误导。
- 全量 `python -m unittest` 534 条通过；`tests/test_full_guide_interactions.py`
  里那条布局测试依赖窗口/屏幕状态，偶发失败。
- 按住显示延迟：新增 `tests/test_hud_show_delay.py`（归一化 / Win 下限 / 配置读写 / 对话框回读），
  控制器加 4 条（配置 250 → 计时器 250、非法值 → 150、缺配置 → 构造参数、Win + 配置 0 → 300）。
  本次全量 560 条，仅上面那条布局测试失败——已用 `git stash` 在干净基线上复跑，
  同样失败，确认与本次改动无关。

## 遗留

- 无修饰键组合（F2 / Delete 等）不在 HUD 契约内，PixPin 那 8 条暂时看不到。
- 其它六个内置包应用仍按默认行数截断，是否也提到全量待定。
- PixPin 其它页签（截图 / 长截图 / 贴图窗口 …）需要点鼠标切换，尚未收录。
- 第二个实例目前只是安静退出，不会把已有实例唤到前台。
- 按住显示延迟改动时如果修饰键正按着，新值要等下一次按住才生效（当前计时器不重启，
  避免改个数字把正在显示的浮窗打乱）。
- 0.6.0-beta.1 已发布（含本批数据与界面改动），上游 `Fx1an5heng` 的下载链接已改指本仓库；
  单实例修复已重传同 tag 的 zip。
