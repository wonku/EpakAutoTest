# 飞书文档拉取

## URL → token

| URL 形态 | token 位置 | 下一步 |
|----------|------------|--------|
| `https://xxx.feishu.cn/wiki/{token}` | `wiki` 后一段 | `wiki_v2_space_getNode` → 再读实际文档 |
| `https://xxx.feishu.cn/docx/{token}` | `docx` 后一段 | `docx_v1_document_rawContent` |
| `https://xxx.larksuite.com/...` | 同上 | 同左 |

Query、锚点（`?`、`#`）忽略。token 一般为字母数字串。

## MCP 调用顺序

### Wiki

```
wiki_v2_space_getNode
  params.token = <wiki_token>
  # 可选 useUAT: true

→ 读取 node.obj_token / node.obj_type / node.title

若 obj_type == docx:
  docx_v1_document_rawContent
    path.document_id = <obj_token>
    useUAT: true（权限不足时）
```

### 直接 Docx

```
docx_v1_document_rawContent
  path.document_id = <docx_token>
```

## 电子表格（sheet）读取

当前官方 `preset.default` **不包含**电子表格读单元格工具。要让 Agent 读到「表单字段-2.2」这类 Wiki 电子表格，需要三层都打通：

### 1. 开放平台 API 权限（应用侧）

在 [飞书开放平台](https://open.feishu.cn/app) → 你的 MCP 应用 → **权限管理**，批量开通并发布：

- `sheets:spreadsheet:readonly`（读电子表格，推荐）
- `drive:drive:readonly` 或 `drive:export:readonly`（可选，用于导出为 xlsx）

开通后若为企业自建应用，需**创建版本并提交发布**，管理员审批通过后正式环境才生效。测试期可用「免审测试」链接。

### 2. 文档协作者权限（表格侧）

仅有 API scope 不够。打开表格 → **分享** → 添加 MCP 应用为协作者（至少「可阅读」）。

Wiki 节点：`https://tvd6quau8vr.feishu.cn/wiki/Orn9wUv93itKzMkiWcBcRygWnRh?sheet=zQuRgR`  
电子表格 token：`W469sXDObhCosWtUGx0ctb8VnXd`，sheetId：`zQuRgR`。

### 3. MCP 工具开关（Cursor 侧）

在 `~/.cursor/mcp.json` 的 `-t` 中追加（已建议配置）：

```text
sheets.v3.spreadsheetSheet.query,sheets.v3.spreadsheetSheet.get,sheets.v3.spreadsheet.get,drive.v1.exportTask.create,drive.v1.exportTask.get
```

然后：**重启 Cursor MCP / 重新 OAuth 授权**（`--oauth` + `user_access_token` 模式下，新增 scope 后必须重新登录授权）。

### 兜底

若短期无法开通，把表格导出为本地 xlsx，或把关键列粘贴到对话 / `specs/`，Agent 仍可按粘贴稿更新用例。
