CREATE TABLE IF NOT EXISTS muster_curves(
 drill text NOT NULL REFERENCES muster_drills(code), seconds int NOT NULL,
 at_risk integer NOT NULL CHECK(at_risk>0), arrivals int NOT NULL CHECK(arrivals>=0),
 censored int NOT NULL CHECK(censored>=0), remaining real NOT NULL CHECK(remaining BETWEEN 0 AND 1),
 PRIMARY KEY(drill,seconds), CHECK(arrivals+censored<=at_risk)
);
