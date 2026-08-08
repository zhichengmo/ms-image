# MS-Scaffold 微服务脚手架
Author：Wen ZhiChao

> 基于 FastAPI + SQLAlchemy 2.0 的通用微服务脚手架，提供完整的开发框架和最佳实践

## 📖 项目概述

MS-Scaffold 是一个现代化的 FastAPI 微服务脚手架，采用异步架构设计，提供开箱即用的微服务开发环境。该脚手架参考了企业级微服务架构最佳实践，集成了完整的认证、缓存、日志、数据库等核心功能。

## ✨ 核心特性

### 🏗️ 双端架构
- **用户端API** (端口8000): 面向C端用户，使用RS256+RSA公钥鉴权
- **管理端API** (端口8001): 面向管理后台，使用HS256+密钥鉴权
- **独立文档**: 分别提供专用的Swagger API文档

### 🗄️ 数据层支持
- **MySQL异步连接池**: 主数据库 + 可选集成数据库支持
- **Redis缓存**: 异步连接池管理，支持缓存和会话存储
- **MongoDB支持**: 可选的NoSQL数据库支持
- **Alembic迁移**: 自动数据库迁移管理

### 🔐 认证与安全
- **双重JWT认证**: RS256(用户端) + HS256(管理端)
- **RSA密钥验证**: 支持RSA公钥/私钥对验证
- **Basic Auth**: 管理端基础认证支持
- **权限控制**: 多级权限管理体系

### 📊 监控与日志
- **结构化日志**: 统一的日志格式和轮转策略
- **并发安全**: 多进程安全的日志记录
- **请求追踪**: 完整的请求响应日志记录
- **异常处理**: 全局异常捕获和处理

### 🚀 开发体验
- **热重载**: 开发环境自动重载
- **类型安全**: 完整的类型提示支持
- **CRUD基类**: 标准化的数据操作封装
- **自动文档**: 自动生成API文档

## 🚀 快速开始

### 1. 使用脚手架创建新项目

#### 方法一：使用项目生成器（推荐）
```bash
# 克隆脚手架到本地
git clone https://github.com/your-org/ms-image.git
cd ms-image

# 在当前目录创建新项目
python create_new_project.py my-api-service

# 或指定目标目录（推荐）
python create_new_project.py my-api-service /path/to/your/projects

# 或在上级目录创建（避免嵌套在脚手架内）
python create_new_project.py my-api-service ../

# 进入新项目目录
cd ../my-api-service  # 或对应的目标路径
```

**使用说明**：
- `<项目名称>`: 必需参数，如 `user-service`、`order-api`
- `[目标目录]`: 可选参数，指定项目创建位置
  - 不指定：在当前目录（脚手架目录内）创建
  - 指定路径：如 `/home/user/projects` 或 `../`
  - 推荐使用 `../` 避免在脚手架目录内创建项目

#### 方法二：手动复制
```bash
# 复制脚手架目录
cp -r ms-image my-new-service
cd my-new-service

# 删除.git目录重新初始化
rm -rf .git
git init
```

### 2. 环境配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
vim .env  # 或使用其他编辑器
```

关键配置项：
```bash
# 应用基础配置
APPLICATION_NAME=My API Service
APPLICATION_PORT=8000

# 数据库配置
MYSQL_HOST=localhost
MYSQL_DB=my_service_db
MYSQL_USER=root
MYSQL_PW=your_password

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT密钥配置
SECRET_KEY=your-secret-key
ADMIN_SECRET_KEY=your-admin-secret
```

### 3. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 数据库初始化

```bash
# 初始化数据库迁移
alembic revision --autogenerate -m "Initial migration"

# 执行迁移
alembic upgrade head
```

### 5. 启动服务

#### 开发环境
```bash
# 启动双端服务（用户端8000 + 管理端8001）
python run_servers.py

# 或者单独启动
python start_user_api.py   # 仅用户端
python start_admin_api.py  # 仅管理端
```

#### 生产环境
```bash
# 使用Docker Compose
docker-compose up -d

# 或使用Gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### 6. 验证部署

访问以下地址验证服务：
- **用户端API文档**: http://localhost:8000/docs
- **管理端API文档**: http://localhost:8001/admin/docs
- **健康检查**: http://localhost:8000/api/v1/health
- **管理端状态**: http://localhost:8001/api/v1/status

## 🏛️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                   客户端层                                │
├─────────────────┬───────────────────────────────────────┤
│   用户端API     │          管理端API                     │
│   (端口8000)    │         (端口8001)                     │
│   RS256鉴权     │         HS256鉴权                      │
└─────────────────┴───────────────────────────────────────┘
           │                        │
           ▼                        ▼
