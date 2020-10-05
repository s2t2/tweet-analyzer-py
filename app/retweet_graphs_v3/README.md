# Retweet Graphs v3

After collecting tweets, our goal is to detect similarities in retweet activity between users.

## Setup

### BQ Setup

First, create a new dataset called "election_2020_analysis" or something, and set the `BIGQUERY_DATASET_NAME` env var accordingly.

Copy tweets there:

```sql
DROP TABLE IF EXISTS election_2020_analysis.tweets;
CREATE TABLE election_2020_analysis.tweets as (
    SELECT DISTINCT
        cast(status_id as int64) as status_id
        ,status_text
        ,truncated
        ,cast(retweeted_status_id as int64) as retweeted_status_id
        ,cast(retweeted_user_id as int64) as retweeted_user_id
        ,upper(retweeted_user_screen_name) as retweeted_user_screen_name
        ,cast(reply_status_id as int64) as reply_status_id
        ,cast(reply_user_id as int64) as reply_user_id
        ,is_quote
        ,geo
        ,created_at
        ,cast(user_id as int64) as user_id
        ,user_name
        ,upper(user_screen_name) as user_screen_name
        ,user_description
        ,user_location
        ,user_verified
        ,user_created_at
    FROM election_2020_production.tweets
-- LIMIT 10
);
```

### GCS Setup

Create a new bucket called "election-analysis-2020" and set the `GCS_BUCKET_NAME` env var accordingly.

## Usage

All-in-one weekly worker:

```sh
START_DATE="2020-09-26" N_DAYS=7 N_PERIODS=1 python -m app.retweet_graphs_v3.worker
```




















Then import the CSV file from GCS or CSV into BQ, into a table called "import_bot_probabilities". And choose a threshold where there are about 1% bots (usually around 70% or 80%):

```sql
SELECT
      count(distinct user_id) as bots
      ,count(distinct case when bot_probability >= 0.5 then user_id end) as bots_50
      ,count(distinct case when bot_probability >= 0.6 then user_id end) as bots_60
      ,count(distinct case when bot_probability >= 0.7 then user_id end) as bots_70
      ,count(distinct case when bot_probability >= 0.8 then user_id end) as bots_80
      ,count(distinct case when bot_probability >= 0.9 then user_id end) as bots_90
    FROM election_2020_analysis.import_bot_probabilities
```

Create a new table of bot probabilities, like "bots_over_70":

```sql
CREATE TABLE election_2020_analysis.bots_over_70 as (
   SELECT user_id, bot_probability
   FROM  election_2020_analysis.import_bot_probabilities
   WHERE bot_probability >= 0.7
)
```

### Bot Communities

Construct a bot retweet graph, for all bots above the given threshold (i.e. the `BOT_MIN`):

```sh
START_DATE="2020-09-26" END_DATE="2020-10-03" BOT_MIN=0.7 python -m app.retweet_graphs_v3.bot_retweet_grapher
```
















Constructing bot similarity graph (using the same `BOT_MIN` from the previous step):

```sh
BOT_TABLE_NAME="bots_above_70"  python -m app.bot_communities.bot_similarity_grapher
```

Assigning bots to spectral communities based on their similarity scores (using the same `BOT_MIN` from the previous step, and any small positive integer value for `N_COMMUNITIES`):

```sh
BOT_TABLE_NAME="bots_above_70" N_COMMUNITIES="2" python -m app.bot_communities.spectral_clustermaker
```

> WARNING: this process will overwrite previous community assignments, and due to randomness new results may not match.
