USE ai_agent;

-- 简历表：PDF 原件在 OSS 上的地址（未启用 OSS 时为 NULL）
ALTER TABLE ai_agent.resumes
    ADD COLUMN oss_url VARCHAR(500) NULL COMMENT '采购需求PDF的OSS地址' AFTER content_text;

-- JD 表：JD 原图在 OSS 上的地址（文本粘贴通道为 NULL）
ALTER TABLE ai_agent.jds
    ADD COLUMN oss_url VARCHAR(500) NULL COMMENT 'JD原图的OSS地址' AFTER content_text;