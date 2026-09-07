# Jenkins：EPAK 英文商城 UI 巡检（每 30 分钟）

Job 名称：**Pyautotest-Epak-UI**

## 0. GitHub 连不上时的报错

若 Console 出现：

```text
fatal: unable to access 'https://github.com/wonku/EpakAutoTest.git/': Recv failure: Connection was reset
```

说明失败发生在 **Jenkins 从 GitHub 拉代码** 阶段，流水线还没开始跑 pytest。  
`Jenkinsfile.epak-ui` 里的任何 `retry()` **都无法覆盖这一步**（Job 仍是 Pipeline script from SCM）。

### 推荐方案：本机目录 + Pipeline script（无需每次 fetch GitHub）

适用：Jenkins 与本机代码在同一台电脑，代码已在 `E:\cursor\Pyautotest`。

1. 打开 Job **Pyautotest-Epak-UI** → **Configure**
2. **Pipeline** → Definition 改为 **Pipeline script**（不要用 Pipeline script from SCM）
3. 打开仓库文件 **`Jenkinsfile.epak-ui.stable`**，**全文复制**粘贴到 Script 框
4. 确认 `REPO_DIR = 'E:\\cursor\\Pyautotest'` 路径正确
5. 保存后 **Build with Parameters**，保持 **`SKIP_GIT_SYNC=true`**（默认已勾选）
6. **Build Now**

这样构建时 **不访问 GitHub**，直接使用本机已有代码执行 EPAK UI 巡检。

以后网络恢复、想在构建前自动 `git pull` 时，取消勾选 `SKIP_GIT_SYNC` 即可（会调用 `scripts/jenkins_git_update_retry.bat`，默认 5 次重试、间隔 90 秒）。

### 继续用 SCM 时的备选

若必须保留 **Pipeline script from SCM**：

| 配置项 | 建议 |
|--------|------|
| Shallow clone | 勾选，depth = 1 |
| Timeout | 60 分钟 |
| 仓库 URL | 可换镜像，如 `https://gitclone.com/github.com/wonku/EpakAutoTest.git` |
| Post-build | 安装 Naginator Plugin，失败后自动重试 3 次、间隔 120 秒 |

## 1. 创建 / 对照 Job

1. **New Item** → **Pipeline**（名称：`Pyautotest-Epak-UI`）
2. GitHub 可访问时可用 **Pipeline script from SCM**，Script Path 填 `Jenkinsfile.epak-ui`
3. GitHub 不通时按第 0 节改用 **`Jenkinsfile.epak-ui.stable`**
4. **Build Triggers**：流水线内已配置 `cron('H/30 * * * *')`，与 Job 级定时二选一即可

根目录 `Jenkinsfile` 仍是 **Android Monkey**；易食包请用 `Jenkinsfile.esbao-ui`。三者分开建 Job。

## 2. Credentials

与易食包 UI Job 相同，配置 `EMAIL_*`：

| 变量 | 说明 |
|------|------|
| `EMAIL_SMTP_HOST` / `EMAIL_FROM` / `EMAIL_USERNAME` / `EMAIL_TO` / `EMAIL_PASSWORD` | 巡检邮件 |

## 3. 本地手动执行（与 Jenkins 一致）

```bat
cd E:\cursor\Pyautotest
set SEND_EMAIL_REPORT=true
scripts\run_epak_ui_jenkins.bat
```

## 4. 相关文件

| 文件 | 作用 |
|------|------|
| `Jenkinsfile.epak-ui.stable` | 不依赖 SCM 的稳定流水线（推荐） |
| `Jenkinsfile.epak-ui` | 原 SCM 模式流水线 |
| `scripts/run_epak_ui_jenkins.bat` | Jenkins / 本地执行 EPAK UI pytest |
| `scripts/jenkins_git_update_retry.bat` | git fetch/pull 带重试 |
| `tests/test_epak_mall_ui.py` | EPAK 商城 UI 巡检用例 |
