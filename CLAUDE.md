# MS-Scaffold 微服务脚手架

## 项目概述

MS-Scaffold 是一个基于 FastAPI + SQLAlchemy 2.0 的通用微服务脚手架，提供了完整的开发框架和最佳实践。该脚手架参考 ms-credits 项目架构设计，提供了开箱即用的微服务开发环境。

## 系统架构

基于 FastAPI + SQLAlchemy 2.0 异步架构，采用分层设计模式：

```
presentation layer (API层) → service layer (业务层) → repository layer (数据层)
```

### 双端架构设计
- **用户端API** (端口8000): 面向C端用户，使用RS256+RSA公钥鉴权
- **管理员API** (端口8001): 面向管理后台，使用HS256+密钥鉴权，独立权限体系
- **独立Swagger文档**: 用户端和管理端分别提供专用API文档

## 核心特性

### 1. 数据库连接管理 (Database)
- **主数据库**: MySQL主数据库，存储核心业务数据
- **集成数据库**: MS_HD数据库集成，支持跨服务数据访问
- **异步连接池**: 高性能异步数据库连接池管理
- **自动表名**: 驼峰命名自动转换为下划线表名

### 2. 认证与授权 (Authentication)
- **双重JWT认证**: RS256(用户端) + HS256(管理端)
- **RSA公钥验证**: 用户端使用rsa_public.pem验证
- **角色权限控制**: 支持多级权限管理
- **API密钥验证**: 内部服务调用密钥验证

### 3. 缓存与会话 (Cache & Session)
- **Redis异步连接池**: 高性能缓存和会话存储
- **连接池管理**: 自动连接池创建和清理
- **缓存工具**: 通用的缓存操作封装

### 4. 日志系统 (Logging)
- **日志格式**: `%(asctime)s - [%(levelname)s] - %(name)s - %(message)s`
- **时间格式**: `%Y-%m-%d %H:%M:%S`
- **日志处理器**: 控制台输出 + 文件轮转记录
- **并发安全**: 使用ConcurrentRotatingFileHandler支持多进程日志
- **文件轮转**: 10MB自动轮转，保留100个备份文件

### 5. CRUD基类 (Data Access)
- **通用CRUD操作**: 标准化的数据库操作方法
- **复杂查询支持**: 支持join、where、order等复杂查询
- **自动序列化**: Pydantic模型自动序列化
- **分页查询**: 内置分页查询支持

#### CRUD使用规范
使用 `XxDal(db_session)` 模式进行数据库操作，DAL 类继承自 DalBase：

```python
# 正确的CRUD使用方式
from app.crud.user import UserDal
from app.core.async_db import get_db_session

async def get_user_service(user_id: str):
    async with get_db_session() as db:
        user_dal = UserDal(db)  # 传入AsyncSession，实例化DAL
        return await user_dal.get_data(user_id)  # 调用DalBase的方法

# 创建用户示例
async def create_user_service(user_data: UserCreate):
    async with get_db_session() as db:
        user_dal = UserDal(db)
        return await user_dal.create_data(user_data.model_dump())

# 更新用户示例
async def update_user_service(user_id: str, user_data: UserUpdate):
    async with get_db_session() as db:
        user_dal = UserDal(db)
        return await user_dal.put_data(user_id, user_data.model_dump())

# 查询用户列表示例
async def get_users_service(page: int = 1, limit: int = 10):
    async with get_db_session() as db:
        user_dal = UserDal(db)
        return await user_dal.get_datas(page=page, limit=limit)

# 业务逻辑层Service类示例
class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_dal = UserDal(db)  # 在构造函数中初始化DAL

    async def create_user(self, user_data: UserCreate):
        return await self.user_dal.create_data(user_data.model_dump())
```

**关键要点**:
1. 必须使用 `XxDal(AsyncSession)` 传入数据库会话
2. DAL类继承自 DalBase，在 `__init__` 中调用 `super().__init__(db=db, model=Model)`
3. 支持的DalBase方法包括:
   - `get_data()` - 获取单个记录
   - `create_data()` - 创建新记录
   - `put_data()` - 更新记录
   - `delete_datas()` - 删除记录
   - `get_datas()` - 获取多个记录（支持分页）
4. 所有操作都是异步的，需要使用 await 关键字
5. Service层通常在构造函数中初始化多个DAL实例

### 6. 异常处理 (Exception Handling)
- **全局异常捕获**: 统一的异常处理机制
- **自定义异常**: 业务异常定义和处理
- **错误响应**: 标准化的错误响应格式

## 项目结构

### 核心目录结构

