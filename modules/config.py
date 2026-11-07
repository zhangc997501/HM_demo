"""
配置文件
项目相关的配置信息
"""

# ==== 库文件 =======================
# Python 标准库
import os
# 环境变量加载库
from dotenv import load_dotenv
# OpenAI 库
from openai import OpenAI

# env文件路径
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
print(BASE_DIR)
# 加载环境变量
load_dotenv(os.path.join(BASE_DIR, '.env'))

# =================== 模型配置信息
# getenv 方法获取环境变量，如果不存在则返回空字符串
# 参数1：环境变量名称
# 参数2：环境变量不存在时的默认值
API_KEY = os.getenv('API_KEY', '') # 模型密钥
BASE_URL = os.getenv('BASE_URL', '') # 模型基础URL
TEXT_MODEL = os.getenv('TEXT_MODEL', '') # 文本模型名称
VL_MODEL = os.getenv('VL_MODEL', '') # VL模型名称

# 用 OpenAI 官方 SDK 连接阿里云百炼（OpenAI 兼容协议）：
# SDK 不关心对面是谁，只认 base_url + api_key，这就是"兼容协议"的好处
client = OpenAI(api_key=API_KEY or "not-configured", base_url=BASE_URL)


# =================== JWT 配置信息
"""
JWT 是一种开放标准 (RFC 7519)，
用于在网络应用环境间安全地将信息作为 JSON 对象传输。
密钥来自于环境变量 JWT_SECRET
"""
JWT_SECRET = os.getenv('JWT_SECRET', '') # JWT 密钥
JWT_EXPIRE_HOURS = int(os.getenv('JWT_EXPIRE_HOURS', '')) # JWT 过期时间（小时）

# ==================== Mysql 配置信息
MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1') # Mysql 主机
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306)) # Mysql 端口
MYSQL_USER = os.getenv('MYSQL_USER', 'root') # Mysql 用户
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '') # Mysql 密码
MYSQL_DB = os.getenv('MYSQL_DB', '') # Mysql 数据库

# ==================== Redis 配置信息
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1') # Redis 主机
REDIS_PORT = int(os.getenv('REDIS_PORT', "6379")) # Redis 端口
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '') # Redis 密码
REDIS_DB = int(os.getenv('REDIS_DB', '0')) # Redis 数据库

# ==================== 业务配置
MAX_INTERVIEW_ROUNDS = int(os.getenv("MAX_INTERVIEW_ROUNDS", "20")) #最大轮次


# ############################# 阿里云 OSS 配置 #############################
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com")
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME", "")
OSS_PUBLIC_BASE_URL = os.getenv("OSS_PUBLIC_BASE_URL", "")
OSS_ENABLED = bool(OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET and OSS_BUCKET_NAME)