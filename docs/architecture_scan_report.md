# VGuard 只读式前后端架构审计报告

> 审计范围：仅基于仓库内真实源码、配置、启动脚本与数据文件进行追踪，不依赖 README 或页面文案推断业务。

## 0. 审计结论摘要

- 前端没有接入 `vue-router`，页面切换是由 `frontend/src/stores/navigation.ts` 的本地状态驱动，属于“伪路由 / 状态路由”。
- 前端存在两套 HTTP 调用层：`frontend/src/services/api.ts` 的 `axios` 版本和 `frontend/src/api/*.ts` 的 `fetch` 版本，当前面板混用两套契约。
- 后端主服务入口是 `backend/app/main.py`，真实路由集中在 `backend/app/routers/*`，任务编排在 `backend/app/services/task_manager.py`。
- 注入链路是真实可执行的：`backend/app/services/injection_service.py` 会在 mock / real 之间分流，real 侧调用 `backend/app/scripts/injection_runner.py`。
- 版权归属验证链路是部分真实：`backend/app/services/verification_service.py` 自己实现了真实统计与落盘，`backend/app/scripts/verification_runner.py` 存在但未接入主链路。
- 统计证据链路是真实接口存在，但当前前端统计页默认仍展示 mock，因为 `frontend/src/components/panels/PanelStatistics.vue` 把 `lastTaskId` 固定为空。
- 模型注册表是真实落盘的 JSON：`data/model_registry.json`；当前仓库初始内容为空。
- 认证数据库是真实 SQLite：`data/auth.db`；登录账号由 `backend/app/services/auth_db.py` 预置 `root/root` 和 `gxy/gxy123456`。
- 部署层没有发现 `Dockerfile`、`docker-compose*` 或 `nginx.conf`，主要依赖 `start-local.sh`、`start-local.bat`、`deploy-remote.sh`、`start-remote.sh`。

## 1. 项目技术栈概览

| 层次 | 技术/框架 | 版本/配置 | 代码依据 |
|---|---|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Pinia + axios + ECharts | `frontend/package.json`, `frontend/vite.config.ts` | `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/src/services/api.ts` |
| 后端 | FastAPI + Uvicorn + SQLAlchemy + SciPy + NumPy + httpx | `backend/requirements.txt` | `backend/app/main.py`, `backend/app/services/*`, `backend/app/routers/*` |
| 数据库 | SQLite（认证）+ JSON 注册表 + 文件系统任务证据 | `backend/app/config.py`, `backend/app/core/config.py` | `backend/app/services/auth_db.py`, `backend/app/services/model_registry.py`, `backend/app/services/verification_service.py` |
| 深度学习 | `torch`, `transformers`, `vllm`, `openai` | 真实模式依赖 | `backend/app/services/verifier_service.py`, `backend/app/services/candidates_service.py`, `backend/app/scripts/injection_runner.py` |
| 部署 | 本地 Vite 代理 + FastAPI/静态 SPA 回源 + SSH tunnel | `frontend/vite.config.ts`, `backend/app/main.py`, `start-local.sh`, `deploy-remote.sh` | `start-local.bat`, `start-remote.sh` |

## 2. 目录职责划分

| 目录/文件 | 模块职责 | 关键类/函数 | 是否核心 |
|---|---|---|---|
| `frontend/src/views/*` | 登录页、 landing 页、仪表盘容器 | `LoginView.vue`, `LandingView.vue`, `DashboardView.vue` | 是 |
| `frontend/src/components/panels/*` | 各业务面板与图表展示 | `PanelInjection.vue`, `PanelVerification.vue`, `PanelModelManagement.vue`, `PanelReasoningEffect.vue`, `PanelStatistics.vue` | 是 |
| `frontend/src/services/api.ts` | 真实 API 封装主入口 | `fetchConfig`, `fetchHealth`, `startInjection`, `startVerification`, `generateCandidates` | 是 |
| `frontend/src/api/*` | 另一套 fetch 风格 API 封装 | `listModels`, `evaluateBehavior`, `getEvidence` | 是 |
| `frontend/src/stores/*` | 认证、导航、演示态管理 | `useAuthStore`, `useNavigationStore`, `useDemoStore` | 是 |
| `backend/app/main.py` | FastAPI 入口、CORS、SPA 回源、路由挂载 | `app.include_router(...)`, `SPAMiddleware` | 是 |
| `backend/app/routers/*` | HTTP/WS 路由层 | `auth.py`, `injection.py`, `verification.py`, `models.py`, `behavior.py`, `statistics.py`, `mock.py`, `ws.py` | 是 |
| `backend/app/services/*` | 业务服务、任务、注册表、认证、外部 LLM/RM 接入 | `task_manager.py`, `model_registry.py`, `injection_service.py`, `verification_service.py`, `candidates_service.py` | 是 |
| `backend/app/scripts/*` | 真实注入/验证脚本适配层 | `injection_runner.py`, `verification_runner.py` | 部分 |
| `data/*` | 运行时落盘数据 | `auth.db`, `model_registry.json` | 是 |

