# FastAPI 脚手架使用指南

本文档介绍如何使用 ms-scaffold 脚手架快速创建新的 FastAPI 项目。

## 🚀 快速使用方式

### 方式一：使用内置生成器（推荐）

#### 1. 基本使用
```bash
# 在脚手架目录中
cd /Users/ayogg/Documents/project/ms-scaffold

# 创建新项目
python create_new_project.py my-new-service

# 或指定目标目录
python create_new_project.py my-new-service ~/projects
```

#### 2. 设置全局命令（一次性设置）
```bash
# 在脚手架目录中执行
python setup_global_generator.py

# 添加到 PATH（根据提示操作）
export PATH="~/.fastapi-templates:$PATH"

# 现在可以在任何地方使用
fastapi-new my-new-service
```

### 方式二：直接复制（简单快速）

```bash
# 复制整个脚手架目录
cp -r /Users/ayogg/Documents/project/ms-scaffold ~/projects/my-new-service

# 进入新项目目录
cd ~/projects/my-new-service

# 清理不需要的文件
rm create_new_project.py setup_global_generator.py cookiecutter.json USAGE.md

# 手动替换项目名称（在各配置文件中）
```

### 方式三：使用 Cookiecutter

```bash
# 安装 cookiecutter
pip install cookiecutter

# 从脚手架创建项目
cookiecutter /Users/ayogg/Documents/project/ms-scaffold
```

## 📋 项目创建后的步骤

无论使用哪种方式创建项目，都需要执行以下步骤：

### 1. 配置环境
```bash
cd your-new-project

# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
vim .env  # 或使用其他编辑器
```

### 2. 安装依赖
```bash
# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 数据库设置
```bash
# 生成初始迁移
alembic revision --autogenerate -m "Initial migration"

# 执行迁移
alembic upgrade head
```

### 4. 启动服务
```bash
# 方式1: 同时启动双端
python run_servers.py

# 方式2: 分别启动
python start_user_api.py   # 用户端 (8000)
python start_admin_api.py  # 管理端 (8001)

# 方式3: 使用 Docker
docker-compose up -d
```

### 5. 验证服务
访问以下地址确认服务正常：
- 用户端API文档: http://localhost:8000/docs
- 管理端API文档: http://localhost:8001/admin/docs

## 🔧 项目定制

### 修改项目名称和配置

如果使用直接复制方式，需要手动替换以下文件中的项目名称：

#### 1. 应用配置 (`app/core/config.py`)
```python
# 修改应用名称
APPLICATION_NAME: str = "Your Service Name"
```

#### 2. 主程序 (`main.py`)
```python
# 修改根路径
root_path='/your-service'
```

#### 3. 环境变量 (`.env`)
```bash
# 修改应用名称和数据库名
APPLICATION_NAME=Your Service Name
MYSQL_DB=your_service_db
```

#### 4. 数据库配置 (`alembic.ini`)
```ini
# 修改数据库连接
sqlalchemy.url = mysql+pymysql://root:password@localhost/your_service_db
```

#### 5. Docker 配置 (`docker-compose.yml`)
```yaml
# 修改数据库名称
MYSQL_DATABASE: your_service_db
```

### 添加新功能

#### 1. 添加数据模型
```python
# app/models/your_model.py
from app.models.base import BaseTimeModel
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

class YourModel(BaseTimeModel):
    __tablename__ = "your_table"

    name: Mapped[str] = mapped_column(String(100), comment="名称")
```

#### 2. 添加 API 端点
```python
# app/api/api_v1/endpoints/your_endpoint.py
from fastapi import APIRouter, Depends
from app.schemas.base import GenericResponse

router = APIRouter()

@router.get("/your-endpoint", response_model=GenericResponse[dict])
async def your_endpoint():
    return GenericResponse(
        success=True,
        message="成功",
        data={"result": "data"}
    )
```

#### 3. 注册路由
```python
# app/api/api_v1/api.py
from app.api.api_v1.endpoints import your_endpoint

api_router.include_router(your_endpoint.router, tags=["Your Feature"])
```

## 🛠️ 高级配置

### 自定义生成器

如果需要自定义项目生成逻辑，可以修改 `create_new_project.py`:

```python
# 添加更多文件替换规则
replacements = {
    'ms-scaffold': project_name.lower(),
    # 添加更多替换规则...
}

# 添加更多需要处理的文件
files_to_replace = [
    'app/core/config.py',
    # 添加更多文件...
]
```

### Git 模板仓库

将脚手架推送到 Git 仓库，然后：

```bash
# 使用 Git 模板创建项目
git clone https://github.com/your-username/ms-scaffold-template.git my-new-service
cd my-new-service
rm -rf .git
git init
```

### 创建私有模板仓库

1. 在 GitHub/GitLab 上创建私有仓库
2. 推送脚手架代码
3. 团队成员可以直接克隆使用

## 📝 最佳实践

### 1. 环境变量管理
- 永远不要提交 `.env` 文件
- 为不同环境准备不同的 `.env` 模板
- 使用有意义的默认值

### 2. 数据库迁移
- 每次模型更改后都要生成迁移文件
- 在生产环境谨慎执行迁移
- 备份数据库再执行迁移

### 3. 项目结构
- 保持清晰的分层架构
- 使用有意义的文件和目录命名
- 及时更新文档

### 4. 版本控制
```bash
# 创建项目后立即初始化 Git
git init
git add .
git commit -m "Initial commit from ms-scaffold"
```

## 🔧 故障排除

### 常见问题

#### 1. 端口占用
```bash
# 检查端口使用情况
lsof -i :8000
lsof -i :8001

# 修改端口配置
# 在 .env 文件中修改 APPLICATION_PORT
```

#### 2. 数据库连接失败
```bash
# 检查数据库服务
mysqladmin ping

# 检查连接配置
# 确认 .env 中的数据库配置正确
```

#### 3. 依赖安装失败
```bash
# 升级 pip
pip install --upgrade pip

# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 4. 权限问题
```bash
# 确保脚本有执行权限
chmod +x start_user_api.py start_admin_api.py
```

## 📞 支持

如果遇到问题：

1. 检查本文档的故障排除部分
2. 查看项目的 `README.md` 和 `CLAUDE.md`
3. 检查日志文件 `logs/` 目录
4. 确认环境配置和依赖版本

## 🎯 提示

- 建议为每个项目创建独立的虚拟环境
- 定期更新脚手架模板以包含最新的最佳实践
- 可以根据团队需求定制脚手架内容
- 考虑在 CI/CD 中集成项目生成器