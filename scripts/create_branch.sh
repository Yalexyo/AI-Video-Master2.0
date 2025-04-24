#!/bin/bash

# 创建分支的脚本
# 用法: ./create_branch.sh [类型] [名称]
# 例如: ./create_branch.sh debug api-error

# 确保当前目录是Git仓库
if [ ! -d ".git" ]; then
    echo "错误: 当前目录不是Git仓库"
    exit 1
fi

# 检查参数数量
if [ $# -lt 2 ]; then
    echo "用法: $0 [类型] [名称]"
    echo "类型选项:"
    echo "  1 或 debug - Bug修复分支 (debug/名称)"
    echo "  2 或 ui    - UI优化分支 (ui/名称)"
    echo "  3 或 new   - 新功能分支 (feature/名称)"
    exit 1
fi

# 解析参数
TYPE=$1
NAME=$2
BRANCH_NAME=""

# 判断分支类型并设置对应的分支名
case $TYPE in
    1|debug)
        BRANCH_NAME="debug/$NAME"
        TYPE_DESC="Bug修复"
        ;;
    2|ui)
        BRANCH_NAME="ui/$NAME"
        TYPE_DESC="UI优化"
        ;;
    3|new)
        BRANCH_NAME="feature/$NAME"
        TYPE_DESC="新功能"
        ;;
    *)
        echo "错误: 无效的分支类型"
        echo "类型选项:"
        echo "  1 或 debug - Bug修复分支 (debug/名称)"
        echo "  2 或 ui    - UI优化分支 (ui/名称)"
        echo "  3 或 new   - 新功能分支 (feature/名称)"
        exit 1
        ;;
esac

# 确认当前是否位于main分支
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    read -p "警告: 您当前不在main分支上。是否继续创建分支? (y/n): " CONFIRM
    if [ "$CONFIRM" != "y" ]; then
        echo "操作已取消"
        exit 0
    fi
fi

# 创建新分支
echo "正在创建${TYPE_DESC}分支: $BRANCH_NAME"
git checkout -b $BRANCH_NAME

# 如果创建成功，提示是否推送到远程
if [ $? -eq 0 ]; then
    echo "分支 $BRANCH_NAME 创建成功!"
    read -p "是否推送到远程仓库? (y/n): " PUSH_CONFIRM
    if [ "$PUSH_CONFIRM" = "y" ]; then
        git push -u origin $BRANCH_NAME
    fi
else
    echo "分支创建失败，请检查是否存在同名分支或其他问题。"
fi 