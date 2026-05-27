# 智能任务协同Agent系统

基于 LangGraph + LangChain 的企业级智能协同平台，实现了混合存储架构（知识图谱 + 关系型数据库）、意图识别分发路由、RAG向量检索等功能。

## 功能特性

### 1. 智能对话系统
- 基于 LangGraph ReAct 模式的 Agent 编排
- 意图识别与智能路由分发
- Agent 推理过程可视化
- 支持 RAG 知识检索、图谱查询、数据库查询

### 2. 任务协同中心
- 任务创建、分配、状态管理
- 优先级和截止日期管理
- 任务评分系统
- 项目-任务多层级关联

### 3. 知识图谱管理
- Neo4j 图数据库存储实体关系
- 可视化知识图谱展示
- Cypher 查询支持
- 多跳关系查询优化

### 4. 监控与日志
- Token 消耗实时监控
- 成本分析与预警
- Agent 执行链路追踪
- 系统日志与权限审计

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (React)                        │
│   智能对话 | 任务中心 | 项目管理 | 知识图谱 | 监控中心     │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   API Gateway (FastAPI)                  │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Intent      │   │   RAG        │   │  Graph        │
│  Router      │   │   Service    │   │  Service     │
│  (意图识别)   │   │  (向量检索)   │   │  (Neo4j)     │
└───────────────┘   └───────────────┘   └───────────────┘
        │                                       │
        └───────────────────┬───────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│               LangGraph Agent Core                       │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│   │ Intent  │→ │  Tool   │→ │  LLM    │→ │ Response│   │
│   │ Node    │  │ Call    │  │ Reason  │  │ Format  │   │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    Neo4j     │   │    MySQL     │   │   Chroma      │
│  (图数据库)   │   │  (关系库)    │   │  (向量库)     │
└───────────────┘   └───────────────┘   └───────────────┘
```

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- Neo4j 5.x (可选，未启动时自动降级为演示模式)
- MySQL 8.0 (可选，未启动时自动降级为演示模式)
- Chroma (可选)

### 一体化部署（推荐）

```bash
# 1. 安装后端依赖
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 LLM 配置（至少需要 OPENAI_API_KEY）

# 2. 构建前端
cd ../frontend
npm install
npm run build

# 3. 启动服务（前后端一体化）
cd ../backend
uvicorn app.main:app --reload --port 8000
uvicorn app.main:app --reload
```

启动后访问：
- **前端页面**: http://localhost:8000/
- **API 文档**: http://localhost:8000/docs

### 配置说明

编辑 `backend/.env`:

```env
# LLM 配置
OPENAI_API_KEY=your-api-key

# Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# MySQL 配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=enterprise_agent
```

## 项目结构

```
enterprise-agent-project/
├── backend/
│   ├── app/
│   │   ├── agent/          # LangGraph Agent 定义
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   └── services/       # 业务服务
│   │       ├── intent_router.py   # 意图识别路由
│   │       ├── rag_service.py     # RAG 向量检索
│   │       ├── graph_service.py   # Neo4j 图谱服务
│   │       └── cost_monitor.py    # 成本监控
│   ├── static/             # 前端构建产物（自动部署）
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── components/      # 组件
    │   ├── pages/           # 页面
    │   └── ...
    └── package.json
```

## 核心功能说明

### 意图识别与路由

系统支持以下意图类型：

| 意图类型 | 说明 | 路由目标 |
|---------|------|---------|
| query_score | 查询评分 | DB |
| query_task_status | 查询任务状态 | DB |
| rag_semantic | 语义检索 | RAG |
| rag_similar | 相似任务 | RAG |
| graph_traverse | 图谱遍历 | Graph |
| complex_reasoning | 复杂推理 | LLM |
| task_create | 创建任务 | LLM |

### 权限控制

采用"权限交集原则"，确保数据访问安全：

- **向量检索层**：元数据过滤 (Metadata Filtering)
- **Tool 底层**：强制身份鉴权逻辑
- **数据层**：权限交集验证

### 成本治理

- Token 消耗实时追踪
- 分级熔断与模型降级
- 预算预警机制
- 成本分布分析

## 访问说明

启动服务后：
- **前端应用**: http://localhost:8000/
- **API 文档**: http://localhost:8000/docs

## License

MIT
