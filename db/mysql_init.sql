
# 创建数据库
# utf8mb4_unicode_ci 是一种字符集排序规则
CREATE DATABASE IF NOT EXISTS agent_project DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE agent_project;


-- 用户表：密码 SHA256 哈希后存储，不存明文
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(64)  NOT NULL COMMENT 'SHA256 哈希值（64 位十六进制字符串）',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
) ENGINE=InnoDB COMMENT='用户表';

-- 需求表：第 1 步存解析全文，第 2 步存模型总结
CREATE TABLE IF NOT EXISTS resumes (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT          NOT NULL COMMENT '所属用户',
    filename      VARCHAR(255) NOT NULL COMMENT '原始文件名',
    content_text  MEDIUMTEXT   NOT NULL COMMENT '第 1 步：PyMuPDF 提取的简历全文',
    summary_json  MEDIUMTEXT   NULL COMMENT '第 2 步：模型总结的 JSON（评分/评语/建议）',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    KEY idx_user (user_id),
    CONSTRAINT fk_resumes_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB COMMENT='采购需求表';

-- 图标（JD）表：
CREATE TABLE IF NOT EXISTS jds (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT  NOT NULL COMMENT '所属用户',
    source       VARCHAR(20) NOT NULL DEFAULT 'text' COMMENT '来源：text=粘贴 / image=图片识别',
    content_text TEXT NOT NULL COMMENT 'JD 全文',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '保存时间',
    KEY idx_user (user_id),
    CONSTRAINT fk_jds_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB COMMENT='签字审批表';

-- 展示所有的表
show tables;