┌─────────────────────────────────────────────────────────┐
│                   API路由层                              │
│              FastAPI + Pydantic                        │
└─────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                   业务逻辑层                             │
│               Service Layer                             │
└─────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                   数据访问层                             │
│           CRUD + Repository Pattern                     │
└─────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                   数据存储层                             │
│        MySQL + Redis + MongoDB(可选)                    │
└─────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
ms-image/
├── 📱 app/                          # 应用核心目录
│   ├── 🔧 core/                     # 核心模块
│   │   ├── config.py               # 配置管理
│   │   ├── async_db.py             # 异步数据库连接
│   │   ├── exception.py            # 异常处理
│   │   ├── redis_manager.py        # Redis连接管理
│   │   └── crud.py                 # CRUD基类
│   ├── 🛠️ lib/                      # 工具库
│   │   ├── log/                    # 日志模块
│   │   │   ├── log_config.py       # 日志配置
│   │   │   └── log_request.py      # 请求日志
│   │   ├── conversion.py           # 数据转换工具
│   │   ├── message.py              # 消息模板
│   │   ├── response.py             # 响应工具
│   │   └── oid.py                  # ObjectId处理
│   ├── 📊 models/                   # 数据模型
│   │   └── base.py                 # 基础模型类
│   ├── 📋 schemas/                  # Pydantic模式
│   │   └── base.py                 # 基础响应模式
│   ├── 🌐 api/                      # API路由
│   │   ├── api_v1/                 # 用户端API v1
│   │   │   ├── endpoints/          # API端点
│   │   │   └── api.py              # 路由聚合
│   │   ├── admin_v1/               # 管理端API v1
│   │   │   ├── endpoints/          # 管理端点
│   │   │   └── api.py              # 管理路由聚合
│   │   └── deps.py                 # 依赖注入
│   ├── 💾 crud/                     # 数据访问层
│   └── 🧠 service/                  # 业务逻辑层
├── 🔄 alembic_migrations/           # 数据库迁移
├── 📝 logs/                         # 日志文件
├── 🐳 docker-compose.yml            # Docker配置
├── 🚀 run_servers.py                # 双端启动脚本
├── 📦 requirements.txt              # 依赖列表
└── 📄 .env.example                  # 环境变量模板
```

## 🔧 开发指南

### 1. 添加新的API端点

#### 用户端API
```python
# app/api/api_v1/endpoints/users.py
from fastapi import APIRouter, Depends
from app.schemas.base import GenericResponse

router = APIRouter()

@router.get("/users", response_model=GenericResponse)
async def get_users():
    return GenericResponse(success=True, data={"users": []})
```

#### 管理端API
```python
# app/api/admin_v1/endpoints/admin_users.py
from fastapi import APIRouter, Depends
from app.api.deps import get_admin_user

router = APIRouter()

@router.get("/users", dependencies=[Depends(get_admin_user)])
async def admin_get_users():
    return {"data": {"users": []}}
```

### 2. 添加数据模型

```python
# app/models/user.py
from sqlalchemy import Column, Integer, String, DateTime
from app.models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
```

### 3. 添加CRUD操作（DAL模式）

```python
# app/crud/user.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.crud import DalBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse

class UserDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=User)

    async def create_user(self, user_data: UserCreate):
        """创建新用户"""
        return await self.create_data(user_data.model_dump(), v_schema=UserResponse)

    async def update_user(self, user_id: int, user_data: UserUpdate):
        """更新用户信息"""
        update_data = user_data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_data(user_id, v_schema=UserResponse)
        return await self.put_data(user_id, update_data, v_schema=UserResponse)

    async def get_user_by_email(self, email: str):
        """根据邮箱获取用户"""
        return await self.get_data(email=email, v_schema=UserResponse)
```

### 4. 添加业务逻辑（重要：DAL使用规范）

**✅ 正确的使用方式** - 使用 `XxDal(AsyncSession)` 模式：

```python
# app/service/user_service.py
from app.crud.user import UserDal
from app.core.async_db import get_db_session

# 方式一：Service类模式（推荐）
class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_dal = UserDal(db)  # 关键：传入AsyncSession

    async def create_user(self, user_data: UserCreate):
        return await self.user_dal.create_user(user_data)

    async def get_user(self, user_id: int):
        return await self.user_dal.get_data(user_id)

    async def get_users_list(self, page: int = 1, limit: int = 10):
        return await self.user_dal.get_datas(page=page, limit=limit)

    async def update_user(self, user_id: int, user_data: UserUpdate):
        return await self.user_dal.update_user(user_id, user_data)

    async def delete_user(self, user_id: int, soft: bool = True):
        if soft:
            await self.user_dal.put_data(user_id, {"is_del": 1})
        else:
            await self.user_dal.delete_datas([user_id])

# 方式二：函数式模式
async def create_user_func(user_data: UserCreate):
    async with get_db_session() as db:
        user_dal = UserDal(db)  # 关键：传入AsyncSession
        return await user_dal.create_user(user_data)

async def get_user_func(user_id: int):
    async with get_db_session() as db:
        user_dal = UserDal(db)  # 关键：传入AsyncSession
        return await user_dal.get_data(user_id)
