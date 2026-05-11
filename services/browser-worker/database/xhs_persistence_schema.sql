CREATE TABLE IF NOT EXISTS xhs_search_evidence (
  id bigserial PRIMARY KEY,
  job_id text NOT NULL,
  account_id text NOT NULL,
  keyword text,
  provider_type text,
  status text,
  evidence_json_path text,
  screenshot_path text,
  item_count integer,
  normalized_record_count integer,
  strict_binding_status text,
  hardened_discovery_status text,
  source_replay_status text,
  raw_payload jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xhs_search_evidence_job_id ON xhs_search_evidence(job_id);
CREATE INDEX IF NOT EXISTS idx_xhs_search_evidence_account_id ON xhs_search_evidence(account_id);
CREATE INDEX IF NOT EXISTS idx_xhs_search_evidence_keyword ON xhs_search_evidence(keyword);
CREATE INDEX IF NOT EXISTS idx_xhs_search_evidence_created_at ON xhs_search_evidence(created_at);

CREATE TABLE IF NOT EXISTS xhs_search_records (
  id bigserial PRIMARY KEY,
  job_id text NOT NULL,
  account_id text NOT NULL,
  keyword text,
  rank integer,
  title text,
  author text,
  published_at_text text,
  note_id text,
  note_url text,
  metric_raw_text text,
  like_count_text text,
  evidence_json_path text,
  screenshot_path text,
  raw_record jsonb,
  captured_at timestamptz,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xhs_search_records_job_id ON xhs_search_records(job_id);
CREATE INDEX IF NOT EXISTS idx_xhs_search_records_account_id ON xhs_search_records(account_id);
CREATE INDEX IF NOT EXISTS idx_xhs_search_records_keyword ON xhs_search_records(keyword);
CREATE INDEX IF NOT EXISTS idx_xhs_search_records_created_at ON xhs_search_records(created_at);

CREATE TABLE IF NOT EXISTS xhs_publish_evidence (
  id bigserial PRIMARY KEY,
  job_id text NOT NULL,
  account_id text NOT NULL,
  title text,
  publish_mode text,
  status text,
  note_url text,
  evidence_json_path text,
  screenshot_paths jsonb,
  image_paths jsonb,
  strict_binding_status text,
  hardened_discovery_status text,
  source_replay_status text,
  raw_payload jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xhs_publish_evidence_job_id ON xhs_publish_evidence(job_id);
CREATE INDEX IF NOT EXISTS idx_xhs_publish_evidence_account_id ON xhs_publish_evidence(account_id);
CREATE INDEX IF NOT EXISTS idx_xhs_publish_evidence_created_at ON xhs_publish_evidence(created_at);

CREATE TABLE IF NOT EXISTS xhs_publish_jobs (
  id bigserial PRIMARY KEY,
  job_id text NOT NULL UNIQUE,
  account_id text NOT NULL,
  title text,
  body text,
  tags jsonb,
  image_paths jsonb,
  publish_mode text,
  status text,
  note_url text,
  error_code text,
  error_message text,
  raw_payload jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xhs_publish_jobs_job_id ON xhs_publish_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_xhs_publish_jobs_account_id ON xhs_publish_jobs(account_id);
CREATE INDEX IF NOT EXISTS idx_xhs_publish_jobs_created_at ON xhs_publish_jobs(created_at);

CREATE TABLE IF NOT EXISTS xhs_task_log (
  id bigserial PRIMARY KEY,
  job_id text NOT NULL,
  job_type text NOT NULL,
  account_id text,
  status text,
  source text,
  payload_path text,
  result_path text,
  raw_payload jsonb,
  error_code text,
  error_message text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xhs_task_log_job_id ON xhs_task_log(job_id);
CREATE INDEX IF NOT EXISTS idx_xhs_task_log_account_id ON xhs_task_log(account_id);
CREATE INDEX IF NOT EXISTS idx_xhs_task_log_created_at ON xhs_task_log(created_at);

CREATE TABLE IF NOT EXISTS xhs_workflow_log (
  id bigserial PRIMARY KEY,
  run_id text,
  job_id text,
  workflow_name text NOT NULL,
  status text NOT NULL,
  input_json jsonb,
  output_json jsonb,
  error_code text,
  error_message text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xhs_workflow_log_run_id ON xhs_workflow_log(run_id);
CREATE INDEX IF NOT EXISTS idx_xhs_workflow_log_job_id ON xhs_workflow_log(job_id);
CREATE INDEX IF NOT EXISTS idx_xhs_workflow_log_created_at ON xhs_workflow_log(created_at);
