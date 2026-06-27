# Pyautotest

基于 `Playwright + Pytest + Allure` 的 UI 自动化测试项目，用于测试：

- `https://test-auth.ysbpack.com/user/login`

## 1. 环境准备

- Python 3.10+
- Windows / macOS / Linux

## 2. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

## 3. 配置测试数据

1. 复制示例配置：

```bash
copy .env.example .env
```

2. 按需修改 `.env` 内容（默认已填入当前登录账号）：

```env
BASE_URL=https://test-auth.ysbpack.com
LOGIN_PATH=/user/login
LOGIN_PHONE=13550147740
LOGIN_PASSWORD=Esbao0930666
HEADLESS=false
SLOW_MO=150
```

## 4. 运行测试

```bash
pytest
```

仅跑登录成功用例：

```bash
pytest tests/test_login.py::test_login_success -v
```

通过接口拿 token 直接进入系统（绕过登录页和滑块）：

```bash
pytest tests/test_login_token.py -v
```

进入 CRM 2.0 后点击“销售线索”：

```bash
pytest tests/test_login_token.py::test_open_sales_lead_menu_in_crm -v
```

接口造数：创建销售线索 + 创建活动记录：

```bash
pytest tests/test_api_create_lead_activity.py -v
```
> 活动记录类型参数来自 `.env`：
> `ACTIVITY_TYPE_CODE`、`ACTIVITY_RECORD_TYPE_CODE`（改这两个值后直接执行即可）。
>
> 线索国家参数也可在 `.env` 配置：
> `LEAD_COUNTRY`、`LEAD_COUNTRY_CODE`（`LEAD_COUNTRY_CODE` 留空时会自动调用国家接口联动生成）。

连续跑十次登录并统计平均耗时（控制台末尾会打印汇总，并写入 `reports/benchmark-last.json`）：

```bash
pytest tests/test_login_benchmark.py -v
```

## 5. 移动端 Android Monkey 测试

### 环境准备

- 手机开启开发者选项和 USB 调试，并在授权弹窗中允许当前电脑调试
- 本机安装 Android SDK Platform Tools，确保命令行可执行 `adb`
- 将待测 APK 放到项目根目录，默认文件名为 `app-release.apk`

检查设备连接：

```bash
adb devices
```

### 运行 Monkey

推荐先跑一轮 5000 次事件的稳定性测试：

```bash
pytest tests/mobile/test_monkey.py -m monkey -s
```

Windows 也可以直接执行脚本：

```powershell
.\scripts\run_monkey.ps1
```

带邮件通知执行：

```powershell
.\scripts\run_monkey.ps1 -EmailReport
```

常用参数可在 `.env` 中配置：

```env
MOBILE_APK_PATH=e:\cursor\Pyautotest\app-release.apk
MOBILE_PACKAGE_NAME=
MOBILE_DEVICE_SERIAL=
MOBILE_INSTALL_APK=true
MOBILE_LOGIN_ENABLED=false
MOBILE_LOGIN_DATA_PATH=e:\cursor\Pyautotest\config\mobile_login.json
MONKEY_EVENT_COUNT=5000
MONKEY_THROTTLE_MS=200
MONKEY_SEED=
MONKEY_EXTRA_ARGS=--ignore-crashes --ignore-timeouts --monitor-native-crashes --pct-syskeys 0 --pct-appswitch 0 --pct-anyevent 0 --pct-motion 0 --pct-trackball 0 --pct-nav 0 --pct-majornav 0
MONKEY_FAIL_ON_CRASH=true
MONKEY_KEEP_WIFI_ENABLED=true
MONKEY_CHUNK_EVENT_COUNT=500
MONKEY_SCREENSHOT_ENABLED=true
MONKEY_WHITE_SCREEN_ENABLED=true
MONKEY_WHITE_SCREEN_BRIGHTNESS_THRESHOLD=245
MONKEY_WHITE_SCREEN_RATIO=0.90
MONKEY_ERROR_TEXT_KEYWORDS=Error,Failed,Exception,Network error,Something went wrong,加载失败,错误,异常,白屏
MONKEY_FAIL_ON_INSPECTION_ISSUE=true
```

测试是否执行完成可以看三处：

