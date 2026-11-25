CREATE TABLE IF NOT EXISTS muster_clock(
 drill text NOT NULL, code text NOT NULL, seconds int NOT NULL CHECK(seconds>0),
 kind text NOT NULL CHECK(kind IN('arrived','censored')),
 PRIMARY KEY(drill,code), FOREIGN KEY(drill,code) REFERENCES muster_members(drill,code)
);