## 3. 前端架构

### 3.1 页面与状态流

- 入口是 `frontend/src/main.ts`，挂载 `App.vue` 并注入 Pinia。
- `frontend/src/App.vue` 不使用路由组件，而是根据 `useNavigationStore()` 的 `route` 在 `LoginView.vue` 和 `DashboardView.vue` 之间切换。
- `frontend/src/stores/navigation.ts` 只定义了 3 个状态：`landing`、`login`、`home`，因此它是“页面状态机”，不是 URL 路由。
- `frontend/src/stores/auth.ts` 负责本地 token 持久化、`/auth/me` 轮询式 bootstrap 和退出登录。
- `frontend/src/components/layout/DashboardHeader.vue` 与 `frontend/src/components/AppShell.vue` 会定时调用健康检查接口并控制前端 mock 开关。

### 3.2 前端真实 API 层

| 前端 API 函数 | 请求方法 | 请求地址 | 主要调用页面 |
|---|---|---|---|
| `fetchConfig` | `GET` | `/api/v1/config` | 仪表盘、模型/功能初始化 |
| `fetchHealth` | `GET` | `/api/v1/health` | `DashboardHeader.vue`, `PanelDashboard.vue` |
| `startInjection` | `POST` | `/api/v1/injection/start` | `PanelInjection.vue`, `useInjection.ts` |
| `getInjectionStatus` | `GET` | `/api/v1/injection/status/{taskId}` | `PanelInjection.vue`, `useInjection.ts` |
| `cancelInjection` | `POST` | `/api/v1/injection/cancel/{taskId}` | `useInjection.ts` |
| `startVerification` | `POST` | `/api/v1/verification/start` | `PanelVerification.vue`, `useVerification.ts` |
| `getVerificationStatus` | `GET` | `/api/v1/verification/status/{taskId}` | `PanelVerification.vue`, `useVerification.ts` |
| `getVerificationResult` | `GET` | `/api/v1/verification/result/{taskId}` | `PanelVerification.vue`, `useVerification.ts` |
| `generateCandidates` | `POST` | `/api/v1/candidates/generate` | `PanelModelTest.vue` |
| `fetchDistribution` | `GET` | `/api/v1/mock/distribution/{feature}` | mock 图表链路 |
| `fetchSensitivity` | `GET` | `/api/v1/mock/sensitivity/{feature}` | mock 图表链路 |
| `fetchHeatmap` | `GET` | `/api/v1/mock/heatmap/{feature}` | mock 图表链路 |
| `listModels` | `GET` | `/api/v1/models` | `useDemoStore.loadModels()` |
| `registerModel` | `POST` | `/api/v1/models/register` | `PanelModelManagement.vue` |
| `testLoadModel` | `POST` | `/api/v1/models/test-load` | `PanelModelManagement.vue`, `PanelModelTest.vue` |
| `deleteModel` | `DELETE` | `/api/v1/models/{model_id}` | `PanelModelManagement.vue` |
| `evaluateBehavior` | `POST` | `/api/v1/behavior/evaluate` | `PanelReasoningEffect.vue` |
| `getEvidence` | `GET` | `/api/v1/statistics/evidence?task_id=...` | `PanelStatistics.vue` |

### 3.3 前端组件与业务映射

| 页面 | 子组件 | 图表/表格 | 数据来源 | 状态 |
|---|---|---|---|---|
| `LoginView.vue` | `Input`, `Button` | 无 | `/auth/login`, `/auth/register` | 真实 |
| `LandingView.vue` | `Button` | 论文介绍、架构示意 | 本地静态内容 | 页面展示 |
| `DashboardView.vue` | `AppShell`, 各 `Panel*` | 以面板切换代替 URL 路由 | `useDemoStore.activeTab` | 真实容器 |
| `PanelDashboard.vue` | `DistributionHistogram` | 资产饼图、GPU 仪表、结果分布、质量散点 | `fetchHealth` + `useDemoStore` | 部分真实 |
| `PanelModelManagement.vue` | 表格、弹窗、图表 | 模型资产、类型分布、验证结果、质量散点 | `listModels` + `useDemoStore` | 真实/ mock 双分支 |
| `PanelInjection.vue` | `Progress`, `DistributionHistogram` | 训练曲线、指标对比、登记卡 | `/api/v1/injection/*` 或本地 timer | 真实/ mock 双分支 |
| `PanelReasoningEffect.vue` | `DistributionHistogram` | 散点图、Top-K 排名变化、候选输出对比 | `/api/v1/behavior/evaluate` | 真实/ mock 双分支 |
| `PanelVerification.vue` | `Progress`, `DistributionHistogram` | p-value、样本一致性、取证轨迹 | `/api/v1/verification/*` 或本地 timer | 真实/ mock 双分支 |
| `PanelStatistics.vue` | `DistributionHistogram` | 分布、N-p 曲线、热力图 | `getEvidence` / mock 模板 | 当前默认 mock |
| `PanelModelTest.vue` | `Button`, `Progress` | 模型加载、推理输出 | `testLoadModel`, `generateCandidates` | 真实/ mock 双分支 |
| `PanelAbout.vue` | `DistributionHistogram` | 论文图示复刻 | 本地静态数据 | 页面展示 |

