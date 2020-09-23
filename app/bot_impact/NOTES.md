# Notes

## Queries

```sql
/*
SELECT *
FROM impeachment_production.user_friends_flat
LIMIT 10
*/


/*
SELECT
   count(distinct status_id) as status_count -- 67666557
   ,count(distinct user_id) as user_count -- 3600545
FROM impeachment_production.statuses


*/

/*
SELECT min(created_at), max(created_at) -- user_id, created_at
FROM impeachment_production.statuses
WHERE EXTRACT(DATE FROM created_at) = "2020-02-06"
-- ORDER BY created_at desc -- 2020-02-05 00:00:00
LIMIT 10
*/


SELECT DISTINCT cast(user_id as int64) as user_id, upper(user_screen_name) as user_screen_name
FROM impeachment_production.tweets
WHERE EXTRACT(DATE FROM created_at) = "2020-02-05" -- 376,224

```


```sql
SELECT
  t.status_id
  ,t.created_at
  ,t.user_id
  ,upper(t.user_screen_name) as user_screen_name
  ,uf.friend_count
  ,uf.friend_names
FROM impeachment_production.user_friends uf
JOIN impeachment_production.tweets t ON upper(t.user_screen_name) = upper(uf.screen_name)
WHERE EXTRACT(DATE FROM t.created_at) = "2020-02-05"
-- LIMIT 10

-- 53.6 sec elapsed, 27.7 GB processed
```

```sql
SELECT
  EXTRACT(DATE FROM created_at) as date
  ,count(distinct user_id) as user_count
FROM impeachment_production.tweets
GROUP BY 1
ORDER BY 1
```

## BQ Migrations

Bad migrations:

```sql
/*
DROP TABLE IF EXISTS impeachment_production.user_friends_flat_20200205;
CREATE TABLE impeachment_production.user_friends_flat_20200205 as (
  SELECT
    DISTINCT uff.screen_name, uff.friend_name
  FROM impeachment_production.user_friends_flat uff
  JOIN impeachment_production.tweets t ON t.user_id = uff.user_id
  WHERE EXTRACT(DATE FROM t.created_at) = "2020-02-05"
  -- LIMIT 10
)


SELECT count(screen_name) as row_count
FROM impeachment_production.user_friends_flat_20200205
-- 322,144,795 edges on this day

*/


/*
DROP TABLE IF EXISTS impeachment_production.user_friends_20200205;
CREATE TABLE impeachment_production.user_friends_20200205 as (

  SELECT
    uf.screen_name
    ,uf.friend_names
  FROM impeachment_production.user_friends uf
  JOIN impeachment_production.statuses t on t.user_id = uf.user_id
  WHERE uf.friend_count > 0
    AND extract(date from t.created_at) = "2020-02-05"

);
-- 1,031,392
```

Do it right:

``` sql
DROP TABLE IF EXISTS impeachment_production.user_friends_v2;
CREATE TABLE impeachment_production.user_friends_v2 as (
  SELECT
    uff.user_id
    ,uff.screen_name
    --,uff.friend_count
    ,ARRAY_AGG(DISTINCT UPPER(uff.friend_name) IGNORE NULLS) as friend_names
  FROM impeachment_production.user_friends_flat uff
  GROUP BY 1,2
);
```


```sql
DROP TABLE IF EXISTS impeachment_production.user_friends_20200205;
CREATE TABLE impeachment_production.user_friends_20200205 as (
  SELECT uf.user_id ,uf.screen_name ,uf.friend_names
  FROM impeachment_production.user_friends_v2 uf
  JOIN (
    SELECT DISTINCT user_id FROM impeachment_production.tweets t
    WHERE extract(date from t.created_at) = "2020-02-05"
  ) t ON t.user_id = uf.user_id
);

/*
SELECT count(screen_name) as row_count, sum(array_length(friend_names)) as edge_count
FROM impeachment_production.user_friends_20200205
-- 361,505
-- 322,146,064
*/
```



```sql
--SELECT REGEXP_REPLACE("RT @YoMama: Hey blah blah 456789 &^ #tag #topic. You know?", r"[^a-zA-Z0-9 @#]", "")
-- should equal 'RT @YoMama Hey blah blah 456789  #tag #topic You know'

SELECT
  REGEXP_REPLACE("RT @YoMama: Hey blah blah 456789 &^ #tag #topic. You know?", r"[^a-zA-Z0-9 @#]", "")
  ,SPLIT(UPPER(REGEXP_REPLACE("RT @YoMama: Hey blah blah 456789 &^ #tag #topic. You know?", r"[^a-zA-Z0-9 @#]", "")) , ' ') as tokens
```




