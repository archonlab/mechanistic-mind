# Nested PE history representation (no payload pool)

Content-addressed sharing of forgotten member maps was evaluated and **rejected**: at t1000 every nested forgotten class has a unique packed payload.

Implemented (forgotten-only, lossless):

- `_pack_keys` stored as the interned tuple (JSON still lists)
- class-level `mean_c` packed onto that schema when a class is forgotten

Not implemented:

- shared member payload IDs
- lag views onto a canonical record
- struct-of-arrays archive
- any cap or merge

Cognition/TPS/TPE/lag identity unchanged. Old Hybrid G snapshots still compact on load.
