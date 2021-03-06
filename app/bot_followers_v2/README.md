# Bot Followers v2

For the bots, how many (active) followers does each have, and who are they?

## User Followers Flat - v2


```sql
DROP TABLE IF EXISTS impeachment_production.user_followers_flat_v2;
CREATE TABLE impeachment_production.user_followers_flat_v2 as (
  SELECT
    cast(sn.user_id as int64) as user_id
    ,sn.screen_name
    ,cast(uff.user_id as int64) as follower_id
    ,uff.screen_name as follower_name
  FROM impeachment_production.user_screen_names sn
  JOIN impeachment_production.user_friends_flat uff ON upper(sn.screen_name) = upper(uff.friend_name)
  --WHERE sn.screen_name = "ACLU"
  --LIMIT 100
)
```

```sql
DROP TABLE IF EXISTS impeachment_production.active_followers_flat_v2;
CREATE TABLE impeachment_production.active_followers_flat_v2 as (
  SELECT
    cast(sn.user_id as int64) as user_id
    ,sn.screen_name
    ,cast(auff.user_id as int64) as follower_id
    ,auff.screen_name as follower_name
  FROM impeachment_production.user_screen_names sn
  JOIN impeachment_production.active_user_friends_flat auff ON upper(sn.screen_name) = upper(auff.friend_name)
  --WHERE sn.screen_name = "ACLU"
  --LIMIT 100
)
```


```sql
-- FOLLOWERS
SELECT
  count(distinct user_id) as user_count -- 2,987,137
  ,count(distinct follower_id) as follower_count -- 3,315,115
FROM impeachment_production.user_followers_flat_v2
```

```sql
-- ACTIVE FOLLOWERS
SELECT
  count(distinct user_id) as user_count -- 2,971,946
  ,count(distinct follower_id) as follower_count -- 3,310,307
FROM impeachment_production.active_followers_flat_v2
```


```sql
SELECT
  count(distinct uf.user_id) as user_count -- 22,814
  , count(distinct uf.follower_id) as follower_count -- 886,275
FROM impeachment_production.user_followers_flat_v2 uf
JOIN impeachment_production.user_details_v4 bu on bu.user_id = uf.user_id
WHERE bu.is_bot = true

```

```sql
SELECT
  count(distinct bu.user_id) as user_count -- 24,150
FROM impeachment_production.user_details_v4 bu
WHERE bu.is_bot = true
```

OK so about 1300 bots have no followers. that makes sense. For the remaining bots, how many followers on average?

```sql
SELECT
    count(distinct user_id) as bot_count -- 22814
    , round(avg(follower_count), 4) as avg_followers -- 1308.10173
FROM (
  SELECT
    uf.user_id
    , count(distinct uf.follower_id) as follower_count
  FROM impeachment_production.user_followers_flat_v2 uf
  JOIN impeachment_production.user_details_v4 bu on bu.user_id = uf.user_id
  WHERE bu.is_bot = true
  GROUP BY 1
)
```

... as compared to humans?


```sql
SELECT
    count(distinct user_id) as human_count -- 2,949,208
    ,round(avg(follower_count), 4) as avg_followers -- 207.5755
FROM (
  SELECT
    uf.user_id
    , count(distinct uf.follower_id) as follower_count
  FROM impeachment_production.user_followers_flat_v2 uf
  JOIN impeachment_production.user_details_v4 bu on bu.user_id = uf.user_id
  WHERE bu.is_bot = false
  GROUP BY 1
)
```

So bots have five times as many active followers? Let's see the bots with the most followers:


```sql
  SELECT
    uf.user_id
    ,string_agg(uf.screen_name, " | ") as screen_names
    ,count(distinct uf.follower_id) as follower_count
  FROM impeachment_production.user_followers_flat_v2 uf
  JOIN impeachment_production.user_details_v4 bu on bu.user_id = uf.user_id
  WHERE bu.is_bot = false
  GROUP BY 1
  ORDER BY follower_count desc
  LIMIT 10
```