### 3.4 前端真实状态判断

- `PanelModelManagement.vue`：真实能力存在，mock 分支直接改 `useDemoStore`，真实分支走 `/models/*`。
- `PanelInjection.vue`：真实能力存在，`store.mockMode` 为真时只做本地进度条；真实分支会创建任务并轮询状态。
- `PanelVerification.vue`：真实能力存在，mock 分支本地生成 p-value；真实分支走 `/verification/*`。
- `PanelReasoningEffect.vue`：真实能力存在，mock 分支显示伪造候选集；真实分支走 `/behavior/evaluate`。
- `PanelStatistics.vue`：接口真实存在，但当前实现里 `lastTaskId = ''`，因此默认永远回退 mock，属于“接口真实、页面默认 mock”。
- `useInjection.ts`、`useVerification.ts`、`useWebSocket.ts` 作为可复用组合式函数存在，但当前面板主要没有直接使用它们，属于备用/半接入层。

## 4. 后端架构

### 4.1 路由入口

| HTTP/WS 方法 | 路由 | Router/函数 | Service/脚本 | 返回内容 | 状态 |
|---|---|---|---|---|---|
| `POST` | `/api/v1/auth/login` | `backend/app/routers/auth.py:login` | `auth_db.verify_user`, `auth_db.create_session` | token、username、role | 真实 |
| `POST` | `/api/v1/auth/register` | `auth.py:register` | `auth_db.create_user` | `ok` | 真实 |
| `GET` | `/api/v1/auth/me` | `auth.py:me` | `auth_db.get_username_by_token` | username、role | 真实 |
| `POST` | `/api/v1/auth/logout` | `auth.py:logout` | `auth_db.delete_session` | `ok` | 真实 |
| `POST` | `/api/v1/injection/start` | `routers/injection.py:start_injection` | `task_manager.create_task` + `run_injection_task` | `taskId` | 真实 |
| `GET` | `/api/v1/injection/status/{task_id}` | `injection.py:get_injection_status` | `task_manager.get_status_dict` | 任务状态 | 真实 |
| `GET` | `/api/v1/injection/latest` | `injection.py:get_latest_task` | 只读任务列表 | 最新任务状态 | 真实 |
| `POST` | `/api/v1/injection/cancel/{task_id}` | `injection.py:cancel_injection` | `task_manager.cancel_task` | `ok` | 真实 |
| `POST` | `/api/v1/verification/start` | `routers/verification.py:start_verification` | `task_manager.create_task` + `run_verification_task` | `task_id` | 真实 |
| `GET` | `/api/v1/verification/status/{task_id}` | `verification.py:get_verification_status` | `task_manager.get_task` | 进度、logs、result | 真实 |
| `GET` | `/api/v1/verification/result/{task_id}` | `verification.py:get_verification_result` | `task_manager.get_task` | result、logs | 真实 |
| `POST` | `/api/v1/verification/cancel/{task_id}` | `verification.py:cancel_verification` | `task_manager.cancel_task` | `ok` | 真实 |
| `POST` | `/api/v1/candidates/generate` | `routers/candidates.py:generate_candidates` | mock 数据或 `candidates_service.run_candidates` | 候选集 | 真实 |
| `GET` | `/api/v1/models` | `routers/models.py:api_list_models` | `model_registry.list_models` | 四类模型列表 | 真实 |
| `POST` | `/api/v1/models/register` | `models.py:api_register_model` | `model_registry.register_model` | model record | 真实 |
| `POST` | `/api/v1/models/test-load` | `models.py:api_test_load` | `vllm_list_models` / `transformers` | 加载结果 | 真实 |
| `DELETE` | `/api/v1/models/{model_id}` | `models.py:api_delete_model` | `model_registry.delete_model` | 删除结果 | 真实 |
| `POST` | `/api/v1/behavior/evaluate` | `routers/behavior.py:evaluate_behavior` | `generate_candidates` + `get_verifier` | 评分、排名、统计摘要 | 真实 |
| `GET` | `/api/v1/statistics/evidence` | `routers/statistics.py:get_statistics_evidence` | `Path(VGUARD_TASK_DIR)` + `scipy.stats.wilcoxon` | 分布、收敛曲线、摘要 | 真实 |
| `GET` | `/api/v1/mock/distribution/{feature}` | `routers/mock.py:get_distribution` | `mock_data.DISTRIBUTION_DATA` | mock 分布 | mock |
| `GET` | `/api/v1/mock/sensitivity/{feature}` | `mock.py:get_sensitivity` | `mock_data.SENSITIVITY_DATA` | mock 灵敏度 | mock |
| `GET` | `/api/v1/mock/heatmap/{feature}` | `mock.py:get_heatmap` | `mock_data.HEATMAP_DATA` | mock 热力图 | mock |
| `WS` | `/ws/injection/{task_id}` | `routers/ws.py:ws_injection` | `task_manager.register_ws` | 进度推送 | 真实 |
| `WS` | `/ws/verification/{task_id}` | `ws.py:ws_verification` | `task_manager.register_ws` | 进度推送 | 真实 |
| `WS` | `/ws/candidates/{task_id}` | `ws.py:ws_candidates` | `task_manager.register_ws` | 进度推送 | 真实但前端未见消费 |
| `GET` | `/api/v1/config` | `backend/app/main.py:get_config` | `backend/app/core/config.py` | 模型、特征、默认值 | 真实 |
| `GET` | `/api/v1/health` | `backend/app/main.py:health_check` | `torch.cuda` 统计 | health、GPU 信息 | 真实 |

