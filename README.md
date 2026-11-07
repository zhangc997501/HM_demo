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
Audioresources/         运行时生成的音频（已在 .gitignore 中忽略）
```

## 快速开始

```powershell
pip install fastapi uvicorn python-dotenv openai dashscope numpy sounddevice
Copy-Item .env.example .env      # 然后填入 API_KEY、JWT_SECRET、数据库密码等
python main.py                   # http://127.0.0.1:8989/docs
```

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/voice/ping` | 设备上电自检，返回服务器时间与最大音频字节数 |
| POST | `/api/voice/chat` | multipart 上传完整 wav（浏览器 / 上位机） |
| POST | `/api/voice/raw` | body 直接放裸 PCM（16bit 小端单声道），参数走 query：`device_sn`、`session_id`、`sample_rate` |

响应统一为 `{code, session_id, user_text, reply, audio, elapsed_ms}`，`code=0` 表示成功。
多轮对话靠回传同一个 `session_id`，历史保存在进程内 `SESSIONS` 字典（重启即丢，未接 Redis）。

## 约定

- **不要把 `.env` 提交到仓库**，它已被 `.gitignore` 忽略；新增配置项请同步更新 `.env.example`。
- 音频、日志、`.idea/`、`__pycache__/` 均不纳入版本管理。
