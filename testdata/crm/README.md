# CRM UI 测试样例文件

线索冒烟会读取本目录下的真实附件：

- 优先：`lead_attachment_sample.jpg`
- 回退：`testdata/order/contract_sample.jpg`（过小，不推荐）

可自行替换为业务侧真实样例（jpg/png/pdf，建议 > 1KB），文件名保持 `lead_attachment_sample.jpg` 或改测试里的 `_SAMPLE_JPG` 路径。