### 4.2 后端分层

- API 接入层：`backend/app/routers/*`
- 任务调度层：`backend/app/services/task_manager.py`
- 业务服务层：`backend/app/services/injection_service.py`、`verification_service.py`、`candidates_service.py`、`behavior.py`
- 模型注册层：`backend/app/services/model_registry.py`
- 认证存储层：`backend/app/services/auth_db.py`
- 外部推理接入层：`backend/app/services/llm_service.py`、`verifier_service.py`
- 真实训练脚本层：`backend/app/scripts/injection_runner.py`
- 真实验证脚本层：`backend/app/scripts/verification_runner.py`（存在但未接入主调用链）

### 4.3 关键后端实现细节

- `backend/app/services/task_manager.py` 的任务是内存态为主，启动时 `_load()` 会删除 `backend/task_store.json`，因此任务状态不会跨重启保留。
- `backend/app/services/verification_service.py` 会把完成后的验证结果写到 `VGUARD_TASK_DIR`，默认是 `backend/data/tasks/{task_id}.json`，随后 `backend/app/routers/statistics.py` 读取该文件生成证据图。
- `backend/app/services/injection_service.py` 在 mock 模式下用 `mock_data.INJECTION_CURVE` 模拟训练进度，并把水印模型注册写回 `model_registry.json`。
- `backend/app/services/injection_service.py` 的 real 分支会调用 `backend/app/scripts/injection_runner.py:run_injection`，并通过 `progress_callback` 把训练进度广播到 WebSocket。
- `backend/app/services/candidates_service.py` 的 real 分支会调用外部生成模型服务 `VGUARD_VLLM_BASE_URL`，再用 reward model 重新打分。
- `backend/app/services/behavior.py` 的 real 分支会先 `generate_candidates(...)`，再用 `get_verifier(...)` 做 batch 打分与重排统计。
- `backend/app/services/auth_db.py` 直接用 SQLAlchemy 建表并在模块加载时 `seed_user(...)`，因此账号种子是代码内置而不是独立初始化脚本。

## 5. 数据库与文件存储

### 5.1 SQL / JSON 实体

| 实体/数据表 | 主要字段 | 用途 | 读写模块 |
|---|---|---|---|
| `users` | `username`, `password_hash`, `salt`, `role` | 账号认证 | `backend/app/services/auth_db.py` |
| `sessions` | `token`, `username`, `created_at` | 登录态 session | `backend/app/services/auth_db.py` |
| `data/model_registry.json` 的 `base_verifiers` | `id`, `name`, `path`, `metadata` | 基础 Verifier 注册表 | `model_registry.py` |
| `data/model_registry.json` 的 `watermarked_verifiers` | `id`, `base_verifier`, `feature`, `method`, `trigger` | 水印 Verifier 注册表 | `model_registry.py`, `injection_service.py` |
| `data/model_registry.json` 的 `target_verifiers` | `id`, `path`, `metadata` | 待检测目标注册表 | `model_registry.py` |
| `data/model_registry.json` 的 `generators` | `id`, `path`, `backend` | 候选生成模型注册表 | `model_registry.py` |
| `backend/data/tasks/{task_id}.json` | `task_id`, `status`, `result`, `logs` | 验证证据落盘 | `verification_service.py`, `statistics.py` |

### 5.2 文件系统资源