Should we be restricting this to see how many **human** followers?

## User Followers - v2

```sql
-- for the follower:
-- ... are they bot or not?
-- ... is their opinion 0 or 1?
SELECT
  uff.user_id
  ,uff.screen_name
  ,uff.follower_id
  ,uff.follower_name
  ,CASE WHEN fbu.user_id IS NOT NULL THEN true ELSE false END follower_is_bot
FROM impeachment_production.active_followers_flat_v2 uff
LEFT JOIN impeachment_production.bots_above_80_v2 fbu ON fbu.user_id = uff.follower_id
LIMIT 10
```


```sql
DROP TABLE IF EXISTS impeachment_production.active_user_friends_bh_v2;
CREATE TABLE IF NOT EXISTS impeachment_production.active_user_friends_bh_v2 as (
  SELECT
     user_id
    ,count(distinct friend_id) as friend_count
    ,count(distinct case when friend_is_bot = true then friend_id end) as friend_count_b
    ,count(distinct case when friend_is_bot = false then friend_id end) as friend_count_h
    --,array_agg(distinct case when friend_is_bot = true and friend_id is not null then friend_id end) as friend_ids_b
    --,array_agg(distinct case when friend_is_bot = false and friend_id is not null then friend_id end) as friend_ids_h
    ,string_agg(distinct case when friend_is_bot = true then friend_id end, " | ") as friend_ids_b
    ,string_agg(distinct case when friend_is_bot = false then friend_id end,  " | ") as friend_ids_h
  FROM (
    SELECT
      uff.user_id
      ,uff.screen_name
      ,uff.friend_id
      ,uff.friend_name
      ,CASE WHEN fbu.user_id IS NOT NULL THEN true ELSE false END friend_is_bot
    FROM impeachment_production.active_user_friends_flat_v2 uff
    LEFT JOIN impeachment_production.bots_above_80_v2 fbu ON fbu.user_id = uff.friend_id
    WHERE uff.friend_id is not null
    --LIMIT 10
  ) zz
  GROUP BY 1
  --LIMIT 10
)
```


```sql
SELECT count(distinct user_id) as user_count -- 2,971,946 (users who have followers)
FROM impeachment_production.active_followers_bh_v2
```


```sql
DROP TABLE IF EXISTS impeachment_production.user_followers_bh_v2;
CREATE TABLE IF NOT EXISTS impeachment_production.user_followers_bh_v2 as (
  SELECT
    uf.user_id
    ,extract(date from ud.user_created_at) as created_on
    ,ud.screen_name_count
    ,ud.screen_names
    ,ud.is_bot
    ,ud.community_id as bot_network
    ,ud.status_count
    ,ud.rt_count
    ,ud.avg_score_lr
    ,ud.avg_score_nb
    ,ud.avg_score_bert
    --,cast(round(ud.avg_score_lr) as int64) as community_lr
    --,cast(round(ud.avg_score_nb) as int64) as community_nb
    --,cast(round(ud.avg_score_bert) as int64) as community_bert

    ,uf.follower_count
    ,uf.follower_count_b
    ,uf.follower_count_h
    ,uf.follower_ids_b
    ,uf.follower_ids_h
  FROM impeachment_production.active_followers_bh_v2 uf
  JOIN impeachment_production.user_details_v4 ud ON ud.user_id = uf.user_id
  --LIMIT 10
)
```

```sql
SELECT
   coalesce(
        cast(round(avg_score_bert) as int64),
        cast(round(avg_score_nb) as int64),
        cast(round(avg_score_lr) as int64),
        999
    ) as opinion_community

  ,count(distinct user_id) as user_count
FROM impeachment_production.user_followers_v2
-- WHERE is_bot = true -- 22814
--WHERE community_bert is null -- 422,312
GROUP BY 1
```

opinion_community	| user_count
--- | ---
0	| 1,913,883
1	| 1,058,062


