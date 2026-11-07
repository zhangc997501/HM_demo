# 协作开发指南

面向「我想把这个项目分享给别人一起开发」的场景。仓库地址：
`https://github.com/zhangc997501/HM_demo`

## 1. 先把仓库分享出去

目前仓库是 **私有** 的（匿名访问返回 404），别人拿到链接也打不开，必须先授权。两条路：

**A. 私有仓库 + 邀请协作者（推荐，代码不外泄）**

1. 仓库页 → **Settings** → 左侧 **Collaborators** → **Add people**
2. 输入对方的 GitHub 用户名或注册邮箱，发送邀请
3. 对方在邮件 / GitHub 通知里 **Accept invitation** 后即可 clone、推分支、提 PR

> GitHub 免费套餐的私有仓库最多 3 个协作者。人多的话：升级套餐，或建一个 Organization、或把仓库改公开。

**B. 改成公开仓库（谁都能看、能 fork）**

仓库页 → **Settings** → 拉到底 **Danger Zone** → **Change repository visibility** → **Change to public**，
按提示输入仓库名确认。公开前务必确认 `.env`、密钥、录好的音频都没进仓库。

## 2. 新成员本地跑起来

```powershell
git clone https://github.com/zhangc997501/HM_demo.git
cd HM_demo

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # 需要 Python >= 3.10

Copy-Item .env.example .env              # 真实密钥找项目负责人单独发，不要走聊天记录/PR

mysql -u root -p < db\mysql_init.sql     # 建库建表
mysql -u root -p < db\oss_url.sql        # 加 oss_url 字段

python main.py                           # http://127.0.0.1:8989/docs
```

跑通标准：`GET /api/voice/ping` 返回 `{"ok": true, ...}`。

## 3. 分支与提交

- `main` 始终保持可运行，**不要在 main 上直接改**
- 每个需求/修复开一个分支：`feat/interview-rounds`、`fix/asr-timeout`
- 提交信息：`<type>(<scope>): <中文摘要>`，type 取 `feat` / `fix` / `docs` / `refactor` / `chore`
- 一个提交只做一件事；正文用 `-` 说明**为什么**改，而不是复述代码

```powershell
git switch -c feat/interview-rounds
# ...改代码...
git add -A
git commit -m "feat(voice): 支持按 session_id 查询历史轮次"
git push -u origin feat/interview-rounds
```

## 4. Pull Request 流程

1. 推完分支后，GitHub 页面会出现 **Compare & pull request**
2. 标题写清改了什么；描述里写：动机、影响范围、怎么验证（贴 `/docs` 或 curl 的返回）
3. 至少一个人 review 通过再合并；合并用 **Squash and merge**，保持 main 历史线性
4. 合并后删掉远端分支，本地 `git switch main && git pull`

如果 GitHub 套餐支持，可以在 **Settings → Branches** 给 `main` 加保护规则：
要求 PR + 至少 1 个 approval + 禁止 force push。私有仓库在免费套餐下该功能受限，
那就靠上面这些约定，别直接推 main。

## 5. 密钥与配置纪律

- 仓库里只提交 `.env.example`，**永远不提交 `.env`**（已在 `.gitignore` 中）
- 新增配置项的固定动作：`config.py` 加 `os.getenv(...)` + `.env.example` 加同名空值 + 通知其他人补自己的 `.env`
- 万一密钥被误提交：**先去百度云/阿里云控制台作废并重置这个 key**，历史清理（`git filter-repo`）会改写所有人的提交历史，必须先协商再动

## 6. 网络问题（国内协作的实际情况）

GitHub 直连在国内不稳定，双方都需要代理；本项目还遇到了「Clash 规则模式把 github.com 判成直连导致推送被重置」的问题，
仓库里的 `scripts\push.ps1` 就是为此写的（详细说明见 README 的「提交与推送」）。

想彻底省事的另一个办法是加一个 Gitee 镜像，每次推两份：

```powershell
git remote add gitee https://gitee.com/<你的账号>/HM_demo.git
git push origin main
git push gitee main
```

## 7. 多人协作时的现状提醒

- 会话历史存在进程内的 `SESSIONS` 字典里（`modules/voice_api.py`），**重启即丢、也无法多机共享**，
  两个人本地各跑一份不会互相干扰，但演示时不要指望"换台机器能接着聊"
- 数据库名目前三处不一致：`.env` 的 `MYSQL_DB=ai_interview`、`db/mysql_init.sql` 建 `agent_project`、
  `db/oss_url.sql` 里 `USE ai_agent`。让新人踩这个坑不合适，接手前先统一
- `Audioresources/` 是运行时产物，不进仓库；每台机器各自生成即可