| 文件类型 | 输入/输出 | 保存目录 | 生成模块 | 使用模块 |
|---|---|---|---|---|
| 认证数据库 | 读写 | `data/auth.db` 或 `backend/data/vguard_auth.sqlite3`（取决于环境变量） | `auth_db.py` | `routers/auth.py` |
| 模型注册表 | 读写 | `data/model_registry.json` | `model_registry.py` | `routers/models.py`, `injection_service.py`, `useDemoStore.loadModels()` |
| 任务状态快照 | 主要是内部状态 | `backend/task_store.json` | `task_manager.py` | `routers/injection.py`, `routers/verification.py` |
| 验证证据 | 输出 | `backend/data/tasks/{task_id}.json` | `verification_service.py` | `statistics.py`, `PanelStatistics.vue` |
| 训练/验证脚本 | 输入模型/数据集，输出结果与进度 | `backend/app/scripts/*` | `injection_runner.py`, `verification_runner.py` | `injection_service.py`, `verification_service.py` |
| 上传/临时模型路径 | 输入 | `VGUARD_DATA_DIR` 下的模型目录 | 配置驱动 | `models.py`, `candidates_service.py`, `verifier_service.py` |

## 6. 节点与通信拓扑

| 起始节点 | 目标节点 | 协议 | 端口/地址 | 传输内容 | 调用方向 | 代码依据 |
|---|---|---|---|---|---|---|
| 浏览器 | Vite dev server | HTTP | `5173` | 前端静态资源与 HMR | 请求 | `frontend/vite.config.ts` |
| 浏览器 | FastAPI | HTTP | `/api/v1/*` | JSON API | 请求 | `frontend/src/services/api.ts`, `frontend/src/api/*` |
| 浏览器 | FastAPI | WebSocket | `/ws/*` | 任务进度推送 | 双向 | `frontend/src/services/api.ts`, `backend/app/routers/ws.py` |
| FastAPI | 任务管理器 | 内存调用 | 进程内 | 任务状态、广播 | 单向 | `task_manager.py` |
| FastAPI | 模型注册表 | 文件读写 | `data/model_registry.json` | 模型元数据 | 单向 | `model_registry.py` |
| FastAPI | 认证 DB | SQLAlchemy | SQLite/MySQL | 用户、session | 单向 | `auth_db.py` |
| FastAPI | 外部生成服务 | HTTP | `VGUARD_VLLM_BASE_URL` | chat/completions、models | 单向 | `llm_service.py` |
| FastAPI | Verifier 模型 | 本地推理 | 本机 GPU/CPU | tokenizer、logits | 单向 | `verifier_service.py` |
| FastAPI | 训练脚本 | Python 函数调用 | 进程内线程池 | 训练进度、结果 | 单向 | `injection_service.py` |
| FastAPI | 结果落盘目录 | 文件系统 | `backend/data/tasks` | 取证 JSON | 单向 | `verification_service.py` |

### 6.1 节点分组建议

- 用户访问层：浏览器
- Web 接入层：Vite dev server、FastAPI、SPA 静态资源回源
- 平台服务层：FastAPI routers + services
- 算法计算层：`injection_runner.py`、`verifier_service.py`、`candidates_service.py`
- 数据与文件层：SQLite、`model_registry.json`、`backend/data/tasks`
- 外部服务层：vLLM / OpenAI-compatible LLM 服务

## 7. 功能模块清单

| 一级模块 | 二级功能 | 页面入口 | 后端接口 | 核心处理 | 输出结果 | 状态 |
|---|---|---|---|---|---|---|
| 认证 | 登录 | `LoginView.vue` | `/auth/login` | `auth_db.verify_user` | token、username | 真实 |
| 认证 | 注册 | `LoginView.vue` | `/auth/register` | `auth_db.create_user` | `ok` | 真实 |
| 认证 | 登出 | `AppShell.vue` | `/auth/logout` | `auth_db.delete_session` | `ok` | 真实 |
| 模型管理 | 列表/新增/删除/测试加载 | `PanelModelManagement.vue` | `/models`, `/models/register`, `/models/test-load`, `/models/{id}` | `model_registry` + `transformers`/`vllm` | 模型列表、加载结果 | 真实/ mock 双分支 |
| 水印注入 | 任务创建、进度、取消 | `PanelInjection.vue` | `/injection/start`, `/injection/status`, `/injection/cancel`, `/ws/injection/{task_id}` | `injection_service` + `injection_runner` | 训练曲线、登记卡 | 真实/ mock 双分支 |
| 行为核验 | 候选排序、Top-K 重排 | `PanelReasoningEffect.vue` | `/behavior/evaluate` | `generate_candidates` + `get_verifier` | 散点、排名、候选输出 | 真实/ mock 双分支 |
| 版权归属验证 | 样本采样、Wilcoxon 检验 | `PanelVerification.vue` | `/verification/start`, `/verification/status`, `/verification/result`, `/ws/verification/{task_id}` | `verification_service` | p-value、结论、轨迹 | 真实/ mock 双分支 |
| 统计证据 | 证据分布、收敛曲线 | `PanelStatistics.vue` | `/statistics/evidence?task_id=...` | 读取任务证据 JSON | 图表、摘要 | 接口真实，页面默认 mock |
| 候选生成测试 | 单问题生成 | `PanelModelTest.vue` | `/candidates/generate` | `candidates_service` 或 mock 数据 | 候选回答 | 真实/ mock 双分支 |
| 仪表盘 | 在线状态、GPU、资产分布 | `PanelDashboard.vue` | `/health` | `torch.cuda`、store 统计 | 仪表图、资产图 | 部分真实 |
| 关于页 | 论文/图示展示 | `PanelAbout.vue` | 无 | 本地静态数据 | 架构图、论文图 | 页面展示 |

