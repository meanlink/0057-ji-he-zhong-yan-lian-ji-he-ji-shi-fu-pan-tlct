CREATE TABLE IF NOT EXISTS muster_drills(
 code text PRIMARY KEY, title text NOT NULL, day date NOT NULL,
 cutoff integer NOT NULL CHECK(cutoff BETWEEN 10 AND 1800),
 status text NOT NULL DEFAULT 'open' CHECK(status IN('open','sealed','calculated'))
);
CREATE TABLE IF NOT EXISTS muster_members(
 drill text NOT NULL REFERENCES muster_drills(code), code text NOT NULL, group_name text NOT NULL,
 PRIMARY KEY (drill,code)
);