```sql
SELECT
   coalesce(
        cast(round(avg_score_bert) as int64),
        cast(round(avg_score_nb) as int64),
        cast(round(avg_score_lr) as int64),
        999
    ) as opinion_community
    ,is_bot
  ,count(distinct user_id) as user_count
FROM impeachment_production.user_followers_v2
-- WHERE is_bot = true -- 22814
--WHERE community_bert is null -- 422,312
GROUP BY 1,2
```


opinion_community	| is_bot	| user_count
---	| ---	| ---
0	| false	| 1,904,201
1	| false	| 1,044,930
1	| true	| 13,132
0	| true	| 9,682


```sql
SELECT
   coalesce(avg_score_bert, avg_score_nb, avg_score_lr) as opinion_score
  ,count(distinct user_id) as user_count
FROM impeachment_production.user_followers_bh_v2
WHERE coalesce(avg_score_bert, avg_score_nb, avg_score_lr) = 0.5  -- 13,122
GROUP BY 1
```


```sql
DROP TABLE IF EXISTS impeachment_production.user_follower_network_v2;
CREATE TABLE IF NOT EXISTS user_follower_network_v2 as (
  SELECT
     user_id
     ,created_on
     ,screen_name_count
     ,screen_names
     ,is_bot
     ,bot_network
     ,status_count
     ,rt_count
     ,avg_score_lr
     ,avg_score_nb
     ,avg_score_bert
     ,coalesce(avg_score_bert, avg_score_nb, avg_score_lr) as opinion_community

     ,follower_count
     ,follower_count_b
     ,follower_count_h
     ,follower_ids_b
     ,follower_ids_h
  FROM impeachment_production.user_followers_bh_v2
  WHERE coalesce(avg_score_bert, avg_score_nb, avg_score_lr) <> 0.5  -- excludes 13,122 humans
  --LIMIT 10
)
```


Export this table to GCS as "user_follower_network_v2/nodes_*.csv" (sharded into smaller files due to size),

then upload all smaller files into drive as "user_follower_network_v2/nodes_*.csv".

Oh need to add q status...


```sql
DROP TABLE IF EXISTS impeachment_production.user_details_v5;
CREATE TABLE IF NOT EXISTS impeachment_production.user_details_v5 as (
  SELECT
    uf.user_id
    ,extract(date from ud.user_created_at) as created_on
    ,ud.screen_name_count
    ,ud.screen_names

    ,ud.is_bot
    ,ud.community_id as bot_network

    ,case when q.q_status_count > 0 then true else false end is_q
    ,q.q_status_count

    ,ud.status_count
    ,ud.rt_count

    ,ud.avg_score_lr
    ,ud.avg_score_nb
    ,ud.avg_score_bert
    ,cast(round(coalesce(ud.avg_score_bert, ud.avg_score_nb, ud.avg_score_lr)) as int64) as opinion_community

    ,uf.follower_count
    ,uf.follower_count_b
    ,uf.follower_count_h
    ,uf.follower_ids_b
    ,uf.follower_ids_h

  FROM impeachment_production.active_followers_bh_v2 uf
  JOIN impeachment_production.user_details_v4 ud ON ud.user_id = uf.user_id
  LEFT JOIN impeachment_production.q_users q ON q.user_id = uf.user_id
  WHERE coalesce(ud.avg_score_bert, ud.avg_score_nb, ud.avg_score_lr) <> 0.5
  --LIMIT 10
)
```


Execute each of these queries and "save" the result to google drive:

```sql
-- nodes.csv
SELECT user_id , created_on ,screen_name_count ,screen_names
 ,is_bot ,bot_network ,is_q, q_status_count
 ,status_count ,rt_count ,opinion_community
 ,follower_count, follower_count_b, follower_count_h
FROM impeachment_production.user_details_v5

-- follower_edges.csv
SELECT user_id
 ,follower_ids_b, follower_ids_h
FROM impeachment_production.user_details_v5
```

JK the edges are too big, so go the GCS export route with manual uploads to "user_follower_network_v2/follower_edges_*.csv".