## 8. 核心业务调用链

### 8.1 用户登录与权限

1. 用户在 `frontend/src/views/LoginView.vue` 输入用户名和密码。
2. 页面调用 `frontend/src/services/auth.ts:login(...)`。
3. 请求命中 `backend/app/routers/auth.py:login`。
4. `auth_db.verify_user(...)` 校验 `data/auth.db` 中的 `users` 表。
5. 成功后 `auth_db.create_session(...)` 写入 `sessions` 表并返回 token。
6. `frontend/src/stores/auth.ts` 将 token 存入 `localStorage`，`App.vue` 切换到 `home`。

### 8.2 模型上传 / 路径注册

1. 用户在 `frontend/src/components/panels/PanelModelManagement.vue` 打开“添加模型”。
2. mock 模式下直接写入 `useDemoStore`。
3. 真实模式下调用 `frontend/src/api/models.ts:registerModel(...)`。
4. 请求命中 `backend/app/routers/models.py:api_register_model`。
5. `backend/app/services/model_registry.py:register_model(...)` 将记录写入 `data/model_registry.json`。
6. 模型管理表格通过 `useDemoStore.loadModels()` 重新拉取列表。

### 8.3 水印注入任务创建

1. 用户在 `frontend/src/components/panels/PanelInjection.vue` 选择 Verifier、特征和触发器。
2. mock 模式下本地 `setInterval` 模拟训练进度。
3. 真实模式下调用 `frontend/src/services/api.ts:startInjection(...)`。
4. 请求命中 `backend/app/routers/injection.py:start_injection`。
5. `task_manager.create_task(TaskType.INJECTION, ...)` 创建任务。
6. `backend/app/services/injection_service.py:run_injection_task(...)` 根据 `useMock` 分流。
7. mock 分支使用 `mock_data.INJECTION_CURVE`，real 分支调用 `backend/app/scripts/injection_runner.py:run_injection(...)`。
8. 进度通过 `task_manager.broadcast(...)` 推送到 `/ws/injection/{task_id}`，前端可轮询或 WS 接收。
9. 结束后 `register_model(...)` 自动登记水印 Verifier，并写入 `data/model_registry.json`。

### 8.4 注入进度查询 / WebSocket / 轮询

1. 前端 `PanelInjection.vue` 先用 `startInjection(...)` 创建任务。
2. `useWebSocket('injection')` 或面板内轮询调用 `/injection/status/{taskId}`。
3. 后端 `task_manager.get_status_dict(...)` 返回当前 `progress`、`phase`、`metrics`。
4. 结束态会返回 `wm_id` 和 `result`，前端据此更新登记卡。

### 8.5 版权归属验证任务

1. 用户在 `frontend/src/components/panels/PanelVerification.vue` 选择待检测目标、已登记水印档案和候选生成模型。
2. mock 模式下本地构造 paired samples、p-value 和结论。
3. 真实模式下调用 `frontend/src/services/api.ts:startVerification(...)`。
4. 请求命中 `backend/app/routers/verification.py:start_verification`。
5. `backend/app/services/verification_service.py:run_verification_task(...)` 根据 `useMock` 分流。
6. mock 分支直接在内存里做 Wilcoxon，真实分支：
   - 从 `data/verification_queries.jsonl` 读取查询集
   - 用 `llm_service.generate_candidates(...)` 生成候选
   - 用 `verifier_service.get_verifier(...).score_batch(...)` 计算触发/无触发分数
   - 用 `scipy.stats.wilcoxon` 计算 p-value
7. 结果写入 `backend/data/tasks/{task_id}.json`。
8. 前端通过 `/verification/status/{taskId}` 或 `/verification/result/{taskId}` 取回完整结果。

### 8.6 p-value / 显著性计算

1. `backend/app/services/verification_service.py` 在 real 与 mock 分支都用 `scipy.stats.wilcoxon`。
2. `backend/app/routers/statistics.py` 读取任务证据 JSON 后，再对前几个样本子集重复做 Wilcoxon 收敛曲线。
3. `frontend/src/components/panels/PanelVerification.vue` 将 p-value 与阈值 `0.01` 做比较，并展示 `detected / weak / not_detected` 语义。

### 8.7 验证器行为核验