```

**❌ 错误的使用方式**：
```python
# 不要这样做
user_dal = UserDal()  # 缺少AsyncSession参数
user_data = await user_crud.create(user_data)  # 使用了过时的模式
```

**🔑 关键要点**：
1. 必须使用 `XxDal(AsyncSession)` 传入数据库会话
2. DAL类继承自 DalBase，在构造函数中调用 `super().__init__(db=db, model=Model)`
3. 支持的DalBase方法包括：
   - `get_data()` - 获取单个记录
   - `create_data()` - 创建新记录
   - `put_data()` - 更新记录
   - `delete_datas()` - 删除记录
   - `get_datas()` - 获取多个记录（支持分页）
4. Service层推荐在构造函数中初始化DAL实例
5. 可以在DAL中添加业务相关的自定义方法（如 `create_user`, `get_user_by_email` 等）

## 🔐 认证配置

### RS256 (用户端)
1. 生成RSA密钥对：
```bash
# 生成私钥
openssl genpkey -algorithm RSA -out rsa_private.pem -pkcs8 -aes256

# 提取公钥
openssl pkey -in rsa_private.pem -pubout -out rsa_public.pem
```

2. 将`rsa_public.pem`放在项目根目录

### HS256 (管理端)
在`.env`文件中设置：
```bash
ADMIN_SECRET_KEY=your-256-bit-secret-key-here
```

## 📋 API接口规范

### 用户端API

#### 健康检查
```http
GET /api/v1/health
```

#### 版本信息
```http
GET /api/v1/version
```

### 管理端API

#### 状态检查
```http
GET /admin/api/v1/status
Authorization: Basic <base64(username:password)>
```

#### 系统信息
```http
GET /admin/api/v1/info
Authorization: Basic <base64(username:password)>
```

### 统一响应格式

```json
{
  "success": true,
  "data": {},
  "message": "操作成功",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 🐳 Docker部署

### 开发环境
```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down
```

### 生产环境
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=production
    restart: unless-stopped
```

## 📊 监控与日志

### 日志配置
- **日志级别**: DEBUG/INFO/WARNING/ERROR
- **日志格式**: `%(asctime)s - [%(levelname)s] - %(name)s - %(message)s`
- **文件轮转**: 10MB自动轮转，保留100个备份
- **并发安全**: 支持多进程环境

### 日志位置
```
logs/
├── app.log              # 应用日志
├── request.log          # 请求日志
├── error.log            # 错误日志
└── gunicorn_error.log   # Gunicorn错误日志
```

### 监控指标
- API响应时间
- 数据库连接池状态
- Redis连接状态
- 错误率统计

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_api.py

# 生成覆盖率报告
pytest --cov=app tests/
```

## 🔄 数据库迁移

```bash
# 创建新迁移
alembic revision --autogenerate -m "Add user table"

# 升级到最新版本
alembic upgrade head

# 降级到指定版本
alembic downgrade -1

# 查看迁移历史
alembic history
```

## 📈 性能优化

### 数据库优化
- 使用异步连接池
- 适当的索引策略
- 查询优化和分页

### 缓存策略
- Redis缓存热点数据
- 合理的缓存过期时间
- 缓存预热和更新

### 异步处理
- 使用async/await
- 异步数据库操作
- 异步HTTP客户端

## 🛡️ 安全最佳实践

- JWT令牌安全管理
- API访问权限控制
- 敏感信息环境变量存储
- HTTPS强制使用
- 输入验证和SQL注入防护

## 📚 技术栈

| 类别 | 技术选择 | 版本 | 说明 |
|------|----------|------|------|
| Web框架 | FastAPI | 0.115.6 | 高性能异步Web框架 |
| ORM | SQLAlchemy | 2.0.36 | 现代化异步ORM |
| 数据验证 | Pydantic | 2.10.4 | 类型安全的数据验证 |
| 数据库 | MySQL | 8.0+ | 关系型数据库 |
| 缓存 | Redis | 5.2.1+ | 内存数据库 |
| 服务器 | Uvicorn | 0.21.0 | ASGI服务器 |
| 迁移 | Alembic | 1.13.1 | 数据库迁移工具 |
| 容器化 | Docker | - | 应用容器化 |

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📝 更新日志

### v1.0.0 (2024-01-15)
- ✅ 初始脚手架发布
- ✅ 双端API架构
- ✅ JWT双重认证
- ✅ 异步数据库支持
- ✅ Redis缓存集成
- ✅ 完整的日志系统
- ✅ Docker容器化支持

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 💬 技术支持

[//]: # (- 📧 技术问题: [issues]&#40;https://github.com/your-org/ms-image/issues&#41;)

[//]: # (- 📖 文档: [Wiki]&#40;https://github.com/your-org/ms-image/wiki&#41;)

[//]: # (- 💡 特性建议: [discussions]&#40;https://github.com/your-org/ms-image/discussions&#41;)

---

**MS-Scaffold** - 让微服务开发更简单 🚀