```
ms-image/
├── app/
│   ├── core/                  # 核心模块
│   │   ├── config.py         # 配置管理
│   │   ├── async_db.py       # 异步数据库连接
│   │   ├── exception.py      # 异常处理
│   │   ├── redis_manager.py  # Redis连接管理
│   │   └── crud.py           # CRUD基类
│   ├── lib/                   # 工具库
│   │   ├── log/              # 日志模块
│   │   │   ├── log_config.py # 日志配置
│   │   │   └── log_request.py# 请求日志
│   │   ├── conversion.py     # 数据转换工具
│   │   ├── message.py        # 消息模板
│   │   ├── response.py       # 响应工具
│   │   ├── oid.py           # ObjectId处理
│   │   └── pydantic_object_id.py # Pydantic ObjectId
│   ├── models/               # 数据模型
│   │   └── base.py           # 基础模型类
│   ├── schemas/              # Pydantic模式
│   │   └── base.py           # 基础响应模式
│   ├── api/                  # API路由
│   │   ├── api_v1/           # 用户端API v1
│   │   │   ├── endpoints/    # API端点
│   │   │   │   └── health.py # 健康检查
│   │   │   └── api.py        # 路由聚合
│   │   ├── admin_v1/         # 管理端API v1
│   │   │   ├── endpoints/    # 管理端点
│   │   │   │   └── admin.py  # 管理接口
│   │   │   └── api.py        # 管理路由聚合
│   │   └── deps.py           # 依赖注入
│   ├── crud/                 # 数据访问层
│   ├── service/              # 业务逻辑层
│   └── ...
├── alembic_migrations/       # 数据库迁移
│   ├── env.py               # Alembic环境配置
│   ├── script.py.mako       # 迁移脚本模板
│   └── versions/            # 迁移版本文件
├── logs/                     # 日志文件
├── docs/                     # 项目文档
├── scripts/                  # 工具脚本
├── main.py                   # 应用入口
├── run_servers.py            # 双端启动脚本
├── start_user_api.py         # 用户端启动脚本
├── start_admin_api.py        # 管理端启动脚本
├── requirements.txt          # 依赖列表
├── docker-compose.yml        # Docker配置
├── Dockerfile                # Docker镜像
├── alembic.ini              # Alembic配置
├── .env.example             # 环境变量模板
└── README.md                # 项目说明
```

## API 接口设计

### 用户端API (端口8000)

#### 健康检查 `/api/v1/health`
```
GET    /health                                    # 健康检查
GET    /version                                   # 版本信息
```

### 管理端API (端口8001)

#### 管理员接口 `/api/v1/status`
```
GET    /status                                    # 管理员状态检查 (需要Basic Auth)
GET    /info                                      # 管理员信息 (需要Basic Auth)
```

## 业务流程

### 1. 应用启动流程
```
启动应用 → 初始化Redis连接池 → 注册路由 → 启动服务器 → 监听请求
```

### 2. 请求处理流程
```
接收请求 → 认证验证 → 路由匹配 → 业务处理 → 响应返回 → 日志记录
```

### 3. 数据库操作流程
```
获取会话 → 执行查询 → 处理结果 → 序列化响应 → 关闭会话
```

## 关键技术特性

### 1. 双端API架构
- **用户端**: RS256+RSA公钥鉴权，RESTful设计
- **管理端**: HS256+密钥鉴权，Basic Auth，独立Swagger文档
- **统一响应格式**: GenericResponse模板，完整的类型定义

### 2. 异步数据库
- **SQLAlchemy 2.0**: 现代化的异步ORM
- **连接池管理**: 自动连接池创建和清理
- **多数据库支持**: 主数据库 + 集成数据库

### 3. 并发安全
- **异步处理**: 基于asyncio的高并发处理
- **连接池**: 数据库和Redis连接池管理
- **日志安全**: 并发安全的日志记录

### 4. 可扩展性
- **模块化设计**: 清晰的分层架构
- **插件化**: 易于扩展新功能
- **配置驱动**: 环境变量配置管理

### 5. 开发友好
- **类型安全**: 完整的类型提示
- **自动文档**: Swagger API文档
- **热重载**: 开发环境自动重载

## 运行环境

### 开发环境
```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境
cp .env.example .env

# 启动双端服务
python run_servers.py

# 或者单独启动
python start_user_api.py   # 用户端
python start_admin_api.py  # 管理端
```

### API访问地址
- **用户端API文档**: http://localhost:8000/docs
- **管理端API文档**: http://localhost:8001/admin/docs
- **用户端API**: http://localhost:8000/ms-image/api/v1/
- **管理端API**: http://localhost:8001/ms-image/admin/api/v1/

### 生产环境
- Docker 容器化部署
- MySQL 主从复制
- Redis 缓存加速
- Nginx 反向代理

## 监控和日志

### 日志系统
- **日志格式**: 标准化的日志格式
- **文件轮转**: 自动日志轮转和备份
- **并发安全**: 多进程安全的日志记录
- **分级记录**: DEBUG/INFO/WARNING/ERROR分级