1. 用户在 `frontend/src/components/panels/PanelReasoningEffect.vue` 选择生成模型、Verifier、查询和特征。
2. 真实模式下调用 `frontend/src/api/behavior.ts:evaluateBehavior(...)`。
3. 请求进入 `backend/app/routers/behavior.py:evaluate_behavior`。
4. `backend/app/services/llm_service.py:generate_candidates(...)` 从 vLLM/OpenAI-compatible 接口获取候选。
5. `backend/app/services/verifier_service.py:get_verifier(...).score_batch(...)` 对候选做打分。
6. 后端输出候选排名、Top-1 变化、Top-5 重排率、KL 散度与相关性。

### 8.8 模型资产列表与分类

1. `frontend/src/stores/demo.ts:loadModels()` 拉取 `/api/v1/models`。
2. `backend/app/routers/models.py:api_list_models` 读取 `data/model_registry.json`。
3. `PanelModelManagement.vue` 按 `role` 将资产分成基础 Verifier、水印 Verifier、待检测目标、候选生成模型四类。
4. 点击“测试加载”时，`models.py:api_test_load` 走 `transformers` 或 `vllm_list_models()`。

### 8.9 统计证据与下载

1. `PanelStatistics.vue` 计划通过 `frontend/src/api/statistics.ts:getEvidence(...)` 拉证据。
2. 后端 `backend/app/routers/statistics.py:get_statistics_evidence` 读取 `backend/data/tasks/{task_id}.json`。
3. 该接口返回特征分布、delta 分布、p-value 收敛数据和摘要。
4. 但当前前端实现里 `lastTaskId = ''`，因此默认直接展示 mock 图表，不会真正触发该接口。

## 9. 实现状态与架构风险

| 模块 | 当前状态 | 发现的问题 | 对架构图的影响 | 建议画法 |
|---|---|---|---|---|
| 前端路由 | `route` 状态机 | 没有 `vue-router` | 不能画成 URL 路由树 | 画成“页面状态切换” |
| 前端 API 层 | 混合 | `axios` 与 `fetch` 两套封装并存 | 容易出现契约分叉 | 画成两条前端 API 线 |
| 注入任务 | 真实 + mock | 前后端都有双分支 | 需要区分沙箱/真实路径 | 画成条件分支 |
| 版权归属验证 | 真实 + mock | 脚本文件存在，但主链路在 `verification_service.py` | 不要把脚本误画成唯一入口 | 画成“service 主导，script 适配” |
| 统计证据 | 接口真实 | 前端默认 `lastTaskId = ''`，页面实际展示 mock | 不能直接标为“真实闭环” | 画成“接口存在，前端默认 mock” |
| 模型注册 | 真实 | JSON 注册表为空，初始无真实资产 | 资产图初始应为空或 demo 数据 | 画成“空注册表 + 支持写入” |
| 任务持久化 | 部分 | `task_manager` 内存态，重启清空 | 不能画成持久化数据库 | 画成“内存态 + JSON 证据” |
| 外部推理 | 真实 | 依赖 `vllm`、`openai`、`transformers`、`torch` | 真实链路受环境强约束 | 画成外部服务节点 |
| 配置体系 | 分裂 | `backend/app/config.py` 与 `backend/app/core/config.py` 并存，且默认值不一致 | 画图时必须区分“旧配置/新配置” | 画成双配置源 |

### 9.1 需要特别标注的风险

- `start-remote.sh` 和 `deploy-remote.sh` 都导出 `VGUARD_MOCK_MODE="auto"`，但 `backend/app/config.py` 与 `backend/app/core/config.py` 都只把 `true/1/yes` 视为真值，因此 `auto` 实际不会按字面“自动判断”生效。
- `backend/app/config.py` 与 `backend/app/core/config.py` 都在定义模型、数据集和 mock 开关，但取值规则不完全一致；`backend/app/main.py` 主要使用 `app.core.config`，而部分 service/router 仍使用 `app.config`。
- `backend/app/services/verification_runner.py` 目前只是脚本文件存在，主验证链路并未调用它。
- `frontend/src/components/panels/PanelStatistics.vue` 真实接口存在，但页面默认不走真实任务 ID，因此不能把它画成“已经闭环的取证下载”。
- `frontend/src/composables/useInjection.ts`、`useVerification.ts`、`useWebSocket.ts` 目前更像通用工具层，不应强行画成当前页面主调用链。

## 10. 绘图节点清单

### 10.1 硬件架构图节点

