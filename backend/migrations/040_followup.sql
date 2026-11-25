CREATE TABLE IF NOT EXISTS muster_followup(
 drill text NOT NULL, code text NOT NULL, owner text NOT NULL,
 action text NOT NULL CHECK(length(action)>=5),
 PRIMARY KEY(drill,code), FOREIGN KEY(drill,code) REFERENCES muster_clock(drill,code)
);
