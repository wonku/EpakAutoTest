# Jenkins：CRM API 回归

## 1. GitHub 连不上时的报错

若 Console 出现：

```text
fatal: unable to access 'https://github.com/wonku/EpakAutoTest.git/': Recv failure: Connection was reset
```

说明失败发生在 **Jenkins 从 GitHub 拉代码** 阶段，流水线还没开始跑 pytest。  
`Jenkinsfile.crm-api` 里的任何 `retry()` **都无法覆盖这一步**。

## 2. 推荐方案：本机目录 + Pipeline script（无需每次 fetch GitHub）

适用：Jenkins 与本机代码在同一台电脑，代码已在 `E:\cursor\Pyautotest`。

1. 打开 Job **Pyautotest-CRM-API** → **Configure**
2. **Pipeline** → Definition 改为 **Pipeline script**（不要用 Pipeline script from SCM）
3. 打开仓库文件 **`Jenkinsfile.crm-api.stable`**，**全文复制**粘贴到 Script 框
4. 确认 `REPO_DIR = 'E:\\cursor\\Pyautotest'` 路径正确
5. 保存后 **Build with Parameters**，保持 **`SKIP_GIT_SYNC=true`**（默认已勾选）
6. **Build Now**

这样构建时 **不访问 GitHub**，直接使用本机已有代码执行 CRM API 回归。

以后网络恢复、想在构建前自动 `git pull` 时，取消勾选 `SKIP_GIT_SYNC` 即可（会调用 `scripts/jenkins_git_update_retry.bat`，默认 5 次重试、间隔 90 秒）。

## 3. 继续用 SCM 时的备选

若必须保留 **Pipeline script from SCM**：

| 配置项 | 建议 |
|--------|------|
| Shallow clone | 勾选，depth = 1 |
| Timeout | 60 分钟 |
| 仓库 URL | 可换镜像，如 `https://gitclone.com/github.com/wonku/EpakAutoTest.git` |
| Post-build | 安装 Naginator Plugin，失败后自动重试 3 次、间隔 120 秒 |

## 4. Credentials

| 变量 | 说明 |
|------|------|
| `LOGIN_PHONE` | CRM 登录手机号 |
| `LOGIN_PASSWORD_ENCRYPTED` | 加密后的登录密码 |
| `EMAIL_*` | 可选，邮件报告 |

## 5. 回归范围（`-m api`）

当前会一并执行：

| 模块 | 用例文件 | 说明 |
|------|----------|------|
| 销售线索 | `test_api_create_lead*.py` / claim / assign / 公海等 | 原有线索链路 |
| **客户** | **`tests/test_api_customer_flow.py`** | 列表 / 详情 / 查重 / 活动分页 |
| **销售机会** | **`tests/test_api_opportunity_flow.py`** | 列表 / 详情 / 活动 / 联系人 |
| **联系人** | **`tests/test_api_contact_flow.py`** | 列表 / 详情 / 活动 |
| 异常场景 | `test_api_negative.py` | 可由 `INCLUDE_NEGATIVE=false` 排除 |
| 其他 | 带 `@pytest.mark.api` 的用例（如订单造数） | 一并纳入 |

`Jenkinsfile.crm-api.stable` 使用本机 `REPO_DIR`，**无需 push GitHub**：保存本机代码后直接 Build 即可吃到客户用例。  
若 Job 仍粘贴的是旧版 Script，请重新复制 `Jenkinsfile.crm-api.stable`（超时已调到 20 分钟）。

## 6. 本地手动执行（与 Jenkins 一致）

```powershell
cd E:\cursor\Pyautotest
$env:SEND_EMAIL_REPORT = "true"
$env:INCLUDE_NEGATIVE = "true"
.\scripts\run_crm_api_jenkins.bat
```

只验证客户 4 条：

```powershell
pytest tests/test_api_customer_flow.py -m api -v
```

## 7. 相关文件

| 文件 | 作用 |
|------|------|
| `Jenkinsfile.crm-api.stable` | 不依赖 SCM 的稳定流水线 |
| `Jenkinsfile.crm-api` | 原 SCM 模式流水线 |
| `scripts/run_crm_api_jenkins.bat` | Jenkins / 本地执行 CRM API pytest |
| `scripts/jenkins_git_update_retry.bat` | git fetch/pull 带重试 |
| `tests/test_api_customer_flow.py` | 客户主路径 API |
| `api/services/crm_customer_service.py` | 客户 API 封装 |
| `tests/test_api_opportunity_flow.py` | 销售机会主路径 API |
| `api/services/crm_opportunity_service.py` | 销售机会 API 封装 |