- 命令行出现 `1 passed`、`failed` 或 `skipped` 等 pytest 结束汇总。
- `reports/test-summary-last.json` 会记录本次开始时间、结束时间、耗时、通过/失败统计。
- `reports/mobile/monkey/` 每次会生成一个时间戳目录，包含 `monkey.log`、`logcat.txt`、`device-info.txt`。

### 邮件报告

邮件报告默认关闭，避免误发。需要在 `.env` 或 Jenkins 环境变量中配置：

```env
EMAIL_REPORT_ENABLED=true
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=465
EMAIL_SMTP_SSL=true
EMAIL_USERNAME=your_email@example.com
EMAIL_PASSWORD=your_smtp_auth_code
EMAIL_FROM=your_email@example.com
EMAIL_TO=receiver1@example.com,receiver2@example.com
EMAIL_SUBJECT_PREFIX=[Pyautotest]
EMAIL_ATTACH_LOGS=true
```

也可以不打开 `EMAIL_REPORT_ENABLED`，只在命令行临时加 `--email-report`：

```bash
pytest tests/mobile/test_monkey.py -m monkey -s --email-report
```

说明：

- `MOBILE_PACKAGE_NAME` 留空时会自动从 APK 的 `AndroidManifest.xml` 解析包名；如果解析失败，手动填写包名即可。
- 有多台设备连接时，需要填写 `MOBILE_DEVICE_SERIAL`，值来自 `adb devices`。
- 每次执行会生成 `monkey.log`、`logcat.txt`、`device-info.txt` 到 `reports/mobile/monkey/`，并作为 Allure 附件保存。
- 默认会安装 APK 后再跑 Monkey；如已安装且不想覆盖，可设置 `MOBILE_INSTALL_APK=false`。
- 默认 Monkey 使用保守事件配置，禁用系统键、应用切换和滑动类事件，避免误拉快捷设置关闭 WiFi。
- `MONKEY_KEEP_WIFI_ENABLED=true` 会在 Monkey 前后尝试确保 WiFi 开启；如果设备系统限制该命令，不会让测试失败。
- `MONKEY_CHUNK_EVENT_COUNT` 控制分段巡检频率；默认每 500 个随机事件截图并检查一次。
- 巡检会生成 `inspection-summary.json` 和 `screenshots/chunk-xxx.png`；发现白屏或错误文案时，用例会失败并把问题截图放进 Allure/邮件附件。
- `MONKEY_ERROR_TEXT_KEYWORDS` 可以按 APP 文案补充，例如 `Server Error`、`No data`、`请求失败` 等。

### Monkey 前置登录

如果希望进入 APP 后先登录，再跑 Monkey：

```powershell
copy config\mobile_login.example.json config\mobile_login.json
```

然后修改 `config/mobile_login.json` 中的账号、密码和控件定位信息，并在 `.env` 开启：

```env
MOBILE_LOGIN_ENABLED=true
MOBILE_LOGIN_DATA_PATH=e:\cursor\Pyautotest\config\mobile_login.json
```

登录配置支持两种定位方式：

- 使用控件信息：`text`、`text_contains`、`resource_id`、`resource_id_contains`、`description`、`description_contains`、`class_name`
- 使用坐标：直接在步骤里配置 `x`、`y`

示例：

```json
{
  "enabled": true,
  "username": "your_login_name",
  "password": "your_password",
  "steps": [
    {"action": "tap", "selector": {"text_contains": "账号"}},
    {"action": "input", "value": "${username}"},
    {"action": "tap", "selector": {"text_contains": "密码"}},
    {"action": "input", "value": "${password}"},
    {"action": "tap", "selector": {"text": "登录"}}
  ],
  "success_selector": {"text_contains": "首页"}
}
```

`config/mobile_login.json` 已加入 `.gitignore`，真实账号密码不会进入 Git。

### Appium 随机探索

相比 Monkey，Appium 随机探索只操作 APP 内可点击元素，更适合验证页面行为、白屏和错误页。

1. 启动 Appium Server（新开一个终端）：

```powershell
.\scripts\start_appium.ps1
```

2. 运行随机探索：

```powershell
.\scripts\run_appium_explore.ps1
```

或直接：

