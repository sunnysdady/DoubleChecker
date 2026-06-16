#!/usr/bin/env bash
# push_to_github.sh — 首次把本项目推送到 GitHub
# 用法: bash push_to_github.sh [仓库URL]
#   默认 https://github.com/sunnysdady/DoubleChecker.git
# 认证: 运行时 git 会要 用户名 + 密码；密码处粘贴你的 Personal Access Token(PAT)。
set -e
REPO="${1:-https://github.com/sunnysdady/DoubleChecker.git}"
cd "$(cd "$(dirname "$0")" && pwd)"

command -v git >/dev/null 2>&1 || { echo "未装 git：sudo apt-get install -y git"; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init
# 没设过身份就给个默认，避免 commit 失败
git config user.email >/dev/null 2>&1 || git config user.email "sunnysdady@gmail.com"
git config user.name  >/dev/null 2>&1 || git config user.name  "sunnysdady"
git add -A
git commit -m "DoubleChecker: OCR 校对预处理工具" || echo "（无改动可提交）"
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO"
echo "▶ 推送到 $REPO  （用户名: 你的 GitHub 用户名；密码: 粘贴 PAT）"
git push -u origin main
echo "✅ 已推送。仓库已有内容报错时，先： git pull --rebase origin main  再重推。"
