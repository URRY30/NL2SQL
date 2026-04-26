# 人才系统 AI 问数智能体

`NL2SQL-Data-Agent-v2` 是面向 `rencai1` 人才管理系统 AI 问答模块的 NL2SQL 数据智能体。它不是通用数据平台，也不是裸 SQL 生成器，而是给人才系统提供“受控查数据库”的能力：根据用户问题生成 SQL、校验 SQL、执行人才库查询，并把结果交给人才系统的大模型组织最终回答。

原始 NL2SQL Data Agent 平台方案仍作为底层设计参考，但当前版本的产品形态明确收敛为：

```text
人才系统 AI 问答 -> NL2SQL Data Agent -> PostgreSQL 人才库 -> 查询结果 -> 大模型回答
```

## 当前范围

- 默认连接 PostgreSQL。
- 当前只发布一个业务专题：`talent`。这是刻意收敛，不是缺陷，因为当前目标就是人才系统 AI 模块。
- 白名单视图已扩展为 8 个只读问数视图：
  - `vw_talent_ai_query`
  - `vw_talent_review_ai_query`
  - `vw_talent_education_ai_query`
  - `vw_talent_career_ai_query`
  - `vw_talent_project_ai_query`
  - `vw_talent_tag_ai_query`
  - `vw_succession_ai_query`
  - `vw_org_position_ai_query`
- 支持扫描视图字段、类型、样例枚举值和行数。
- 支持构造人才领域上下文。
- 支持问题规划：统计、分布、排名、占比、趋势、明细、教育、经历、项目、标签、继任、组织岗位和敏感拒答。
- 支持大模型 SQL 生成，当前可选 `dashscope`、`ollama` 或 `bigmodel`，并带 P0 规则兜底。
- 支持 SQL Guard：只读、白名单视图、危险关键字、`SELECT *`、`LIMIT`。
- 支持一跳式接口：`POST /api/service/query`。
- `/ui/` 是管理员调试台，不是最终业务用户界面。最终用户应在 `rencai1` 的 AI 问答模块中使用。

## 启动

```powershell
cd C:\Users\xuexi\Desktop\nl2sql-data-agent\NL2SQL-Data-Agent-v2
copy .env.example .env
python -m pip install -r requirements.txt
python main.py
```

默认地址：

```text
http://127.0.0.1:8010
```

健康检查：

```text
GET http://127.0.0.1:8010/api/health
```

页面初始化/元数据检查：

```text
GET http://127.0.0.1:8010/api/bootstrap
```

## 使用阿里 DashScope

默认 `.env` 已配置为：

```text
LLM_PROVIDER=dashscope
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen3.6-plus
DASHSCOPE_API_KEY=replace-with-your-dashscope-key
```

把 `DASHSCOPE_API_KEY` 换成阿里云百炼 API Key 后重启服务。也可以不写进 `.env`，直接在服务器环境变量里配置。

启动 NL2SQL 服务后，访问：

```text
http://127.0.0.1:8010/api/health
```

如果返回里看到：

```json
{
  "llm_provider": "dashscope",
  "llm_model": "qwen3.6-plus",
  "llm_configured": true
}
```

说明 NL2SQL Data Agent 已经会优先调用阿里模型生成 SQL。若远程模型调用失败，系统会自动使用 P0 规则兜底，保证调试链路不中断。

## 使用本地 Ollama

如果要切回本地 Ollama，把 `.env` 改成：

```text
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
```

并确认 Ollama 服务正在运行，本地有模型：

```powershell
ollama list
ollama run qwen3:8b
```

如果没有模型：

```powershell
ollama pull qwen3:8b
```

如果返回 `registered view not found`，说明目标库还没有白名单视图。先执行：

```text
python scripts/apply_sql_file.py sql/init_talent_ai_query_views_v2.sql
```

`init_talent_ai_query_views_v2.sql` 会适配当前人才库：已有业务表生成真实视图，当前库还没有的继任/岗位表会先生成空白占位视图，保证 NL2SQL 语义面完整。

## 一跳式问数

```http
POST /api/service/query
Content-Type: application/json
```

```json
{
  "client_id": "talent_aiqa",
  "topic_id": "talent",
  "question": "各部门核心人才数量是多少？",
  "return_mode": "sql_result_trace"
}
```

返回包括：

- `sql`
- `result`
- `risk.guard_status`
- `trace`
- `knowledge_hits`
- `candidates`

## 覆盖评测

第二阶段增加了覆盖测试集和评测脚本：

```powershell
python scripts/build_coverage_testset.py
python scripts/evaluate_coverage.py --fail-under 90
python scripts/build_grounded_talent_qa_testset.py
python scripts/evaluate_grounded_talent_qa.py --fail-under 95
python -m pytest tests -q
```

当前覆盖集在：

```text
data/testsets/talent_coverage_v1.csv
data/testsets/talent_grounded_qa_1000.csv
```

`talent_coverage_v1.csv` 覆盖总量统计、条件统计、分布排名、占比、明细、教育经历、任职经历、项目经历、标签、评审趋势、继任计划、组织岗位和敏感拒答。

`talent_grounded_qa_1000.csv` 会基于当前 PostgreSQL 真实人才数据生成 1000 条个人字段问答测试，例如“李泽阳的AI等级为多少？”。评测脚本会执行生成 SQL，并检查返回结果是否包含预期答案。

每条失败后不要优先改 Prompt，先归因：

- 找错表：补 `table_profiles` / 白名单视图。
- 找错字段：补 `column_aliases`。
- 枚举错：补 `enum_mappings`。
- 口径错：补 `metrics` / `business_rules`。
- SQL 风格错：补 `sql_cases`。
- 安全风险：加强 `SqlGuard`。

## 接入人才系统

下一阶段重点是接入人才管理系统的 AI 问答模块：

1. 在 `rencai1/backend/app/services/aiqa_service.py` 中调用 `POST /api/service/query`。
2. 传入当前登录用户、组织、数据权限和用户问题。
3. NL2SQL Data Agent 返回 SQL、结果和 Trace。
4. 人才系统后端把查询结果交给最终回答大模型。
5. 保存 AI 问答消息、SQL Trace、执行状态和错误信息。

接入后，普通用户不需要看到 SQL、Guard 和 Trace；这些内容只给管理员调试和审计使用。