```sql
CREATE TABLE impeachment_production.user_follower_network_v2_nodes as (
SELECT user_id , created_on ,screen_name_count ,screen_names
 ,is_bot ,bot_network ,is_q, q_status_count
 ,status_count ,rt_count ,opinion_community
 ,follower_count, follower_count_b, follower_count_h
FROM impeachment_production.user_details_v5
)

CREATE TABLE impeachment_production.user_follower_network_v2_edges as (
SELECT user_id
 ,follower_ids_b, follower_ids_h
FROM impeachment_production.user_details_v5
)
```

## Figures

```sql

-- for each day, how many bots were active?
-- what are the follower counts for each bot?
-- what are the opinion communities?

--SELECT
--    extract(date from t.created_at) as date
--    ,count(distinct t.user_id) as user_count
--  FROM impeachment_production.tweets t
--  --JOIN impeachment_production.user_details_v5 u ON u.user_id = cast(t.user_id as int64)
--  WHERE t.created_at BETWEEN '2019-12-20 00:00:00' AND '2020-02-15 23:59:59'
--    --and u.avg_score_bert is not null
--  GROUP BY 1
--  ORDER BY 1

--SELECT
--  u.user_id
--  ,u.screen_names
--  ,u.opinion_community
--  ,u.is_q
--  ,u.status_count
--  ,u.follower_count
--  ,u.follower_count_b
--  ,u.follower_count_h
--FROM impeachment_production.user_details_v5 u
----JOIN impeachment_production.tweets t on cast(t.user_id as int64) = u.user_id
--WHERE u.is_bot = true
--LIMIT 10

SELECT
  extract(date from t.created_at) as date

  ,count(distinct t.user_id) as user_count

  ,count(distinct case when is_bot=true and u.opinion_community=0 then u.user_id end) as user_count_b0
  ,count(distinct case when is_bot=true and u.opinion_community=1 then u.user_id end) as user_count_b1
  --,count(distinct case when is_bot=false and u.opinion_community=0 then u.user_id end) as user_count_h0
  --,count(distinct case when is_bot=false and u.opinion_community=1 then u.user_id end) as user_count_h1

  ,sum(case when is_bot=true and u.opinion_community=0 then u.status_count end) as  status_count_b0
  ,sum(case when is_bot=true and u.opinion_community=1 then u.status_count end) as  status_count_b1
  --,sum(case when is_bot=false and u.opinion_community=0 then u.status_count end) as status_count_h0
  --,sum(case when is_bot=false and u.opinion_community=1 then u.status_count end) as status_count_h1

  ,sum(case when is_bot=true and u.opinion_community=0 then u.follower_count end) as  follower_count_b0
  ,sum(case when is_bot=true and u.opinion_community=1 then u.follower_count end) as  follower_count_b1
  --,sum(case when is_bot=false and u.opinion_community=0 then u.follower_count end) as follower_count_h0
  --,sum(case when is_bot=false and u.opinion_community=1 then u.follower_count end) as follower_count_h1


  ,sum(case when is_bot=true and u.opinion_community=0 then u.follower_count_b end) as  follower_count_b0_b
  ,sum(case when is_bot=true and u.opinion_community=1 then u.follower_count_b end) as  follower_count_b1_b

  ,sum(case when is_bot=true and u.opinion_community=0 then u.follower_count_h end) as  follower_count_b0_h
  ,sum(case when is_bot=true and u.opinion_community=1 then u.follower_count_h end) as  follower_count_b1_h

FROM impeachment_production.user_details_v5 u
JOIN impeachment_production.tweets t on cast(t.user_id as int64) = u.user_id
WHERE u.is_bot = true
GROUP BY 1
--LIMIT 10


```

# User Friends - v2

JK we also want to make friend networks. So let's re-do this. We'll make a smaller nodes table, with friend/follower counts, and a separate table for friend edges, and a separate table for follower edges.

See [Friend Follower Networks](/app/friend_follower_networks/README.md).
