---
name: git-use
description: 连接本地项目与 GitHub 仓库并上传（push）的完整流程，包括 HTTPS 令牌认证、克隆/初始化后推送、.gitignore 与敏感信息检查，以及本机常见故障（schannel 报错、代理、凭据管理器卡住、dubious ownership）。触发词：「git」「github」「上传」「push」「clone」「推送到 GitHub」。
---

# Git Use

把本地文件上传到 GitHub，或把 GitHub 仓库克隆/关联到本地。默认用 HTTPS + Personal Access Token（PAT）认证，SSH 仅作备选。

## 上传前先确认

- `git --version` 可用，且已配置 `user.name`、`user.email`。
- 扫一遍要上传的内容，确认没有令牌（`ghp_`、`github_pat_`）、`.env`、密钥或真实个人信息。公开仓库任何人可见。
- 用 `.gitignore` 排除 `.venv/`、`__pycache__/`、`*.pyc`、`node_modules/`、`.env` 等，避免把虚拟环境和依赖传上去。

## 凭证

- GitHub 从 2021 年起不接受账号密码推送，要用 Personal Access Token：Settings → Developer settings → Personal access tokens → Tokens (classic)，勾选 `repo` 权限生成。
- 令牌只完整显示一次，不要写进代码或聊天记录。用 `git config --global credential.helper manager` 让系统缓存。
- 临时推送可把令牌放在一次性 URL 里，不写进 remote 配置：

```
git push https://用户名:令牌@github.com/用户名/仓库.git main
```

## 场景 A：克隆已有仓库

```
git clone https://github.com/用户名/仓库.git
cd 仓库
```

## 场景 B：把本地项目上传到新仓库

先在 GitHub 网页新建空仓库（建议不要勾选生成 README，避免首次推送冲突），然后：

```
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/用户名/仓库.git
git push -u origin main
```

## 日常同步

```
git pull
git add .
git commit -m "说明"
git push
```

## 本机技能库同步工作流（han-skills）

本机技能库就一份：`C:\Users\admin\.agents\skills`，已直接连接 GitHub（remote 为 origin）。

```powershell
# 改完技能文件后，提交并推送
cd C:\Users\admin\.agents\skills
git add -A
git commit -m "说明"
git push

# 换电脑或需要回退时，从 GitHub 拉取
git pull
```

要点：

- `hanjinhong-profile/` 已写入 `.gitignore`，保持本地私有、不上传。
- 每次推送后，在仓库 README 的「更新日志」追加一条记录。
- 推送时若凭据管理器弹窗卡住，参考下文「推送卡住」的绕过方式。

## 本机常见故障（实测）

1. **schannel 报错**：Windows 上 git/curl 报 `SEC_E_NO_CREDENTIALS` 时，改用 OpenSSL：`git config --global http.sslBackend openssl`。
2. **代理**：本机代理为 `http://127.0.0.1:7897`；走代理访问 GitHub 时同样优先用 OpenSSL 后端。
3. **推送卡住**：后台出现 `git-credential-helper-selector` 进程且无输出，是凭据管理器弹窗在等待输入。绕过方式：`git -c credential.helper= -c http.version=HTTP/1.1 push ...`，并设 `GIT_TERMINAL_PROMPT=0`。
4. **dubious ownership**：跨账户（如沙盒）操作他人目录下的仓库时报错，用 `git config --global --add safe.directory <路径>`，或单次执行加 `-c safe.directory=<路径>`。
5. **公开仓库下载不需要令牌**，只有 push（写操作）才需要认证。

## 安全底线

- 推送前检查敏感串与个人信息；学号、邮箱、密钥等需用户明确同意后再上传。
- 用过即弃的令牌建议在推送完成后吊销并重新生成。