| 节点ID | 节点名称 | 部署位置 | 软件/服务 | 是否真实存在 | 适合使用的图形 |
|---|---|---|---|---|---|
| A | 浏览器 | 用户侧 | Vue SPA | 是 | 圆角矩形 |
| B | 前端静态资源 / Vite dev server | 本地或开发机 | Vite | 是 | 圆角矩形 |
| C | FastAPI 后端 | 本地或远程 GPU 服务器 | `backend/app/main.py` | 是 | 圆角矩形 |
| D | 任务管理器 | 后端进程内 | `task_manager.py` | 是 | 小型服务框 |
| E | 训练脚本 | 后端进程内线程 | `injection_runner.py` | 是 | 算法框 |
| F | Verifier 推理服务 | 后端进程内 | `verifier_service.py` | 是 | 算法框 |
| G | 认证 SQLite | `data/auth.db` / `backend/data/*.sqlite3` | SQLite | 是 | 数据库图标 |
| H | 模型注册 JSON | `data/model_registry.json` | JSON 文件 | 是 | 文件图标 |
| I | 任务证据目录 | `backend/data/tasks` | 文件系统 | 是 | 文件夹图标 |
| J | 外部 LLM 服务 | 远端或本机 | vLLM / OpenAI-compatible | 条件存在 | 云服务图标 |

### 10.2 硬件架构连线

- 浏览器 → 前端静态资源：`HTTP`
- 浏览器 → FastAPI：`HTTP / WebSocket`
- FastAPI → 任务管理器：`进程内调用`
- FastAPI → 训练脚本：`线程池 / 函数调用`
- FastAPI → Verifier / LLM 服务：`本地推理 / HTTP`
- FastAPI → SQLite / JSON / 文件夹：`文件读写`

### 10.3 功能架构图节点

- 系统首页 / 项目概览
- 登录与认证
- 模型管理
- 水印注入
- 验证器行为核验
- 版权归属验证
- 统计证据报告
- 模型测试
- 关于页

## 11. 代码证据索引

| 编号 | 结论 | 文件路径 | 函数/类/配置 |
|---|---|---|---|
| 1 | 前端无 `vue-router`，靠状态机切页 | `frontend/src/App.vue`, `frontend/src/stores/navigation.ts` | `nav.push(...)`, `route: 'landing'|'login'|'home'` |
| 2 | 前端真实 HTTP 主封装 | `frontend/src/services/api.ts` | `fetchHealth`, `startInjection`, `startVerification`, `generateCandidates` |
| 3 | 前端另一套 API 封装 | `frontend/src/api/*.ts` | `listModels`, `evaluateBehavior`, `getEvidence` |
| 4 | 登录 / session 认证 | `backend/app/routers/auth.py`, `backend/app/services/auth_db.py` | `login`, `register`, `me`, `logout`, `AuthDB` |
| 5 | 任务编排中心 | `backend/app/services/task_manager.py` | `TaskManager`, `TaskType`, `TaskStatus` |
| 6 | 注入真实链路 | `backend/app/services/injection_service.py`, `backend/app/scripts/injection_runner.py` | `run_injection_task`, `run_injection` |
| 7 | 验证真实链路 | `backend/app/services/verification_service.py` | `run_verification_task`, `_run_real`, `_run_mock` |
| 8 | 候选生成真实链路 | `backend/app/services/candidates_service.py`, `backend/app/services/llm_service.py` | `run_candidates`, `generate_candidates`, `vllm_list_models` |
| 9 | Verifier 打分服务 | `backend/app/services/verifier_service.py` | `VerifierScorer`, `score_batch`, `get_verifier` |
| 10 | 模型注册表 | `backend/app/services/model_registry.py` | `list_models`, `register_model`, `delete_model` |
| 11 | 统计证据接口 | `backend/app/routers/statistics.py` | `get_statistics_evidence` |
| 12 | Mock 数据源 | `backend/app/services/mock_data.py` | `DISTRIBUTION_DATA`, `SENSITIVITY_DATA`, `HEATMAP_DATA`, `INJECTION_CURVE` |
| 13 | FastAPI 主入口与 SPA 回源 | `backend/app/main.py` | `SPAMiddleware`, `config`, `health` |
| 14 | 部署脚本 | `start-local.sh`, `start-local.bat`, `start-remote.sh`, `deploy-remote.sh` | SSH tunnel / uvicorn loop |

## 12. 审计覆盖范围汇总

- 前端源码文件：`71`
- 后端源码文件：`29`
- 数据文件：`2`
- 重点启动/部署脚本：`4`
- 真实 HTTP 路由 + WS 路由：`27`
- 前端真实 API 函数：`29`
- 发现的数据库实体：`2` 张 SQL 表 + `4` 个 JSON 注册分桶
- 真实业务链路：`登录、模型管理、注入、行为核验、版权验证、统计证据`
- mock 业务链路：`图表数据、部分注入、部分验证、模型管理回退、统计页默认展示`

## 13. 最后判断

VGuard 不是单纯的“前后端 demo 目录”，而是一个同时包含：

- 真实 FastAPI 任务编排与落盘链路
- 真实模型注册 / 认证数据库
- 真实 Verifier 打分与统计检验
- mock / real 双分支前端展示层
- 远程 GPU 部署与本地 SSH 代理启动脚本

的混合架构。

如果要画图，建议把“mock 沙箱”和“真实 GPU 链路”分成两套路径分别画，不要合并成一条线。