### 业务监控
- API 响应时间
- 数据库连接池状态
- 缓存命中率
- 错误率统计

## 安全考虑

### 认证安全
- JWT双重认证机制
- RSA公钥验证
- API密钥验证

### 数据安全
- 数据库连接加密
- 敏感信息环境变量存储
- API访问权限控制

## 技术栈

### 后端框架
- **FastAPI 0.115.6**: 异步Web框架，自动API文档生成
- **SQLAlchemy 2.0.36**: 异步ORM，类型安全的数据库操作
- **Pydantic 2.10.4**: 数据验证和序列化，类型提示支持
- **Alembic 1.13.1**: 数据库迁移管理

### 数据库与缓存
- **MySQL**: 主数据库，支持多库连接
- **Redis 5.2.1**: 缓存和会话存储
- **异步连接池**: 异步数据库连接池管理

### 认证与安全
- **JWT**: RS256(用户端) + HS256(管理端) 双重认证
- **RSA公钥验证**: 用户端使用rsa_public.pem验证
- **Basic Auth**: 管理端基础认证

### 开发工具
- **Uvicorn**: ASGI服务器，支持热重载
- **Docker**: 容器化部署
- **Pytest**: 单元测试框架

## 扩展功能

### 已实现特性
- ✅ 双端API架构（用户端+管理端）
- ✅ 异步数据库连接池
- ✅ Redis缓存管理
- ✅ JWT双重认证
- ✅ 全局异常处理
- ✅ 并发安全日志系统
- ✅ CRUD基类封装
- ✅ 自动API文档生成

### 可扩展功能
- 消息队列集成 (RabbitMQ)
- 文件上传服务 (OSS)
- 定时任务调度
- 服务监控和告警
- API限流和熔断
- 分布式锁机制
- 配置中心集成
- 服务注册与发现

## 部署说明

1. **环境配置**：复制 `.env.example` 为 `.env` 并配置相应参数
2. **数据库初始化**：运行数据库迁移脚本
3. **缓存配置**：配置 Redis 连接参数
4. **启动服务**：使用 Docker Compose 一键启动

## 版本历史

### v1.0.0 (当前版本)
- ✅ 基础脚手架架构
- ✅ 双端API支持
- ✅ 异步数据库连接
- ✅ Redis缓存管理
- ✅ JWT认证系统
- ✅ 日志系统
- ✅ 异常处理
- ✅ API文档生成

## 使用说明

### 1. 快速启动
```bash
# 克隆项目
cp -r ms-image my-new-service
cd my-new-service

# 安装依赖
pip install -r requirements.txt

# 配置环境
cp .env.example .env
# 编辑 .env 文件配置数据库等信息

# 启动服务
python run_servers.py
```

### 2. 开发新功能
- 在 `app/models/` 中定义数据模型
- 在 `app/schemas/` 中定义API模式
- 在 `app/crud/` 中创建CRUD操作类（继承CRUDBase）
- 在 `app/service/` 中实现业务逻辑（使用 `crud.xxdal(db)` 模式）
- 在 `app/api/` 中添加API端点
- 运行 `alembic revision --autogenerate` 生成迁移

#### CRUD开发模式
```python
# 1. app/models/user.py - 定义数据模型
from app.models.base import BaseModel

class User(BaseModel):
    __tablename__ = "users"
    name: str
    email: str

# 2. app/schemas/user.py - 定义API模式
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str

# 3. app/crud/user.py - 创建DAL类
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.core.crud import DalBase

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

# 4. app/service/user.py - 业务逻辑
from app.crud.user import UserDal
from app.core.async_db import get_db_session

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_dal = UserDal(db)

    async def get_user_by_id(self, user_id: str):
        return await self.user_dal.get_data(user_id)

    async def create_user(self, user_data: UserCreate):
        return await self.user_dal.create_user(user_data)

# 或者函数式写法
async def get_user_by_id(user_id: str):
    async with get_db_session() as db:
        user_dal = UserDal(db)
        return await user_dal.get_data(user_id)
```

### 3. 部署到生产
- 设置 `ENV=production`
- 配置生产数据库连接
- 使用 Docker 容器化部署
- 配置反向代理和负载均衡

## 项目信息

- **项目名称**: MS-Scaffold
- **技术栈**: FastAPI + SQLAlchemy 2.0 + MySQL + Redis
- **架构模式**: 分层架构 + 双端API
- **文档版本**: v1.0.0
- **创建日期**: 2025-01-15

## 重要提醒

### 开发规范
- 遵循 PEP 8 代码规范
- 使用类型提示
- 编写单元测试
- 保持代码简洁

### 安全注意事项
- 不要将敏感信息硬编码
- 使用环境变量管理配置
- 定期更新依赖包
- 启用
- 日志记录和监控