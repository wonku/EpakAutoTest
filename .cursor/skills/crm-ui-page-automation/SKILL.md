---
name: crm-ui-page-automation
description: >-
  CRM UI（Playwright）页面对象与冒烟用例的编写/排障规范：先定位阻碍根因再改代码，
  复用 CrmOpportunityPage/CrmCustomerPage 已沉淀 API，禁止 body(5,5)/裸 Enter 提交，
  附件必须等上传完成，查重弹窗仅在保存后处理。
  在编写或修复线索/客户/机会/联系人/活动/询价等 CRM UI 用例、Page Object，
  或出现「未保存将失效」「线索重复」「附件未上传」「下拉点不到」时使用。
---

# CRM UI 页面自动化（沉淀与复用）

## 核心原则（必须先遵守）

1. **失败先定阻碍根因，禁止盲目重试**
   - 先看日志/截图：卡在哪一步？是弹窗挡住、误提交、上传未完成，还是选择器错？
   - 定点修通该阻碍，再跑全链路。不要靠「多加 wait / 多套兜底 / 再跑一遍」代替分析。
2. **先复用，再扩展**
   - 新页面/新字段优先继承或调用已有基类方法，不要再造一套交互。
   - 客户页已验证的能力（工商选企、级联、上传等待、询盘字段）线索等模块直接复用。
3. **方法沉淀**
   - 同类坑修通后，把稳定 API 收到基类；本 Skill / `reference.md` 补一条，避免下个页面重踩。

## 类继承与权威 API

| 层级 | 文件 | 职责 |
|------|------|------|
| 基类 | `pages/crm_opportunity_page.py` | 表单浮层规范、Select/Cascader/日期、禁止危险点击 |
| 客户 | `pages/crm_customer_page.py` | 工商选企、省市区、上传等待、询盘字段 |
| 线索等 | `pages/crm_lead_page.py` 等 | 模块特有流程；能复用的不要重写 |

**必须复用（禁止另写一套）：**

- 收起下拉/日期：`_dismiss_select_dropdown()`（**禁止** `body.click(5,5)`，会触发「未保存将失效」）
- 误出离开确认：`_stay_on_form_if_discard_prompt()`
- 点下拉项：`_click_dropdown_option_node()` / `_pick_dropdown_option()`
- 级联：`select_cascader_levels` / `select_business_type_cascade` / `select_industry_cascade`
- 日期 RangePicker：`set_ant_range_picker`（只读，禁止 `fill`）
- 上传：`_upload_form_item_file`（等 `file/file/upload` + 列表真实文件名）
- 工商选企：`pick_company_via_qichacha`（键盘输入触发远程搜索，点选项后再查）

详细踩坑与选择器见 [reference.md](reference.md)。

## 新建表单标准顺序（线索等）

```
1. 打开表单后：锁定页脚「确定」（防 Enter/误点提交）
2. 基础信息 → 公司（工商下拉点选）→ 经营类型/行业/地区
3. 询盘信息（关键词、备注等）必须先填完
4. 上传附件：等接口成功 + 列表出现真实文件名（如 contract_sample.jpg）后再继续
5. 保存前门禁：断言询盘/附件就绪；若误出查重 → 点「取消创建」回到表单
6. 解锁「确定」→ 点击保存
7. 仅此时处理查重：点「继续创建」（填表未完成时禁止点继续创建）
8. 列表筛选断言；删除回滚可作独立用例
```

**查重时机：** 只有点击保存后才会查重。填表阶段出现查重 = 误提交，应「取消创建」继续填，不要「继续创建」。

## 排障工作流（失败时照此执行）

```
Task Progress:
- [ ] 1. 收集证据：pytest -s 日志关键行 + 截图/用户描述的弹窗与字段状态
- [ ] 2. 判定阻碍类型（见下表）
- [ ] 3. 定点修复（复用已有 API / 补基类方法）
- [ ] 4. 小范围验证该步骤已通
- [ ] 5. 再跑目标冒烟全链路
- [ ] 6. 若是新坑：写入基类 + 更新本 Skill reference
```

### 阻碍类型速查

| 现象 | 根因方向 | 处理 |
|------|----------|------|
| 「未保存将失效」 | body 空白点击 / Escape / 点到取消 | 只用 `_dismiss_select_dropdown` |
| 填到一半出「线索重复」 | Enter 或误点确定提交了 | 填表期锁确定；误出则「取消创建」 |
| 询盘/附件空但已查重 | 保存过早 | 调整顺序 + 保存前门禁 |
| 附件详情仍空 | 未等 upload/列表文件名 | 复用客户上传等待，断言文件名 |
| 公司下拉不出 | fill 不触发 onSearch | `press_sequentially`/键盘 + 点选项 |
| Select 点了没反应 | 被查重层 `repeat_wrapper` 挡住 | 先处理弹窗再操作 |
| 下拉用 Enter「兜底」 | 无下拉时 Enter = 提交表单 | 无可见下拉时禁止 Enter |

## 编写新 Page / 用例时

1. 先读同模块已有 Page 与客户/机会基类，列出可复用方法。
2. 交互问题优先改基类，子类只写业务编排。
3. 冒烟用例：`-s` 打步骤日志；关键断言（选中值、附件文件名、列表命中）。
4. 删除/回滚：独立用例；创建用例把上下文落到 `reports/` 或同进程变量。

## 反模式（禁止）

- 失败后不看证据，反复改 timeout / 重跑碰运气
- 每个页面复制一套 dismiss / upload / cascader
- `body.click(position=(5,5))`、对打开中的新建表单盲目 Escape
- 附件 `set_input_files` 后立刻点保存
- 填表未完成点查重「继续创建」
- Select 无选项时裸 `keyboard.press("Enter")`
