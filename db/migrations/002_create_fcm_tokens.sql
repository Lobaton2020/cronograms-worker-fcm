-- 002_create_fcm_tokens.sql
-- Stores FCM device tokens per user.
-- Requires the `Usuario` table (already exists in `tomanotas`).

CREATE TABLE fcm_tokens (
    id_fcm_token_PK INT NOT NULL AUTO_INCREMENT,
    id_usuario_FK   INT NOT NULL,
    token           VARCHAR(500) NOT NULL,
    platform        VARCHAR(20)  NOT NULL DEFAULT 'android',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id_fcm_token_PK),
    INDEX idx_fcm_tokens_user (id_usuario_FK),
    UNIQUE KEY uniq_fcm_token (token)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
