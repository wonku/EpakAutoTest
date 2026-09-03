# PowerPoint 使用说明

> 本目录已生成可直接打开的演示文稿与配图，分享会前只需改封面占位符。

---

## 已生成文件

| 文件 | 说明 |
|------|------|
| [ai-testing-sharing-session.pptx](./ai-testing-sharing-session.pptx) | **18 页完整 PPT**（深色主题 + 架构图 + 演讲备注） |
| [images/ai-sharing/](./images/ai-sharing/) | 7 张架构图 PNG（1920 级渲染，深色背景） |

### 架构图清单

| 文件 | 对应 PPT 页 |
|------|-------------|
| `diagram-01-pipeline.png` | 第 5 页 — 总链路 |
| `diagram-02-toolstack.png` | 第 4 页 — 工具栈 |
| `diagram-03-api-layers.png` | 第 10 页 — API 分层 |
| `diagram-04-human-ai.png` | 第 8 页 — 人机分工 |
| `diagram-05-jenkins.png` | 第 12 页 — Jenkins |
| `diagram-06-case-reuse.png` | 第 16 页 — 用例复用 |
| `diagram-07-demo-flow.png` | 第 18 页 — Demo 闭环 |

---

## 打开与修改（3 步）

### 1. 打开 PPT

双击 `docs/ai-testing-sharing-session.pptx`，推荐用 **Microsoft PowerPoint** 或 **WPS**。

### 2. 改封面占位符（必做）

第 1 页替换：

- `[你的名字]`
- `[部门名称]`
- `2026 年 [月] 月` → 实际分享日期

### 3. 查看演讲备注

PowerPoint 菜单：**视图 → 备注**（或「演示者视图」），每页下方有口播提示。

---

## 重新生成 PPT / 配图

若修改了 Mermaid 图源或幻灯片文案，在项目根目录执行：

```powershell
cd E:\cursor\Pyautotest
python scripts\generate_ai_sharing_pptx.py
```

脚本会：

1. 从 `ai-testing-sharing-diagrams.md` 读取 7 段 Mermaid，导出 PNG 到 `docs/images/ai-sharing/`
2. 重新生成 `docs/ai-testing-sharing-session.pptx`
3. 若存在 `reports/ui/` 下截图，自动插入第 13 页右下角

> 依赖：`python-pptx`（脚本运行时会用到，未写入 requirements.txt，按需安装：`pip install python-pptx`）

---

## 版式说明

- **幻灯片比例**：16:9（13.333 × 7.5 英寸）
- **背景色**：`#1a1a2e` 深色
- **标题色**：`#4fc3f7` 青色
- **正文字色**：`#e8eaed` 浅灰
- **字体**：Microsoft YaHei（微软雅黑）
- **有架构图的页**：左侧文字 + 右侧插图（约 45% / 55%）

---

## 导入到其他模板（可选）

若部门有统一 PPT 模板：

1. 打开部门模板，新建 18 页空白内容页
2. 从 `ai-testing-sharing-session.pptx` **复制每页内容**（Ctrl+A 全选幻灯片 → 复制 → 粘贴到模板）
3. 或只复制 `docs/images/ai-sharing/` 里的 PNG，按 [ai-testing-sharing-ppt-slides.md](./ai-testing-sharing-ppt-slides.md) 页码手动插入

---

## 配套文档索引

| 文档 | 用途 |
|------|------|
| [ai-testing-sharing-session.md](./ai-testing-sharing-session.md) | 25 分钟完整演讲稿 + Demo 脚本 |
| [ai-testing-sharing-session-15min.md](./ai-testing-sharing-session-15min.md) | 15 分钟压缩口播稿 |
| [ai-testing-sharing-ppt-slides.md](./ai-testing-sharing-ppt-slides.md) | 18 页文字源码（改 PPT 时可对照） |
| [ai-testing-sharing-diagrams.md](./ai-testing-sharing-diagrams.md) | Mermaid 图源（改图后重新跑脚本） |

---

## 分享当天 checklist

- [ ] 封面姓名 / 部门 / 日期已改
- [ ] 笔记本接投影，「演示者视图」打开备注
- [ ] Demo 环境预跑：`pytest tests/test_api_negative.py::test_login_wrong_password -v`
- [ ] 备用：若 Demo 失败，第 13 页已有 UI 巡检截图可讲
- [ ] 15 分钟版口播稿打印或放手机：`ai-testing-sharing-session-15min.md`
