CREATE TABLE IF NOT EXISTS companies (
  company_id VARCHAR(32) PRIMARY KEY, name VARCHAR(255) NOT NULL, sector VARCHAR(255),
  reporting_currency VARCHAR(16) NOT NULL, fiscal_year_note VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS filings (
  filing_id VARCHAR(96) PRIMARY KEY, company_id VARCHAR(32) NOT NULL,
  form_type VARCHAR(32), fiscal_year INT, fiscal_quarter INT, period_end VARCHAR(20),
  filed_date VARCHAR(20), doc_id VARCHAR(128), reporting_unit VARCHAR(32), is_amendment TINYINT NOT NULL DEFAULT 0,
  CONSTRAINT fk_filings_company FOREIGN KEY (company_id) REFERENCES companies(company_id),
  INDEX idx_filings_period (company_id,fiscal_year,fiscal_quarter,filed_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS statement_lines (
  row_id VARCHAR(96) PRIMARY KEY, company_id VARCHAR(32) NOT NULL, filing_id VARCHAR(96) NOT NULL,
  statement VARCHAR(64) NOT NULL, line_item_raw VARCHAR(255) NOT NULL, canonical_item VARCHAR(96),
  fiscal_year INT NOT NULL, fiscal_quarter INT NOT NULL, period_start VARCHAR(20), period_end VARCHAR(20),
  raw_value DOUBLE NOT NULL, raw_unit VARCHAR(32) NOT NULL, currency VARCHAR(16), value_usd DOUBLE,
  source_status VARCHAR(32) NOT NULL DEFAULT 'unreviewed',
  CONSTRAINT fk_lines_company FOREIGN KEY (company_id) REFERENCES companies(company_id),
  CONSTRAINT fk_lines_filing FOREIGN KEY (filing_id) REFERENCES filings(filing_id),
  INDEX idx_lines_period (company_id,fiscal_year,fiscal_quarter),
  INDEX idx_lines_canonical (company_id,canonical_item,fiscal_year,fiscal_quarter)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS kpi_definitions (
  kpi_id VARCHAR(96) PRIMARY KEY, kpi_name VARCHAR(255) NOT NULL, formula TEXT NOT NULL, unit VARCHAR(32) NOT NULL, notes TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS kpi_values (
  id BIGINT PRIMARY KEY AUTO_INCREMENT, company_id VARCHAR(32) NOT NULL,
  fiscal_year INT NOT NULL, fiscal_quarter INT NOT NULL, kpi_id VARCHAR(96) NOT NULL,
  value DOUBLE, status VARCHAR(32) NOT NULL, confidence VARCHAR(16) NOT NULL, confidence_basis TEXT NOT NULL,
  source_row_ids TEXT NOT NULL, calculation_version VARCHAR(64) NOT NULL,
  CONSTRAINT fk_kpi_company FOREIGN KEY (company_id) REFERENCES companies(company_id),
  CONSTRAINT fk_kpi_definition FOREIGN KEY (kpi_id) REFERENCES kpi_definitions(kpi_id),
  UNIQUE KEY uq_kpi_version (company_id,fiscal_year,fiscal_quarter,kpi_id,calculation_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS document_chunks (
  chunk_id VARCHAR(255) PRIMARY KEY, doc_id VARCHAR(128) NOT NULL, company_id VARCHAR(32) NOT NULL,
  filing_id VARCHAR(128), chunk_index INT NOT NULL, text LONGTEXT NOT NULL, content_hash CHAR(64) NOT NULL,
  CONSTRAINT fk_chunks_company FOREIGN KEY (company_id) REFERENCES companies(company_id),
  UNIQUE KEY uq_doc_chunk_hash (doc_id,chunk_index,content_hash),
  INDEX idx_chunks_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS chat_sessions (
  session_id VARCHAR(128) PRIMARY KEY, tenant_id VARCHAR(128) NOT NULL, created_at VARCHAR(40) NOT NULL,
  metadata_json JSON NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS request_metrics (
  request_id VARCHAR(128) PRIMARY KEY, tenant_id VARCHAR(128) NOT NULL, session_id VARCHAR(128), model_version VARCHAR(128),
  prompt_hash VARCHAR(128), retrieval_snapshot VARCHAR(255), ttft_ms DOUBLE, tokens_per_second DOUBLE,
  cache_hit TINYINT, queue_depth INT, error_code VARCHAR(128), created_at VARCHAR(40) NOT NULL,
  INDEX idx_metrics_tenant_time (tenant_id,created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
