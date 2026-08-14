# CRM UI 自动化参考（踩坑与复用明细）

配合 [SKILL.md](SKILL.md)。实现时以仓库代码为准；此处记录「为什么」和「已验证做法」。

## 权威代码位置

- 浮层/下拉/级联/日期：`pages/crm_opportunity_page.py`
- 工商选企、上传、询盘、省市区：`pages/crm_customer_page.py`
- 线索编排（锁确定、取消创建/继续创建、附件门禁）：`pages/crm_lead_page.py`
- 线索冒烟：`tests/test_crm_lead_smoke.py`

## 危险交互

### body(5,5) / 点遮罩

新建/编辑 Modal、Drawer 打开时，点页面空白或左上角常点到遮罩 → 「未保存信息将失效」。

**正确：** `_dismiss_select_dropdown()` — 点表单标题/区块标题或 blur，不点遮罩。

### 裸 Enter

`select_plain_first` / `_pick_dropdown_option` 在下拉未打开时按 Enter，等于提交表单 → 提前查重。

**正确：** 仅当可见 `.ant-select-dropdown` 存在时才键盘选；否则点 option 节点或失败报错。

## 查重弹窗（线索）

- 壳常见 class：`repeat_wrapper___xxxx`（会 `intercepts pointer events`）
- 按钮：`取消创建` / `继续创建`（文案可能带空格：`继 续 创 建`）
- **填表未完成：** `cancel_create_if_duplicate` → 取消创建
- **保存后：** `continue_create_if_duplicate` → 继续创建
- 填表期可用 `_block_create_form_submit(True)` 禁用页脚确定，门禁通过后再解锁

## 附件上传（客户已强调，全模块继承）

1. 使用**真实可读文件**（建议 `testdata/crm/lead_attachment_sample.jpg`，勿用过小占位图）
2. 定位「上传附件」`ant-form-item`，对隐藏 `input[type=file]` `set_input_files`（勿先点触发原生对话框）
3. 等待 `file/file/upload`（或等价）成功，并出现 **`.ant-upload-list-item-done` + 真实文件名**
4. 再缓冲 1–2s 后才允许点保存；详情里空「上传附件」占位 = 未 done/未写入表单
5. 实现：客户页 `_upload_form_item_file`；线索在此之上加 done 态与文件名断言

## 是否关键决策人

默认常为「否」。冒烟必须显式点选「是」（或业务要求值），不能 `select_plain_first` 停在默认。
API：`CrmLeadPage.select_key_decision_maker("是")`。

## 工商 / 公司名称

- 禁止只 `fill`：常不触发远程搜索
- `press_sequentially` / 键盘输入 → 等下拉 → 点目标全称（如「白象食品股份有限公司」）→ 再「工商信息查询」/回填
- API：`pick_company_via_qichacha(keyword, prefer_option=...)`

## 级联与枚举

- 经营类型/行业：级联 API，禁止只点第一级停在「请选择」
- 职务等：按文案点选，排除「未知」
- 跟进人：搜索后必须点选结果行

## 拜访日程

- 菜单「拜访日程」，URL `/memberCenter/crm2Ability/visitSchedule`，列表接口 `POST /api/crm/visit/schedule/page`
- 跟进对象现成客户：`CRM_UI_VISIT_CUSTOMER_KEYWORD` 默认「北京中镜眼镜有限责任公司」
- 筛选 id：`#scheduleName` `#customerIds` `#visitorId` `#scheduleStatus` `#time`
- 新建 id：`#scheduleName` `#customerId` `#visitorId` `#visitDateStr` `#followMethodCode` `#isAllDay` `#remark`
- 行操作随状态：待拜访=编辑/删除；已过期=关联活动记录；已完成=查看活动记录/解绑
- 日期只读，走 picker；禁止 body(5,5)/Escape
- 企微提醒默认当天 09:00，下午跑会 toast「提醒时间不能早于当前时间」
  → 点「更改时间」打开内层弹窗「更改提醒时间」，点时间框选比现在晚的时分，再点该弹窗「确定」（不要点外层保存）
- 账号未绑企微时，保存后会出「无法收到企微通知，确认是否创建？」→ 点「确认」继续创建（不要点取消）

## 线索认领 / 分配 / 公海

- **认领**：目标在「线索公海池」Tab（不是「线索公海」），必须先切范围再按**姓名**查。禁止用错误/残留手机号。
- **分配**：新跟进人必须与当前跟进人不同，否则 toast「分配前后跟进人一致，请修改」。默认关键字用 `tinker`，不要用登录账号「甜甜」。
- **移入公海**：原因是必填。必须用 `select_plain_first('#publicSeaReasonCode')` 点选并断言回填，再点确定。没选上会红框「请输入」，接口根本不会发出。禁止 Escape。
- **造数回滚**：接口 `CrmLeadService.rollback_created_lead` / `delete_lead`（GET `lead/delete?leadId=`，公海也可删）。用例注入 `lead_rollback` fixture，创建后 `register`，teardown 自动删。UI 回滚用 `CrmLeadPage.rollback_row_by_name`。历史脏数据：`rollback_leads_by_name_prefix("自动化认领")`。

## 日期

Ant RangePicker 只读 → `set_ant_range_picker`，禁止对 input `fill`。

## 排障证据怎么读

| 日志/报错片段 | 含义 |
|---------------|------|
| `repeat_wrapper` intercepts pointer events | 查重层挡住点击 |
| `附件列表无有效文件名` / `list=''` | 上传未完成或假成功 |
| `未找到…确定` 且可见按钮是列表「查询/新建」 | 新建表单已关（可能已误提交） |
| `未保存将失效` | 误点遮罩/取消保存 |
| `DBG_COMPANY: typed=…` 后无选项 | 远程搜索未触发或接口慢 |

## 沉淀清单（修通新坑时勾选）

- [ ] 稳定交互是否已落到 `CrmOpportunityPage` / `CrmCustomerPage`？
- [ ] 子类是否只保留编排、无复制粘贴的 dismiss/upload？
- [ ] 本 reference 是否补了现象 → 根因 → API？
- [ ] 冒烟是否有步骤日志与关键字段断言？