```sql

  SELECT DISTINCT
    t.user_id
    -- ,ct.community_id
    -- ,count(distinct ct.hashtag) as community_score
  FROM (
    SELECT
      status_id
      ,user_id
      ,SPLIT(UPPER(REGEXP_REPLACE(status_text, r"[^a-zA-Z0-9 @#]", "")) , ' ') as tweet_tokens
    FROM impeachment_production.statuses
    WHERE status_text like '%#%'
      AND EXTRACT(DATE FROM created_at) = '2020-02-05'
    -- LIMIT 10
  ) t
  JOIN impeachment_production.2_community_tags ct ON ct.hashtag in UNNEST(t.tweet_tokens)
  WHERE ct.community_id = 1
  --GROUP BY 1,2
  --ORDER BY 1
  LIMIT 10
-- );

```

```sql
DROP TABLE IF EXISTS impeachment_production.community_0_20200205;
CREATE TABLE impeachment_production.community_0_20200205 as (

  SELECT DISTINCT t.user_id
  FROM impeachment_production.2_community_tags ct
  JOIN (
    SELECT
      status_id
      ,user_id
      ,SPLIT(UPPER(REGEXP_REPLACE(status_text, r"[^a-zA-Z0-9 @#]", "")) , ' ') as tweet_tokens
    FROM impeachment_production.statuses
    WHERE status_text like '%#%'
      AND EXTRACT(DATE FROM created_at) = '2020-02-05'
    -- LIMIT 10
  ) t ON ct.hashtag in UNNEST(t.tweet_tokens)
  WHERE ct.community_id = 0
  -- LIMIT 10
);

```

```sql
DROP TABLE IF EXISTS impeachment_production.community_1_20200205;
CREATE TABLE impeachment_production.community_1_20200205 as (

  SELECT DISTINCT t.user_id
  FROM impeachment_production.2_community_tags ct
  JOIN (
    SELECT
      status_id
      ,user_id
      ,SPLIT(UPPER(REGEXP_REPLACE(status_text, r"[^a-zA-Z0-9 @#]", "")) , ' ') as tweet_tokens
    FROM impeachment_production.statuses
    WHERE status_text like '%#%'
      AND EXTRACT(DATE FROM created_at) = '2020-02-05'
    -- LIMIT 10
  ) t ON ct.hashtag in UNNEST(t.tweet_tokens)
  WHERE ct.community_id = 1
  -- LIMIT 10
);
```


```sql

/*
SELECT count(distinct user_id) as user_count -- 6417
  FROM impeachment_production.community_1_20200205 u
  LIMIT 10
  */



DROP TABLE IF EXISTS impeachment_production.community_0_friends_20200205;
CREATE TABLE impeachment_production.community_0_friends_20200205 as (
  SELECT u.user_id, uf.screen_name, uf.friend_names
  FROM impeachment_production.community_0_20200205 u
  JOIN impeachment_production.user_friends_v2 uf ON uf.user_id = u.user_id
  -- LIMIT 10
);


DROP TABLE IF EXISTS impeachment_production.community_1_friends_20200205;
CREATE TABLE impeachment_production.community_1_friends_20200205 as (
  SELECT u.user_id, uf.screen_name, uf.friend_names
  FROM impeachment_production.community_1_20200205 u
  JOIN impeachment_production.user_friends_v2 uf ON uf.user_id = u.user_id
  -- LIMIT 10
);

```

```sql
/*
SELECT user_id
FROM impeachment_production.statuses t -- 3,600,545
GROUP BY 1
-- HAVING count(distinct status_id) > 3 -- 1,082,362
-- LIMIT 10
*/

SELECT user_id, count(distinct status_id) as status_count
FROM impeachment_production.tweets t -- 3,600,545
WHERE t.created_at between '2020-02-05' and '2020-02-06' -- 376,192
GROUP BY 1
-- HAVING count(distinct status_id) > 2 -- 101,397
HAVING count(distinct status_id) > 3 -- 72,327
ORDER BY 2 DESC
-- LIMIT 10



SELECT uf.*
FROM impeachment_production.user_friends_v2 uf
JOIN (
  SELECT user_id, count(distinct status_id) as status_count
  FROM impeachment_production.tweets t -- 3,600,545
  WHERE t.created_at between '2020-02-05' and '2020-02-06' -- 376,192
  GROUP BY 1
  HAVING count(distinct status_id) > 3 -- 72,327
  ORDER BY 2 DESC
) u ON u.user_id = uf.user_id -- 69,699 excludes friend-less
-- LIMIT 10



```





```sql
/*
SELECT status_id, predicted_community_id
FROM impeachment_production.2_community_predictions
limit 10
*/

SELECT
  uf.user_id
  ,uf.screen_name
  ,u.status_count
  ,u.prediction_count
  ,u.mean_opinion_score
  ,ARRAY_LENGTH(uf.friend_names) as friend_count
  ,uf.friend_names

FROM impeachment_production.user_friends_v2 uf
JOIN (
    SELECT
      user_id
      ,count(distinct t.status_id) as status_count
      ,count(distinct p.status_id) as prediction_count
      ,avg(p.predicted_community_id) as mean_opinion_score
    FROM impeachment_production.tweets t
    JOIN impeachment_production.2_community_predictions p ON p.status_id = cast(t.status_id as int64)
    WHERE EXTRACT(DATE FROM t.created_at) = '2020-02-05'
    GROUP BY 1
    HAVING count(distinct t.status_id) >= 45
) u ON u.user_id = uf.user_id

```




