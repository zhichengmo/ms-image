#!/usr/bin/env python3
"""
设置全局 FastAPI 项目生成器
将脚手架配置为全局可用的项目生成器
"""

import os
import shutil
import sys
from pathlib import Path


def setup_global_generator():
    """设置全局项目生成器"""

    # 当前脚手架目录
    scaffold_dir = Path(__file__).parent.absolute()

    # 用户主目录
    home_dir = Path.home()

    # 创建 .fastapi-templates 目录
    templates_dir = home_dir / '.fastapi-templates'
    templates_dir.mkdir(exist_ok=True)

    # 复制脚手架到模板目录
    target_scaffold_dir = templates_dir / 'ms-scaffold'

    print(f"🚀 正在设置全局 FastAPI 项目生成器...")
    print(f"📁 模板目录: {target_scaffold_dir}")

    try:
        # 如果目标目录存在，先删除
        if target_scaffold_dir.exists():
            shutil.rmtree(target_scaffold_dir)

        # 复制脚手架
        shutil.copytree(scaffold_dir, target_scaffold_dir, ignore=shutil.ignore_patterns(
            '__pycache__',
            '*.pyc',
            '.git',
            '.idea',
            '.vscode',
            'logs',
            '*.log',
            '.env',
            'setup_global_generator.py'
        ))

        # 创建全局命令脚本
        create_global_command(templates_dir)

        print("✅ 全局生成器设置成功!")
        print("\n🎯 使用方法:")
        print("  fastapi-new <项目名称> [目标目录]")
        print("\n📖 示例:")
        print("  fastapi-new my-api-service")
        print("  fastapi-new user-service ~/projects")

        print(f"\n📋 如果命令不可用，请将以下目录添加到 PATH:")
        print(f"  export PATH=\"{templates_dir}:$PATH\"")
        print(f"  # 或者添加到 ~/.bashrc 或 ~/.zshrc")

    except Exception as e:
        print(f"❌ 设置失败: {e}")
        return False

    return True


def create_global_command(templates_dir: Path):
    """创建全局命令脚本"""

    # 创建命令脚本
    script_content = f'''#!/usr/bin/env python3
"""
全局 FastAPI 项目生成器命令
"""

import sys
import os
sys.path.insert(0, "{templates_dir / 'ms-scaffold'}")

from create_new_project import main

if __name__ == "__main__":
    main()
'''

    # 写入命令脚本
    command_script = templates_dir / 'fastapi-new'
    with open(command_script, 'w') as f:
        f.write(script_content)

    # 设置执行权限
    os.chmod(command_script, 0o755)

    # 创建 Windows 批处理文件
    bat_content = f'''@echo off
python "{command_script}" %*
'''

    bat_script = templates_dir / 'fastapi-new.bat'
    with open(bat_script, 'w') as f:
        f.write(bat_content)


def main():
    """主函数"""
    print("FastAPI 脚手架全局设置工具")
    print("=" * 40)

    success = setup_global_generator()

    if success:
        print("\n🎉 设置完成! 现在您可以在任何地方使用 fastapi-new 命令创建新项目了!")
    else:
        print("\n💥 设置失败，请检查权限和路径")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()