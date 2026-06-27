# Jenkins：易食包商城 UI 巡检（每 30 分钟）

适合团队协作：统一在 Jenkins 查看构建历史、控制台日志、JUnit 结果与截图归档。

## 1. 是否需要 Git？

**需要。** Jenkins 通常从 Git 拉代码再执行流水线，便于：

- 版本管理与回滚
- 多人协作改用例/配置
- 每个构建对应明确 commit

流程：**本地提交 → push 到 Git 仓库 → Jenkins Job 配置仓库地址 → 按 `Jenkinsfile.esbao-ui` 构建。**

`.env` 含密码，**不要提交**；邮件账号在 Jenkins 里用环境变量或 Credentials 注入。

## 2. Jenkins 节点要求（Windows Agent 推荐）

与现有 `Jenkinsfile`（Monkey）一致，使用 **Windows** 节点时最省事：

| 项 | 要求 |
|----|------|
| Python | 3.10+，且 `python` 在 PATH |
| 网络 | 能访问 `auth.esbao.com`、`www.esbao.com`、SMTP、PyPI |
| 浏览器 | 流水线会执行 `playwright install chromium`（可参数关闭） |
| 磁盘 | 保留 `reports/**` 归档，建议定期清理旧构建 |

Linux 节点也可用，需把流水线里的 `bat` 改为 `sh`，并安装 Playwright 系统依赖（`playwright install-deps chromium`）。

## 3. 创建 Jenkins Job

1. **New Item** → **Pipeline**（名称示例：`Pyautotest-Esbao-UI`）
2. **Pipeline** → Definition: **Pipeline script from SCM**
3. **SCM**: Git，填写仓库 URL 与凭据
4. **Script Path**: `Jenkinsfile.esbao-ui`（不是根目录的 `Jenkinsfile`）
5. **Build Triggers**: 勾选 **Build periodically** 时与流水线内 `cron` 二选一即可；本仓库已在 `Jenkinsfile.esbao-ui` 中配置：

   ```groovy
   cron('H/30 * * * *')   // 每 30 分钟
   ```

6. 保存后 **Build Now** 试跑一次

> 根目录 `Jenkinsfile` 仍是 **Android Monkey** 任务；易食包 UI 请用 **`Jenkinsfile.esbao-ui`** 单独建 Job，避免混在一个流水线里。

## 4. 邮件配置（复用现有 EMAIL_*）

在 Job → **Configure** → **Build Environment** → 勾选注入环境变量，或使用 **Credentials** + Pipeline `withCredentials`（推荐密码用 Secret text）。

必填（与本地 `.env` 一致）：

```text
EMAIL_SMTP_HOST=smtp.xxx.com
EMAIL_SMTP_PORT=465
EMAIL_SMTP_SSL=true
EMAIL_USERNAME=your@example.com
EMAIL_PASSWORD=***          # Jenkins Secret
EMAIL_FROM=your@example.com
EMAIL_TO=receiver@example.com
EMAIL_SUBJECT_PREFIX=[Pyautotest]
EMAIL_ATTACH_LOGS=true
```

定时构建要发邮件时，保持参数 **SEND_EMAIL_REPORT=true**（默认已开启），或设置：

```text
EMAIL_REPORT_ENABLED=true
```

## 5. 构建产物与团队查看方式

每次构建会：

- 控制台：pytest 步骤日志
- **JUnit**：`reports/junit/esbao-ui.xml`（Jenkins 测试报告页）
- **Artifacts**：`reports/ui/esbao/<时间戳>/`
  - `report.json`：步骤、首页/详情检查、点击的商品名
  - `*.png`：登录页、首页、热销区、详情页截图
- 邮件：主题含 `PASS` / `FAIL`，正文为巡检摘要，附件含截图与 `report.json`

团队成员无需登录测试机，在 Jenkins **Build History → 某次构建 → Test Result / Artifacts** 即可查看。

## 6. 手动触发与调试

- Jenkins：**Build with Parameters**，可关闭 `INSTALL_PLAYWRIGHT_BROWSER` 加快重复构建
- 节点上命令行（与流水线一致）：

  ```bat
  cd %WORKSPACE%
  set SEND_EMAIL_REPORT=true
  scripts\run_esbao_ui_jenkins.bat
  ```

## 7. 常见问题

| 现象 | 处理 |
|------|------|
| `playwright` 找不到浏览器 | 勾选 `INSTALL_PLAYWRIGHT_BROWSER` 或节点执行 `playwright install chromium` |
| 邮件未发送 | 检查 Jenkins 环境变量 / Secret，`SEND_EMAIL_REPORT=true` |
| 构建互抢浏览器 | 已 `disableConcurrentBuilds()`，同一 Job 不会并行 |
| 只想改频率 | 修改 `Jenkinsfile.esbao-ui` 中 `cron('H/30 * * * *')`，例如每小时：`H * * * *` |

## 8. 与 Windows 计划任务的关系

- **Jenkins 服务器调度**：用本文件 + `Jenkinsfile.esbao-ui`（团队查看友好）
- **本机计划任务**：`scripts/register_esbao_ui_schedule.ps1`（仅当前电脑）

二者选一种为主即可，避免同一台机器重复每 30 分钟跑两次。
