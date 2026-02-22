# 真实环境 Runbook

## macOS PlayCover 环境

### 1. 前置条件

- macOS 12.0+
- PlayCover 已安装
- 金铲铲之战 IPA 已签名并导入 PlayCover

### 2. 权限设置

```bash
# 系统偏好设置 → 隐私与安全性

# 辅助功能
# 添加: Terminal 或运行助手的应用

# 屏幕录制
# 添加: Terminal 或运行助手的应用
```

### 3. 验证窗口匹配

```bash
# 启动游戏
# 在 PlayCover 中启动金铲铲之战

# 等待游戏完全加载 (约 30 秒)

# 检查窗口匹配
./金铲铲助手 --platform mac --debug-window
```

期望输出：
```
Window found: 金铲铲之战
  Position: (0, 0)
  Size: 1920 x 1080
```

### 4. Dry-Run 测试

```bash
# 无实际操作，仅模拟运行
./金铲铲助手 --platform mac --dry-run --interval 3

# 观察日志输出，确认识别和决策正常
# Ctrl+C 退出
```

### 5. Live 运行

```bash
# 实际运行
./金铲铲助手 --platform mac

# 或带 UI
./金铲铲助手 --platform mac --ui tui
```

### 6. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 窗口未找到 | 游戏未启动或未加载完成 | 等待游戏完全加载 |
| 截图失败 | 缺少屏幕录制权限 | 系统偏好设置 → 隐私 → 屏幕录制 |
| 点击无效 | 缺少辅助功能权限 | 系统偏好设置 → 隐私 → 辅助功能 |

---

## Windows 模拟器环境

### 1. 前置条件

- Windows 10/11
- 模拟器 (雷电/夜神/MuMu/蓝叠)
- ADB (系统 PATH 或模拟器内置)

### 2. ADB 安装与验证

#### 方式 A: 使用模拟器内置 ADB

```powershell
# 雷电模拟器
$env:PATH += ";C:\leidian\LDPlayer9"

# 夜神模拟器
$env:PATH += ";C:\Nox\bin"

# MuMu 模拟器
$env:PATH += ";C:\Program Files\Netease\MuMuPlayer\shell"

# 验证
adb version
```

#### 方式 B: 安装 Android Platform Tools

```powershell
# 下载
# https://developer.android.com/studio/releases/platform-tools

# 解压到 C:\platform-tools
$env:PATH += ";C:\platform-tools"

# 验证
adb version
```

### 3. 连接模拟器

```powershell
# 列出设备
adb devices

# 如果没有设备，手动连接
# 雷电
adb connect 127.0.0.1:5555

# 夜神
adb connect 127.0.0.1:62001

# MuMu
adb connect 127.0.0.1:7555

# 蓝叠
adb connect 127.0.0.1:5555
```

### 4. 验证 ADB 连接

```powershell
adb devices -l

# 期望输出
List of devices attached
127.0.0.1:5555   device product:... model:... device:...
```

### 5. 验证截图

```powershell
# 测试截图
adb shell screencap -p /sdcard/test.png
adb pull /sdcard/test.png
```

### 6. Dry-Run 测试

```powershell
.\jinchanchan-assistant.exe --platform windows --dry-run --interval 3
```

### 7. Live 运行

```powershell
.\jinchanchan-assistant.exe --platform windows
```

### 8. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| adb 不是内部命令 | ADB 不在 PATH | 添加到 PATH 或使用完整路径 |
| device not found | 模拟器未启动或未连接 | 启动模拟器，adb connect |
| device offline | ADB 服务异常 | adb kill-server && adb start-server |
| unauthorized | 未授权调试 | 在模拟器中授权 USB 调试 |

### 9. 模拟器端口参考

| 模拟器 | 默认端口 | 多开端口 |
|--------|----------|----------|
| 雷电 | 5555 | 5555+n |
| 夜神 | 62001 | 62025, 62026... |
| MuMu | 7555 | 7555+n |
| 蓝叠 | 5555 | 5565, 5575... |
| 逍遥 | 21503 | 21513, 21523... |

---

## 快速排障清单

```bash
# macOS
./金铲铲助手 --doctor

# Windows
.\jinchanchan-assistant.exe --doctor
```

`--doctor` 会检查：
- 平台适配器可用性
- 窗口/设备连接状态
- 模板文件数量
- OCR 后端可用性
- 权限状态
