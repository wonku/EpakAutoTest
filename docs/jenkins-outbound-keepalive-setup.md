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
