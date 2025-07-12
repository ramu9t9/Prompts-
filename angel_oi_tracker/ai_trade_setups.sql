-- AI Trade Setups Table Schema
-- Integrates with existing options_analytics database

CREATE TABLE IF NOT EXISTS ai_trade_setups (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    bucket_ts TIMESTAMP NOT NULL,
    index_name VARCHAR(20) NOT NULL,
    
    -- AI Analysis Results
    bias VARCHAR(20) NOT NULL,  -- BULLISH/BEARISH/NEUTRAL
    strategy TEXT NOT NULL,
    entry_strike INT NOT NULL,
    entry_type VARCHAR(5) NOT NULL,  -- CE/PE
    entry_price DECIMAL(10,2) NOT NULL,
    stop_loss DECIMAL(10,2) NOT NULL,
    target DECIMAL(10,2) NOT NULL,
    confidence INT NOT NULL,  -- 0-100
    rationale TEXT NOT NULL,
    
    -- AI Model Information
    model_used VARCHAR(50) NOT NULL,
    response_raw JSON,
    
    -- Market Context (for analysis)
    spot_ltp DECIMAL(10,2),
    pcr_oi DECIMAL(8,4),
    pcr_volume DECIMAL(8,4),
    vwap DECIMAL(10,2),
    cpr_top DECIMAL(10,2),
    cpr_bottom DECIMAL(10,2),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    INDEX idx_bucket_index (bucket_ts, index_name),
    INDEX idx_bias_confidence (bias, confidence DESC),
    INDEX idx_entry_strike (entry_strike),
    INDEX idx_model_used (model_used),
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci; 