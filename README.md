# Agent Projecr — 智面 Agent 语音对话服务

基于 FastAPI 的语音对话后端：设备（ESP32-S3）或浏览器上传音频 → 阿里云 DashScope 语音识别（ASR）→
通义千问大模型生成回复 → JSON 返回给设备显示。

## 目录结构

```
main.py                 FastAPI 入口，注册语音路由，默认 0.0.0.0:8989
modules/
  config.py             读取 .env，暴露模型 / JWT / MySQL / Redis / OSS 配置
  voice_api.py          语音接口：/api/voice/ping、/chat、/raw，PCM→WAV、ASR→LLM 编排
  asr.py                DashScope 语音识别封装
  recording.py          sounddevice 本地录音（16kHz / 单声道 / int16）
  LLM.py                单轮文本大模型调用示例
db/
  mysql_init.sql        数据库初始化脚本
  oss_url.sql           OSS 相关表结构 / 字段调整
scripts/
  push.ps1              推送脚本：临时把 Clash 切全局模式 → push → 还原 mode
requirements.txt        依赖清单（要求 Python >= 3.10）
CONTRIBUTING.md         协作开发指南：邀请协作者、分支与 PR、密钥纪律
Audioresources/         运行时生成的音频（已在 .gitignore 中忽略）
```

## 快速开始

需要 **Python >= 3.10**（代码使用了 `str | None` 等 3.10+ 注解语法）。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env      # 然后填入 API_KEY、JWT_SECRET、数据库密码等

mysql -u root -p < db\mysql_init.sql
mysql -u root -p < db\oss_url.sql

python main.py                   # http://127.0.0.1:8989/docs
```

多人协作（邀请协作者、分支与 PR 流程、密钥纪律）见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/voice/ping` | 设备上电自检，返回服务器时间与最大音频字节数 |
| POST | `/api/voice/chat` | multipart 上传完整 wav（浏览器 / 上位机） |
| POST | `/api/voice/raw` | body 直接放裸 PCM（16bit 小端单声道），参数走 query：`device_sn`、`session_id`、`sample_rate` |

响应统一为 `{code, session_id, user_text, reply, audio, elapsed_ms}`，`code=0` 表示成功。
多轮对话靠回传同一个 `session_id`，历史保存在进程内 `SESSIONS` 字典（重启即丢，未接 Redis）。

## 提交与推送

本机 Clash 处于「规则模式」时，github.com 会被判定为直连，`git push` 直接失败：

```
fatal: unable to access 'https://github.com/zhangc997501/HM_demo.git/':
Recv failure: Connection was reset
```

用仓库自带的脚本推送即可（临时把 Clash 切到全局模式，推完自动还原）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\push.ps1
```

脚本会从 Windows 系统代理读取 Clash 的 http 端口，探测控制器（`127.0.0.1:33212`，备选 9090/9091/9097/6170），
读当前 mode → 切 global → `git push -u origin main` → 无论成败都改回原 mode。
如果哪天在 Clash 里给 github.com 配了「走代理」的规则，就可以直接 `git push`，脚本也不会再改 mode。

## 约定

- **不要把 `.env` 提交到仓库**，它已被 `.gitignore` 忽略；新增配置项请同步更新 `.env.example`。
- 音频、日志、`.idea/`、`__pycache__/` 均不纳入版本管理。
- 分支：`main` 为主干，功能开发走 `feat/xxx` 分支，改完再合回 `main`。
- 提交信息：`<type>(<scope>): <中文摘要>`，type 取 `feat` / `fix` / `docs` / `refactor` / `chore`，
  scope 如 `voice`、`db`、`config`。一行摘要说清"做了什么"，正文用 `-` 列表说明"为什么 / 影响面"。
