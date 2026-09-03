# 分享会架构图（Mermaid · 可截图进 PPT）

> **截图方法**  
> 1. 用 VS Code / Cursor 装 Mermaid 预览插件，打开本文件预览后截图  
> 2. 或打开 [Mermaid Live Editor](https://mermaid.live)，粘贴对应代码块导出 PNG/SVG  
> 3. 建议导出宽度 1920px，插入 PPT 第 5、9、10、12 页

---

## 图 1：总链路图（★ 建议放第 5 页）

```mermaid
flowchart TB
    subgraph INPUT["输入层"]
        A1["产品需求 / PRD"]
        A2["飞书 Wiki"]
        A3["评审纪要"]
    end

    subgraph DESIGN["测试设计层"]
        B1["cases_*.py<br/>结构化用例数据"]
        B2["AI 辅助扩写边界场景"]
        B3["generate_*_test_artifacts.py"]
        B4["Excel 用例表"]
        B5["XMind 脑图"]
    end

    subgraph AUTO["自动化执行层"]
        C1["CRM API<br/>test_api_*.py"]
        C2["商城 UI 巡检<br/>esbao / epak"]
        C3["移动端<br/>Monkey / Appium"]
    end

    subgraph REPORT["报告层"]
        D1["Allure"]
        D2["JUnit XML"]
        D3["截图 + report.json"]
        D4["邮件通知"]
    end

    subgraph CI["持续集成层"]
        E1["Jenkins Pipeline"]
        E2["定时触发"]
        E3["构建归档"]
    end

    A1 & A2 & A3 --> B1
    B1 --> B2 --> B3
    B3 --> B4 & B5
    B4 --> C1 & C2 & C3
    C1 & C2 & C3 --> D1 & D2 & D3
    D1 & D2 & D3 --> D4
    C1 & C2 & C3 --> E1
    E1 --> E2 --> E3
    D4 --> E3

    style INPUT fill:#2d3561,stroke:#4fc3f7,color:#fff
    style DESIGN fill:#1e3a5f,stroke:#4fc3f7,color:#fff
    style AUTO fill:#1a4d2e,stroke:#66bb6a,color:#fff
    style REPORT fill:#4a3728,stroke:#ffb74d,color:#fff
    style CI fill:#3d2952,stroke:#ce93d8,color:#fff
```

**讲解话术（30 秒）：**  
从上往下：需求进来先结构化，AI 帮扩场景，脚本一键出 Excel 和脑图；能自动化的进 pytest；跑完出 Allure、截图、邮件；最后挂到 Jenkins 定时回归，变成团队资产。

---

## 图 2：工具栈三层图（建议放第 4 页）

```mermaid
flowchart LR
    subgraph L1["第一层 · IDE"]
        CUR["Cursor<br/>读仓库 · 改文件 · 跑终端"]
    end

    subgraph L2["第二层 · 上下文"]
        CTX["项目代码<br/>conftest / client / 报告格式"]
        RULE["规则与模板<br/>cases_*.py · generate 脚本"]
    end

    subgraph L3["第三层 · 扩展"]
        MCP["MCP 工具<br/>TestSprite 等"]
    end

    subgraph OUT["产出"]
        O1["用例资产"]
        O2["自动化代码"]
        O3["CI 流水线"]
    end

    CUR --> CTX --> RULE
    CUR --> MCP
    CTX --> O1 & O2
    RULE --> O1
    MCP --> O2
    O2 --> O3

    style L1 fill:#1565c0,stroke:#4fc3f7,color:#fff
    style L2 fill:#2e7d32,stroke:#66bb6a,color:#fff
    style L3 fill:#6a1b9a,stroke:#ce93d8,color:#fff
    style OUT fill:#37474f,stroke:#90a4ae,color:#fff
```

---

## 图 3：CRM API 自动化分层（建议放第 10 页）

```mermaid
flowchart TB
    T1["tests/test_api_create_lead.py"]
    T2["tests/test_api_claim_lead.py"]
    T3["tests/test_api_assign_lead.py"]
    T4["tests/test_api_move_lead_public_sea.py"]
    T5["tests/test_api_negative.py<br/>11 条异常场景"]
    T6["tests/test_api_create_lead_activity.py"]

    S1["api/services/crm_lead_service.py"]
    S2["api/services/auth_service.py"]

    CL["api/client.py<br/>HTTP 封装 · 超时 · JSON"]

    FX["conftest.py<br/>auth_login_data fixture<br/>token 自动注入"]

    AL["Allure<br/>attach request / response"]

    T1 & T2 & T3 & T4 & T5 & T6 --> S1 & S2
    S1 & S2 --> CL
    FX --> CL
    T1 & T2 & T3 & T4 & T5 & T6 --> AL

    style T5 fill:#c62828,stroke:#ef5350,color:#fff
    style FX fill:#f57f17,stroke:#ffca28,color:#000
    style AL fill:#1565c0,stroke:#4fc3f7,color:#fff
```

---

## 图 4：人机分工（建议放第 8 页）

```mermaid
flowchart LR
    subgraph AI["🤖 AI 负责"]
        A1["扩边界场景"]
        A2["统一格式"]
        A3["出初稿"]
        A4["样板代码"]
    end

    subgraph HUMAN["👤 人负责"]
        H1["业务规则审核"]
        H2["优先级判断"]
        H3["断言正确性"]
        H4["最终 sign-off"]
    end

    subgraph GATE["质量门禁"]
        G1["pytest 运行"]
        G2["Code Review"]
        G3["CI 回归"]
    end

    AI --> GATE
    HUMAN --> GATE
    GATE --> DONE["可交付资产"]

    style AI fill:#1e3a5f,stroke:#4fc3f7,color:#fff
    style HUMAN fill:#4a3728,stroke:#ffb74d,color:#fff
    style GATE fill:#1a4d2e,stroke:#66bb6a,color:#fff
    style DONE fill:#2e7d32,stroke:#81c784,color:#fff
```

---

## 图 5：Jenkins 回归流水线（建议放第 12 页）

```mermaid
flowchart TB
  subgraph TRIGGER["触发"]
    CRON["Cron 定时<br/>如每 30 分钟"]
    MANUAL["手动 Build"]
  end

  subgraph JENKINS["Jenkins Job"]
    GIT["Git 同步 / 本机目录<br/>SKIP_GIT_SYNC"]
    ENV["注入 Credentials<br/>LOGIN_PHONE · EMAIL_*"]
    RUN["run_crm_api_jenkins.bat<br/>或 Jenkinsfile.esbao-ui"]
  end

  subgraph TEST["执行"]
    PY["pytest -m api"]
    PW["Playwright UI 巡检"]
  end

  subgraph ARTIFACT["产出物"]
    JU["reports/junit/*.xml"]
    AL["reports/allure-results/"]
    UI["reports/ui/esbao/*.png"]
    EM["邮件报告"]
  end

  CRON & MANUAL --> GIT --> ENV --> RUN
  RUN --> PY & PW
  PY --> JU & AL & EM
  PW --> UI & JU & EM

  style TRIGGER fill:#37474f,stroke:#90a4ae,color:#fff
  style JENKINS fill:#1565c0,stroke:#4fc3f7,color:#fff
  style TEST fill:#2e7d32,stroke:#66bb6a,color:#fff
  style ARTIFACT fill:#4a3728,stroke:#ffb74d,color:#fff
```

---

## 图 6：用例生成复用模式（建议放第 16 页）

```mermaid
flowchart LR
    REQ1["CRM3.13 需求"] --> CASE1["cases_crm313.py"]
    REQ2["线索看板需求"] --> CASE2["cases_lead_dashboard.py"]
    REQ3["企微对接需求"] --> CASE3["cases 数据文件"]

    CASE1 & CASE2 & CASE3 --> GEN["generate_*_test_artifacts.py<br/>同一套生成逻辑"]

    GEN --> XLSX["*.xlsx"]
    GEN --> XMIND["*.xmind"]

    XLSX --> REVIEW["人工审核 sign-off"]
    REVIEW --> AUTO["择优转自动化"]

    style GEN fill:#6a1b9a,stroke:#ce93d8,color:#fff
    style REVIEW fill:#f57f17,stroke:#ffca28,color:#000
```

---

## 图 7：Demo 闭环（建议放 Demo 前或第 18 页）

```mermaid
sequenceDiagram
    participant U as 测试工程师
    participant C as Cursor AI
    participant P as pytest
    participant R as Allure / 报告

    U->>C: 给出现有用例 + prompt（补异常场景）
    C->>U: 返回 diff（单文件小步修改）
    U->>U: Review 断言与业务规则
    U->>P: pytest test_api_negative.py -v
    P->>R: 通过 / 失败 + attach JSON
    R->>U: 可见证据，可进 CI
```

---

## PPT 插图对照表

| PPT 页码 | 推荐插图 |
|----------|----------|
| 第 4 页 | 图 2 工具栈三层 |
| 第 5 页 | 图 1 总链路（主图） |
| 第 8 页 | 图 4 人机分工 |
| 第 10 页 | 图 3 API 分层 |
| 第 12 页 | 图 5 Jenkins 流水线 |
| 第 16 页 | 图 6 用例生成复用 |
| 第 18 页 | 图 7 Demo 闭环 |

---

## ASCII 备用图（无法渲染 Mermaid 时投影用）

### 总链路（纯文本版）

```
  需求/Wiki ──→ cases_*.py ──→ generate 脚本 ──→ Excel + XMind
                                                    │
                                                    ▼
                                           pytest 自动化
                                          (API / UI / 移动端)
                                                    │
                     ┌──────────────────────────────┼──────────────────────────────┐
                     ▼                              ▼                              ▼
                 Allure                        截图/JSON                        邮件
                     │                              │                              │
                     └──────────────────────────────┴──────────────────────────────┘
                                                    ▼
                                            Jenkins 定时回归
```
