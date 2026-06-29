# Jenkins：外呼手机号保活（每月 13、15、22 号）

用于维持 CRM 外呼系统绑定手机号的活跃状态：依次登录三个账号，对线索发起外呼，账号之间间隔 5 分钟。

## 1. 创建 Jenkins Job

1. **New Item** → **Pipeline**（名称示例：`Pyautotest-Outbound-Keepalive`）
2. **Pipeline** → Definition: **Pipeline script from SCM**
3. **SCM**: Git，填写仓库 URL 与凭据
4. **Script Path**: `Jenkinsfile.outbound-keepalive`
5. 保存后 **Build Now** 试跑一次

流水线内已配置定时触发：

```groovy
cron('H 9 13,15,22 * *')   // 每月 13、15、22 号约 9 点
```

## 2. Jenkins Credentials / 环境变量

| 变量 | 说明 |
|------|------|
| `OUTBOUND_KEEPALIVE_PASSWORD_ENCRYPTED` | 三个账号共用的登录密码（Secret text） |
| `EMAIL_*` | 可选，发邮件通知（与现有 CRM / UI Job 一致） |

默认保活账号（可在 `OUTBOUND_KEEPALIVE_CASES` 覆盖）：

- `17701563749`（默认 `relation_id=603`）
- `17768025264`（默认 `relation_id=603`）
- `17751104143`（默认 `relation_id=603`）

## 3. 本地手动执行

在 `.env` 中配置：

```env
OUTBOUND_KEEPALIVE_PASSWORD_ENCRYPTED=你的登录密码
# 可选：自定义账号与线索
# OUTBOUND_KEEPALIVE_CASES=[{"account":"17701563749","relation_id":603},{"account":"17768025264","relation_id":603},{"account":"17751104143","relation_id":603}]
# OUTBOUND_KEEPALIVE_ACCOUNT_INTERVAL_SECONDS=300
```

执行：

```powershell
.\scripts\run_outbound_keepalive.ps1
.\scripts\run_outbound_keepalive.ps1 -EmailReport
```

或直接：

```powershell
python scripts/outbound_call_keepalive.py
python scripts/outbound_call_keepalive.py --email-report
```

## 4. 执行逻辑

1. 使用 `AuthService.login_with_encrypted_password` 登录
2. 若未指定 `relation_id`，自动查询当前账号第一条销售线索
3. 调用 `POST /api/crm/yuyingcloud/callPhone`，body: `{"relationId": N, "operateTypeCode": 1}`
4. 第一个账号完成后等待 5 分钟，再处理第二个账号，依此类推
5. 报告写入 `reports/outbound-keepalive/<时间戳>/report.json`

## 5. 注意事项

- 登录接口 `password` 字段需使用与前端一致的加密/编码格式；若登录返回 1200，请核对密码配置
- 未配置 `relation_id` 的账号需有可外呼的销售线索，否则会失败
- 全流程约 15 分钟（含两次 5 分钟等待），Jenkins 超时已设为 45 分钟

## 6. GitHub 连不上 / 构建不稳定（重要）

你遇到的错误发生在 **Jenkins 拉取 GitHub 仓库阶段**（还没执行到外呼脚本）：

```text
fatal: unable to access 'https://github.com/...': Failed to connect to github.com port 443
```

`Jenkinsfile.outbound-keepalive` 里的 `retry()` **无法覆盖这一步**，因为 Jenkins 必须先成功 fetch 仓库才能读到 Jenkinsfile。

### 方案 A（推荐）：本机已有目录，无需再 clone

适用：**Jenkins 与本机代码在同一台电脑**，例如代码已在 `E:\cursor\Pyautotest`。

1. 修改 Job：**Definition → Pipeline script**（不再用 Pipeline script from SCM）

2. 将 **`Jenkinsfile.outbound-keepalive.stable`** 的内容粘贴到 Script 框

3. 确认 `REPO_DIR` 为你的路径（默认已是 `E:\cursor\Pyautotest`）

4. **Build with Parameters** 保持 **`SKIP_GIT_SYNC=true`**（默认已勾选）
   - 不访问 GitHub，直接用本机已有代码执行
   - 以后若网络好了、想构建前自动 `git pull`，取消勾选即可

**不需要** 在 Jenkins 节点再 `git clone` 一份。

前提：Jenkins 构建节点就是这台电脑（`agent any` 且只有本机一个节点）。若 Jenkins 跑在别的机器上，那台机器上必须有同样路径的代码。

### 方案 A2：单独 clone 目录（可选）

仅当 Jenkins 节点上没有开发目录、又需要从 Git 更新代码时，才需要：

```bat
git clone https://github.com/wonku/EpakAutoTest.git E:\jenkins\EpakAutoTest
```

并将 `REPO_DIR` 改为该路径，**取消勾选** `SKIP_GIT_SYNC`。

### 方案 B：继续用 Pipeline script from SCM

在 Job → **Configure → Pipeline → Git** 里增加：

| 配置项 | 建议值 |
|--------|--------|
| **Shallow clone** | 勾选，depth = 1 |
| **Timeout (minutes)** | 60 |
| 仓库 URL | 可换镜像，如 `https://gitclone.com/github.com/wonku/EpakAutoTest.git` |

并安装 **Naginator Plugin**，在 Job 的 **Post-build Actions** 里：

- Retry build after failure：**3** 次
- Delay：**120** 秒

这样 Git fetch 偶发失败时，整个 Job 会自动隔 2 分钟再试。

### 方案 C：节点代理 / 网络

- Jenkins 节点配置 HTTP/HTTPS 代理（**Manage Jenkins → System → HTTP Proxy**）
- 或保证构建节点能稳定访问 `github.com:443`

### 当前仓库已增加的重试

| 文件 | 作用 |
|------|------|
| `scripts/jenkins_git_update_retry.bat` | git fetch/pull 失败重试（环境变量 `GIT_UPDATE_MAX_ATTEMPTS`、`GIT_UPDATE_WAIT_SECONDS`） |
| `scripts/run_outbound_keepalive_jenkins.bat` | Jenkins 节点本地执行保活脚本 |
| `Jenkinsfile.outbound-keepalive.stable` | 不依赖 SCM 拉 Jenkinsfile 的稳定流水线 |
| `Jenkinsfile.outbound-keepalive` | SCM 模式下 pip/保活阶段 `retry()` + 整条流水线 `retry(2)` |
