-- New SQL Schema for Upgraded OI Tracking System
-- This schema includes candle close prices from getCandleData API

CREATE TABLE IF NOT EXISTS option_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    time DATETIME NOT NULL,                    -- 3-minute bucket timestamp (floor to 3min)
    index_name VARCHAR(20) NOT NULL,           -- NIFTY, BANKNIFTY
    expiry DATE NOT NULL,                      -- Option expiry date
    strike INT NOT NULL,                       -- Strike price
    
    -- Index candle data (from getCandleData)
    index_open DECIMAL(10,2),                  -- Index open price
    index_high DECIMAL(10,2),                  -- Index high price
    index_low DECIMAL(10,2),                   -- Index low price
    index_close DECIMAL(10,2) NOT NULL,        -- Index close price (candle close)
    index_volume BIGINT,                       -- Index volume
    
    -- CE (Call) Data
    ce_oi BIGINT DEFAULT 0,                    -- Open Interest
    ce_oi_change BIGINT DEFAULT 0,             -- OI change from previous snapshot
    ce_oi_percent_change DECIMAL(10,4) DEFAULT 0, -- OI % change
    ce_ltp DECIMAL(10,2) DEFAULT 0,            -- Last Traded Price
    ce_ltp_change DECIMAL(10,2) DEFAULT 0,     -- LTP change
    ce_ltp_percent_change DECIMAL(10,4) DEFAULT 0, -- LTP % change
    ce_volume BIGINT DEFAULT 0,                -- Volume
    ce_iv DECIMAL(10,4) DEFAULT 0,             -- Implied Volatility
    ce_delta DECIMAL(10,4) DEFAULT 0,          -- Delta
    ce_theta DECIMAL(10,4) DEFAULT 0,          -- Theta
    ce_vega DECIMAL(10,4) DEFAULT 0,           -- Vega
    ce_gamma DECIMAL(10,4) DEFAULT 0,          -- Gamma
    ce_vs_pe_oi_bar DECIMAL(10,4) DEFAULT 0,   -- CE vs PE OI ratio
    
    -- PE (Put) Data
    pe_oi BIGINT DEFAULT 0,                    -- Open Interest
    pe_oi_change BIGINT DEFAULT 0,             -- OI change
    pe_oi_percent_change DECIMAL(10,4) DEFAULT 0, -- OI % change
    pe_ltp DECIMAL(10,2) DEFAULT 0,            -- Last Traded Price
    pe_ltp_change DECIMAL(10,2) DEFAULT 0,     -- LTP change
    pe_ltp_percent_change DECIMAL(10,4) DEFAULT 0, -- LTP % change
    pe_volume BIGINT DEFAULT 0,                -- Volume
    pe_iv DECIMAL(10,4) DEFAULT 0,             -- Implied Volatility
    pe_delta DECIMAL(10,4) DEFAULT 0,          -- Delta
    pe_theta DECIMAL(10,4) DEFAULT 0,          -- Theta
    pe_vega DECIMAL(10,4) DEFAULT 0,           -- Vega
    pe_gamma DECIMAL(10,4) DEFAULT 0,          -- Gamma
    pe_vs_ce_oi_bar DECIMAL(10,4) DEFAULT 0,   -- PE vs CE OI ratio
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Unique constraint to ensure one snapshot per 3-minute bucket per strike
    UNIQUE KEY unique_snapshot (time, index_name, expiry, strike)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_time ON option_snapshots(time);
CREATE INDEX IF NOT EXISTS idx_index_strike ON option_snapshots(index_name, strike);
CREATE INDEX IF NOT EXISTS idx_expiry ON option_snapshots(expiry);
CREATE INDEX IF NOT EXISTS idx_created_at ON option_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_time_index ON option_snapshots(time, index_name); 