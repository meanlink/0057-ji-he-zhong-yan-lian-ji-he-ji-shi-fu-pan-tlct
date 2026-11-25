CREATE TABLE IF NOT EXISTS muster_corrections(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 drill text NOT NULL REFERENCES muster_drills(code),
 owner text NOT NULL,
 reason text NOT NULL CHECK(length(reason)>=5),
 observations jsonb NOT NULL,
 baseline jsonb NOT NULL,
 status text NOT NULL DEFAULT 'queued'
   CHECK(status IN('queued','running','effective','failed','returned')),
 detail text,
 job_id bigint NOT NULL REFERENCES app_jobs(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
-- 同一演练同时只允许一张在途更正单；生效或退回后可再发起。
CREATE UNIQUE INDEX IF NOT EXISTS muster_corrections_in_flight
  ON muster_corrections(drill) WHERE status IN('queued','running');
