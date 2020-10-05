# Notes

```sql
SELECT count(distinct status_id) as status_count
FROM election_2020_production.tweets -- 13,158,284
--WHERE retweeted_status_id is null -- 2,739,090
-- WHERE retweeted_status_id is not null -- 10,419,194
```

```sql
SELECT
     user_id
     -- ,user_name
     ,user_screen_name
     ,status_id
     ,status_text
     ,created_at
    ,retweeted_status_id
    ,retweeted_user_id
    ,retweeted_user_screen_name
FROM election_2020_analysis.tweets
WHERE retweeted_status_id is not null
  AND extract(DATE from created_at) in ('2020-09-29', '2020-09-30', '2020-10-01') -- first debate (618 two days, 23,203 three days)
-- LIMIT 10

```
