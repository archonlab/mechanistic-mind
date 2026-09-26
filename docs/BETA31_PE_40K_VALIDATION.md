# Beta 3.1 PE 40k validation (canonical cold eviction)

Actual seed 575 run after production gates. Canonical Beta 3.1 config. Not extrapolated.

| Tick | RSS MB | RssAnon MB | RssFile MB | Archive GB |
| --- | --- | --- | --- | --- |
| 0 | 44.035 | 24.449 | 19.586 | 0 |
| 10000 | 616.387 | 596.352 | 20.035 | 1.863 |
| 20000 | 637.215 | 617.180 | 20.035 | 3.750 |
| 30000 | 645.480 | 625.445 | 20.035 | 5.617 |
| 40000 | 644.590 | 624.555 | 20.035 | 7.498 |

TPS 6.319. OOM: no.

OLD_40K_RSS_MB = 18200  
NEW_40K_RSS_MB = 644.59  
40K_RSS_REDUCTION_PERCENT = 96.46  
FORTY_K_COMPLETED_WITHOUT_OOM = YES