```sql

SELECT
  uf.user_id
  ,uf.screen_name
  ,u.status_count
  ,u.prediction_count
  ,u.mean_opinion_score
  ,ARRAY_LENGTH(uf.friend_names) as friend_count
  --,uf.friend_names
  ,case when community_id is not null then true else false end is_bot

FROM impeachment_production.user_friends_v2 uf
JOIN (
    SELECT
      t.user_id
      ,count(distinct t.status_id) as status_count
      ,count(distinct p.status_id) as prediction_count
      ,avg(p.predicted_community_id) as mean_opinion_score
    FROM impeachment_production.tweets t
    JOIN impeachment_production.2_community_predictions p ON p.status_id = cast(t.status_id as int64)
    WHERE EXTRACT(DATE FROM t.created_at) = '2020-02-05'
    GROUP BY 1
    HAVING count(distinct t.status_id) >= 45
) u ON u.user_id = uf.user_id
LEFT JOIN impeachment_production.2_bot_communities b ON b.user_id = cast(u.user_id as int64)


```


```sql
-- this could use optimization. there's no need to hit tweets in the subquery
SELECT
  timeframe.first_day
  ,timeframe.last_day
  ,timeframe.num_days
  ,cast(t.user_id as int64) as user_id
  ,count(distinct t.status_id) as status_count
  ,count(distinct t.status_id) / timeframe.num_days as tweets_per_day
FROM (
  SELECT
    EXTRACT(DATE FROM min(t.created_at)) as first_day
    ,EXTRACT(DATE FROM max(t.created_at)) as last_day
    ,DATE_DIFF(
      EXTRACT(DATE FROM max(t.created_at))
      ,EXTRACT(DATE FROM min(t.created_at))
      ,DAY
    ) as num_days
  FROM impeachment_production.tweets t
  WHERE t.created_at BETWEEN '2019-12-20' AND '2020-02-20'
) timeframe
JOIN impeachment_production.tweets t on t.created_at BETWEEN '2019-12-20' AND '2020-02-20'
GROUP BY 1,2,3,4

```


```sql
DROP TABLE IF EXISTS impeachment_production.user_tweet_rates;
CREATE TABLE impeachment_production.user_tweet_rates as (
  SELECT
    cast(t.user_id as int64) as user_id
    --,count(distinct t.status_id) as status_count
    ,count(distinct t.status_id) / 62 as tweets_per_day
  FROM impeachment_production.tweets t
  WHERE t.created_at BETWEEN '2019-12-20' AND '2020-02-20' -- a time period of consistent collection
  GROUP BY 1
)
```




```sql
SELECT
  uf.user_id
  ,uf.screen_name
  ,u.status_count
  ,u.prediction_count
  ,u.mean_opinion_score
  ,ARRAY_LENGTH(uf.friend_names) as friend_count
  --,uf.friend_names
  ,case when community_id is not null then true else false end is_bot
  ,tr.tweets_per_day as tweet_rate
FROM impeachment_production.user_friends_v2 uf
JOIN (
    SELECT
      cast(t.user_id as int64) as user_id
      ,count(distinct t.status_id) as status_count
      ,count(distinct p.status_id) as prediction_count
      ,avg(p.predicted_community_id) as mean_opinion_score
    FROM impeachment_production.tweets t
    JOIN impeachment_production.2_community_predictions p ON p.status_id = cast(t.status_id as int64)
    WHERE EXTRACT(DATE FROM t.created_at) = '2020-02-05'
    GROUP BY 1
    HAVING count(distinct t.status_id) >= 45
) u ON u.user_id = cast(uf.user_id as int64)
JOIN impeachment_production.user_tweet_rates tr ON tr.user_id = u.user_id
LEFT JOIN impeachment_production.2_bot_communities b ON b.user_id = u.user_id
-- and export to CSV for the given day --> nodes.csv
```






















<hr>




## PG Migrations

```sql

DROP TABLE IF EXISTS user_friends_20200205;
CREATE TABLE user_friends_20200205 as (

  SELECT
    t.user_screen_name as screen_name
    ,uf.friend_names
  FROM user_friends uf
  JOIN tweets t ON upper(t.user_screen_name) = upper(uf.screen_name)
  WHERE t.created_at::date = '2020-02-05'
    AND uf.friend_count > 0
  -- LIMIT 10
)
```


```sql
SELECT count(screen_name) as row_count
FROM user_friends_20200205
-- 998,295 tweeters
```