```powershell
pytest tests/mobile/test_appium_explore.py -m appium -s
```

常用配置：

```env
APPIUM_SERVER_URL=http://127.0.0.1:4723
APPIUM_APP_ACTIVITY=.MainActivity
APPIUM_EXPLORE_STEPS=100
APPIUM_EXPLORE_PAUSE_MS=500
MOBILE_LOGIN_ENABLED=true
APPIUM_BLOCK_TEXT_KEYWORDS=Logout,Log out,Delete,Remove,Pay,Payment,退出,注销,删除,支付
```

每次执行会生成：

- `reports/mobile/appium/<时间>/explore-summary.json`
- `reports/mobile/appium/<时间>/explore.log`
- `reports/mobile/appium/<时间>/screenshots/step-xxx.png`

发现白屏或错误文案时会保存截图，并让用例失败。

### 易食包生产环境商城 UI 巡检（定时 + 邮件）

巡检流程：

1. 打开 `https://auth.esbao.com/` 登录页
2. 点击顶部「易食包」Logo 进入 `https://www.esbao.com/`
3. 全页滚动检查首页关键模块与图片加载
4. 点击「热销爆款」下任意商品并校验详情页

手动执行：

```powershell
.\scripts\run_esbao_ui.ps1
```

带邮件报告执行（复用 `.env` 中已有 `EMAIL_*` 配置）：

```powershell
.\scripts\run_esbao_ui.ps1 -EmailReport
```

或在 `.env` 中开启：

```env
EMAIL_REPORT_ENABLED=true
```

注册 Windows 计划任务（默认每天 08:00 执行并发送邮件）：

```powershell
.\scripts\register_esbao_ui_schedule.ps1 -StartTime "08:00"
```

报告输出目录：

- `reports/ui/esbao/<时间戳>/report.json`
- `reports/ui/esbao/<时间戳>/*.png`（登录页、首页、热销区、详情页截图）
- `reports/scheduled/esbao-ui-*.log`（定时任务日志）

### Jenkins 定时触发（推荐团队协作）

易食包 UI 巡检请**单独建 Pipeline Job**，使用 **`Jenkinsfile.esbao-ui`**（每 30 分钟触发 + 邮件 + 归档截图）：

1. 代码 push 到 Git 仓库
2. Jenkins → New Pipeline Job → SCM 指向本仓库，**Script Path** 填 `Jenkinsfile.esbao-ui`
3. 在 Job 环境变量或 Credentials 中配置 `EMAIL_*`（勿把密码提交进 Git）
4. 首次构建保持 `INSTALL_PLAYWRIGHT_BROWSER=true`

详细步骤见：[docs/jenkins-esbao-ui-setup.md](docs/jenkins-esbao-ui-setup.md)

```groovy
// Jenkinsfile.esbao-ui
triggers {
    cron('H/30 * * * *')   // 每 30 分钟
}
```

Android Monkey 仍使用根目录 **`Jenkinsfile`**（默认每天凌晨触发），与易食包 UI **分开两个 Job**，互不影响。

Jenkins 执行易食包 UI 后会归档 `reports/ui/esbao/**`、`reports/junit/esbao-ui.xml`，团队可在构建页的 **Test Result** 与 **Artifacts** 查看。

## 6. 生成并查看 Allure 报告

```bash
allure serve reports/allure-results
```

> 如果本机未安装 Allure CLI，请先安装：
>
> - Scoop: `scoop install allure`
> - Chocolatey: `choco install allure-commandline`

## 7. 已内置能力

- 登录成功、错误密码、空密码校验三个用例
- 失败自动截图并附加到 Allure
- 滑块验证码自动处理（优先腾讯滑块 iframe，包含重试、刷新和模拟人工轨迹）
- 支持截图分析缺口位置并计算目标水平坐标，优先“一步到位”拖动
- 自动失败后切换人工接管（默认等待 120 秒，你可手动拖动后继续执行）
- 支持 token 直登后按菜单名称动态打开系统菜单
- 新增 API 自动化基础框架（`api/client.py`、`api/services/`、`api/data_factory.py`）
- 新增移动端 Monkey 稳定性测试入口，支持自动安装 APK、解析包名、收集日志
