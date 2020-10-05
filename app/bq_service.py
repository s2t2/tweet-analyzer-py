from datetime import datetime, timedelta, timezone
import os
from functools import lru_cache
from pprint import pprint

from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

from app import APP_ENV, seek_confirmation
from app.decorators.number_decorators import fmt_n

load_dotenv()

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") # implicit check by google.cloud (and keras)
PROJECT_NAME = os.getenv("BIGQUERY_PROJECT_NAME", default="tweet-collector-py")
DATASET_NAME = os.getenv("BIGQUERY_DATASET_NAME", default="impeachment_development") #> "_test" or "_production"
DESTRUCTIVE_MIGRATIONS = (os.getenv("DESTRUCTIVE_MIGRATIONS", default="false") == "true")
VERBOSE_QUERIES = (os.getenv("VERBOSE_QUERIES", default="false") == "true")

CLEANUP_MODE = (os.getenv("CLEANUP_MODE", default="true") == "true")

DEFAULT_START = "2019-12-02 01:00:00" # @deprectated, the "beginning of time" for the impeachment dataset. todo: allow customization via env var
DEFAULT_END = "2020-03-24 20:00:00" # @deprectated, the "end of time" for the impeachment dataset. todo: allow customization via env var

def generate_timestamp():
    """Formats datetime for storing in BigQuery"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def generate_temp_table_id():
    return datetime.now().strftime('%Y_%m_%d_%H_%M_%S')

def split_into_batches(my_list, batch_size=9000):
    """Splits a list into evenly sized batches""" # h/t: h/t: https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
    for i in range(0, len(my_list), batch_size):
        yield my_list[i : i + batch_size]

class BigQueryService():

    def __init__(self, project_name=PROJECT_NAME, dataset_name=DATASET_NAME,
                        verbose=VERBOSE_QUERIES, destructive=DESTRUCTIVE_MIGRATIONS, cautious=True):
        self.project_name = project_name
        self.dataset_name = dataset_name
        self.dataset_address = f"{self.project_name}.{self.dataset_name}"

        self.verbose = (verbose == True)
        self.destructive = (destructive == True)
        self.cautious = (cautious == True)

        self.client = bigquery.Client()

        print("-------------------------")
        print("BIGQUERY SERVICE...")
        print("  DATASET ADDRESS:", self.dataset_address.upper())
        print("  DESTRUCTIVE MIGRATIONS:", self.destructive)
        print("  VERBOSE QUERIES:", self.verbose)

        if self.cautious:
            seek_confirmation()

    @property
    def metadata(self):
        return {"dataset_address": self.dataset_address, "destructive": self.destructive, "verbose": self.verbose}

    def execute_query(self, sql):
        """Param: sql (str)"""
        if self.verbose:
            print(sql)
        job = self.client.query(sql)
        return job.result()

    def execute_query_in_batches(self, sql, temp_table_name=None):
        """Param: sql (str)"""
        if self.verbose:
            print(sql)

        if not temp_table_name:
            temp_table_id = generate_temp_table_id()
            temp_table_name = f"{self.dataset_address}.temp_{temp_table_id}"

        job_config = bigquery.QueryJobConfig(
            priority=bigquery.QueryPriority.BATCH,
            allow_large_results=True,
            destination=temp_table_name
        )
        job = self.client.query(sql, job_config=job_config)
        print("BATCH QUERY JOB:", type(job), job.job_id, job.state, job.location)
        return job

    def insert_records_in_batches(self, table, records):
        """
        Params:
            table (table ID string, Table, or TableReference)
            records (list of dictionaries)
        """
        rows_to_insert = [list(d.values()) for d in records]
        #errors = self.client.insert_rows(table, rows_to_insert)
        #> ... google.api_core.exceptions.BadRequest: 400 POST https://bigquery.googleapis.com/bigquery/v2/projects/.../tables/daily_bot_probabilities/insertAll:
        #> ... too many rows present in the request, limit: 10000 row count: 36092.
        #> ... see: https://cloud.google.com/bigquery/quotas#streaming_inserts
        errors = []
        batches = list(split_into_batches(rows_to_insert, batch_size=5000))
        for batch in batches:
            errors += self.client.insert_rows(table, batch)
        return errors

    def delete_temp_tables_older_than(self, days=3):
        """Deletes all tables that:
            have "temp_" in their name (product of the batch jobs), and were
            created at least X days ago (safely avoid deleting tables being used by in-progress batch jobs)
        """
        cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=days)
        print("CUTOFF DATE:", cutoff_date)

        tables = list(self.client.list_tables(self.dataset_name)) # API call
        tables_to_delete = [t for t in tables if "temp_" in t.table_id and t.created < cutoff_date]
        print("TABLES TO DELETE:")
        pprint([t.table_id for t in tables_to_delete])
        seek_confirmation()

        print("DELETING...")
        for old_temp_table in tables_to_delete:
            print("  ", old_temp_table.table_id)
            self.client.delete_table(old_temp_table)

    #
    # COLLECTING TWEETS V2
    #

    def migrate_topics_table(self):
        print("MIGRATING TOPICS TABLE...")
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.topics`; "
        sql += f"""
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.topics` (
                topic STRING NOT NULL,
                created_at TIMESTAMP,
            );
        """
        return list(self.execute_query(sql))

    def migrate_tweets_table(self):
        print("MIGRATING TWEETS TABLE...")
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.tweets`; "
        sql += f"""
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.tweets` (
                status_id           STRING,
                status_text         STRING,
                truncated           BOOLEAN,
                retweeted_status_id STRING,
                retweeted_user_id   STRING,
                retweeted_user_screen_name   STRING,
                reply_status_id     STRING,
                reply_user_id       STRING,
                is_quote            BOOLEAN,
                geo                 STRING,
                created_at          TIMESTAMP,

                user_id             STRING,
                user_name           STRING,
                user_screen_name    STRING,
                user_description    STRING,
                user_location       STRING,
                user_verified       BOOLEAN,
                user_created_at     TIMESTAMP
            );
        """
        return list(self.execute_query(sql))

    @property
    @lru_cache(maxsize=None)
    def topics_table(self):
        return self.client.get_table(f"{self.dataset_address}.topics") # an API call (caches results for subsequent inserts)

    @property
    @lru_cache(maxsize=None)
    def tweets_table(self):
        return self.client.get_table(f"{self.dataset_address}.tweets") # an API call (caches results for subsequent inserts)

    def fetch_topics(self):
        """Returns a list of topic strings"""
        sql = f"""
            SELECT topic, created_at
            FROM `{self.dataset_address}.topics`
            ORDER BY created_at;
        """
        return self.execute_query(sql)

    def fetch_topic_names(self):
        return [row.topic for row in self.fetch_topics()]

    def append_topics(self, topics):
        """
        Inserts topics unless they already exist.
        Param: topics (list of dict)
        """
        rows = self.fetch_topics()
        existing_topics = [row.topic for row in rows]
        new_topics = [topic for topic in topics if topic not in existing_topics]
        if new_topics:
            rows_to_insert = [[new_topic, generate_timestamp()] for new_topic in new_topics]
            errors = self.client.insert_rows(self.topics_table, rows_to_insert)
            return errors
        else:
            print("NO NEW TOPICS...")
            return []

    def append_tweets(self, tweets):
        """Param: tweets (list of dict)"""
        rows_to_insert = [list(d.values()) for d in tweets]
        errors = self.client.insert_rows(self.tweets_table, rows_to_insert)
        return errors

    #
    # COLLECTING USER FRIENDS
    #

    def migrate_populate_users(self):
        """
        Resulting table has a row for each user id / screen name combo
            (multiple rows per user id if they changed their screen name)
        """
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.users`; "
        sql += f"""
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.users` as (
                SELECT DISTINCT
                    user_id
                    ,user_screen_name as screen_name
                FROM `{self.dataset_address}.tweets`
                WHERE user_id IS NOT NULL AND user_screen_name IS NOT NULL
                ORDER BY 1
            );
        """
        results = self.execute_query(sql)
        return list(results)

    def migrate_user_friends(self):
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.user_friends`; "
        sql += f"""
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.user_friends` (
                user_id STRING,
                screen_name STRING,
                friend_count INT64,
                friend_names ARRAY<STRING>,
                start_at TIMESTAMP,
                end_at TIMESTAMP
            );
        """
        results = self.execute_query(sql)
        return list(results)

    def fetch_remaining_users(self, min_id=None, max_id=None, limit=None):
        """Returns a list of table rows"""
        sql = f"""
            SELECT
                u.user_id
                ,u.screen_name
            FROM `{self.dataset_address}.users` u
            LEFT JOIN `{self.dataset_address}.user_friends` f ON u.user_id = f.user_id
            WHERE f.user_id IS NULL
        """
        if min_id and max_id:
            sql += f"  AND CAST(u.user_id as int64) BETWEEN {int(min_id)} AND {int(max_id)} "
        sql += f"ORDER BY u.user_id "
        if limit:
            sql += f"LIMIT {int(limit)};"
        results = self.execute_query(sql)
        return list(results)

    @property
    @lru_cache(maxsize=None)
    def user_friends_table(self):
        return self.client.get_table(f"{self.dataset_address}.user_friends") # an API call (caches results for subsequent inserts)

    def insert_user_friends(self, records):
        """
        Param: records (list of dictionaries)
        """
        rows_to_insert = [list(d.values()) for d in records]
        #rows_to_insert = [list(d.values()) for d in records if any(d["friend_names"])] # doesn't store failed attempts. can try those again later
        #if any(rows_to_insert):
        errors = self.client.insert_rows(self.user_friends_table, rows_to_insert)
        return errors

    def user_friend_collection_progress(self):
        sql = f"""
        SELECT
            count(distinct user_id) as user_count
            ,round(avg(runtime_seconds), 2) as avg_duration
            ,round(sum(has_friends) / count(distinct user_id), 2) as pct_friendly
            ,round(avg(CASE WHEN has_friends = 1 THEN runtime_seconds END), 2) as avg_duration_friendly
            ,round(avg(CASE WHEN has_friends = 1 THEN friend_count END), 2) as avg_friends_friendly
        FROM (
            SELECT
                user_id
                ,friend_count
                ,if(friend_count > 0, 1, 0) as has_friends
                ,start_at
                ,end_at
                ,DATETIME_DIFF(CAST(end_at as DATETIME), cast(start_at as DATETIME), SECOND) as runtime_seconds
            FROM `{service.dataset_address}.user_friends`
        ) subq
        """
        return self.execute_query(sql)

    #
    # FRIEND GRAPHS
    #

    def fetch_user_friends(self, min_id=None, max_id=None, limit=None):
        sql = f"""
            SELECT user_id, screen_name, friend_count, friend_names, start_at, end_at
            FROM `{self.dataset_address}.user_friends`
        """
        if min_id and max_id:
            sql += f" WHERE CAST(user_id as int64) BETWEEN {int(min_id)} AND {int(max_id)} "
        sql += f"ORDER BY user_id "
        if limit:
            sql += f"LIMIT {int(limit)};"
        #return list(self.execute_query(sql))
        return self.execute_query(sql) # return the generator so we can avoid storing the results in memory

    def fetch_user_friends_in_batches(self, limit=None, min_friends=None):
        sql = f"""
            SELECT user_id, screen_name, friend_count, friend_names
            FROM `{self.dataset_address}.user_friends`
        """
        if min_friends:
            sql += f" WHERE ARRAY_LENGTH(friend_names) >= {int(min_friends)} "
        if limit:
            sql += f" LIMIT {int(limit)}; "

        return self.execute_query_in_batches(sql)

    def partition_user_friends(self, n=10):
        """Params n (int) the number of partitions, each will be of equal size"""
        sql = f"""
            SELECT
                partition_id
                ,count(DISTINCT user_id) as user_count
                ,min(user_id) as min_id
                ,max(user_id) as max_id
            FROM (
            SELECT
                NTILE({int(n)}) OVER (ORDER BY CAST(user_id as int64)) as partition_id
                ,CAST(user_id as int64) as user_id
            FROM (SELECT DISTINCT user_id FROM `{self.dataset_address}.user_friends`)
            ) user_partitions
            GROUP BY partition_id
        """
        results = self.execute_query(sql)
        return list(results)

    def fetch_random_users(self, limit=1000, topic="impeach", start_at=DEFAULT_START, end_at=DEFAULT_END):
        """
        Fetches a random slice of users talking about a given topic during a given timeframe.

        Params:

            topic (str) the topic they were tweeting about:
                        to be balanced, choose 'impeach', '#IGHearing', '#SenateHearing', etc.
                        to be left-leaning, choose '#ImpeachAndConvict', '#ImpeachAndRemove', etc.
                        to be right-leaning, choose '#ShamTrial', '#AquittedForever', '#MAGA', etc.

            limit (int) the max number of users to fetch

            start_at (str) a date string for the earliest tweet

            end_at (str) a date string for the latest tweet

        """
        sql = f"""
            SELECT DISTINCT user_id, user_screen_name, user_created_at
            FROM `{self.dataset_address}.tweets`
            WHERE upper(status_text) LIKE '%{topic.upper()}%' AND (created_at BETWEEN '{start_at}' AND '{end_at}')
            ORDER BY rand()
            LIMIT {int(limit)};
        """
        return self.execute_query(sql)

    #
    # RETWEET GRAPHS
    #

    def fetch_retweet_counts_in_batches(self, topic=None, start_at=None, end_at=None):
        """
        For each retweeter, includes the number of times each they retweeted each other user.
            Optionally about a given topic.
            Optionally with within a given timeframe.

        Params:

            topic (str) the topic they were tweeting about, like 'impeach', '#MAGA', "@politico", etc.
            start_at (str) a date string for the earliest tweet
            end_at (str) a date string for the latest tweet
        """
        sql = f"""
            SELECT
                user_id
                ,user_screen_name
                ,retweet_user_screen_name
                ,count(distinct status_id) as retweet_count
            FROM `{self.dataset_address}.retweets`
            WHERE user_screen_name <> retweet_user_screen_name -- excludes people retweeting themselves
        """
        if topic:
            sql+=f"""
                AND upper(status_text) LIKE '%{topic.upper()}%'
            """
        if start_at and end_at:
            sql+=f"""
                AND (created_at BETWEEN '{start_at}' AND '{end_at}')
            """
        sql += """
            GROUP BY 1,2,3
        """

        return self.execute_query_in_batches(sql)

    def fetch_specific_user_friends(self, screen_names):
        sql = f"""
            SELECT user_id, screen_name, friend_count, friend_names, start_at, end_at
            FROM `{self.dataset_address}.user_friends`
            WHERE screen_name in {tuple(screen_names)} -- tuple conversion surrounds comma-separated screen_names in parens
        """
        return self.execute_query(sql)

    def fetch_specific_retweet_counts(self, screen_names):
        """FYI this fetches multiple rows per screen_name, for each screen_name that user retweeted"""
        sql = f"""
            SELECT user_id, user_screen_name, retweet_user_screen_name, retweet_count
            FROM `{self.dataset_address}.retweet_counts`
            WHERE user_screen_name in {tuple(screen_names)} -- tuple conversion surrounds comma-separated screen_names in parens
                -- AND user_screen_name <> retweet_user_screen_name -- exclude users who have retweeted themselves
            ORDER BY 2,3
        """
        return self.execute_query(sql)

    def fetch_retweet_weeks(self, start_at=None, end_at=None):
        """
        Params:
            start_at (str) like "2019-12-15 00:00:00"
            end_at (str) like "2020-03-21 23:59:59"
        """
        sql = f"""
            SELECT
                CASE
                    WHEN EXTRACT(week from created_at) = 0 THEN EXTRACT(year from created_at) - 1 -- treat first week of new year as the previous year
                    ELSE EXTRACT(year from created_at)
                    END  year

                ,CASE
                    WHEN EXTRACT(week from created_at) = 0 THEN 52 -- treat first week of new year as the previous week
                    ELSE EXTRACT(week from created_at)
                    END  week

                ,count(DISTINCT EXTRACT(day from created_at)) as day_count
                ,min(created_at) as min_created
                ,max(created_at) as max_created
                ,count(DISTINCT status_id) as retweet_count
                ,count(DISTINCT user_id) as user_count
            FROM `{self.dataset_address}.retweets`
        """
        if start_at and end_at:
            sql += f"""
            WHERE created_at BETWEEN '{start_at}' AND '{end_at}'
            """
        sql += """
            GROUP BY 1,2
            ORDER BY 1,2
        """
        return self.execute_query(sql)

    #
    # LOCAL ANALYSIS (PG PIPELINE)
    #

    def fetch_tweets_in_batches(self, limit=None, start_at=None, end_at=None):
        sql = f"""
            SELECT
                status_id
                ,status_text
                ,truncated
                ,NULL as retweeted_status_id -- restore for version 2
                ,NULL as retweeted_user_id -- restore for version 2
                ,NULL as retweeted_user_screen_name -- restore for version 2
                ,reply_status_id
                ,reply_user_id
                ,is_quote
                ,geo
                ,created_at

                ,user_id
                ,user_name
                ,user_screen_name
                ,user_description
                ,user_location
                ,user_verified
                ,user_created_at

            FROM `{self.dataset_address}.tweets`
        """
        if start_at and end_at:
            sql+=f"""
                WHERE (created_at BETWEEN '{str(start_at)}' AND '{str(end_at)}')
            """
        if limit:
            sql += f" LIMIT {int(limit)}; "
        return self.execute_query_in_batches(sql)


    def fetch_user_details_in_batches(self, limit=None):
        sql = f"""
            SELECT
                user_id
                ,screen_name
                ,name
                ,description
                ,location
                ,verified
                ,created_at

                ,screen_name_count
                ,name_count
                ,description_count
                ,location_count
                ,verified_count
                ,created_at_count

                ,screen_names
                ,names
                ,descriptions
                ,locations
                ,verifieds
                ,created_ats

                ,friend_count

                ,status_count
                ,retweet_count

                -- these topics are specific to the impeachment dataset, so will need to generalize if/when working with another topic (leave for future concern)
                ,impeach_and_convict
                ,senate_hearing
                ,ig_hearing
                ,facts_matter
                ,sham_trial
                ,maga
                ,acquitted_forever

            FROM `{self.dataset_address}.user_details`
        """
        if limit:
            sql += f"LIMIT {int(limit)};"

        return self.execute_query_in_batches(sql)

    def fetch_retweeter_details_in_batches(self, limit=None):
        sql = f"""
            SELECT
                user_id

                ,verified
                ,created_at
                ,screen_name_count
                ,name_count

                ,retweet_count
                ,ig_report
                ,ig_hearing
                ,senate_hearing
                ,not_above_the_law
                ,impeach_and_convict
                ,impeach_and_remove
                ,facts_matter
                ,sham_trial
                ,maga
                ,acquitted_forever
                ,country_over_party

            FROM `{self.dataset_address}.retweeter_details`
        """
        if limit:
            sql += f"LIMIT {int(limit)};"

        return self.execute_query_in_batches(sql)

    def fetch_retweeters_by_topic_exclusive(self, topic):
        """
        Get the retweeters talking about topic x and those not, so we can perform a two-sample KS-test on them.
        """
        topic = topic.upper() # do uppercase conversion once here instead of many times inside sql below
        sql = f"""
            -- TOPIC: '{topic}'
            SELECT
                rt.user_id
                ,rt.user_created_at
                ,count(distinct case when REGEXP_CONTAINS(upper(rt.status_text), '{topic}') then rt.status_id end) as count
            FROM {self.dataset_address}.retweets rt
            GROUP BY 1,2
        """
        return self.execute_query(sql)

    def fetch_retweeters_by_topics_exclusive(self, x_topic, y_topic):
        """
        Get the retweeters talking about topic x and not y (and vice versa).
        For each user, determines how many times they were talking about topic x and y.
        Only returns users who were talking about one or the other, so we can perform a two-sample KS-test on them.
        """
        x_topic = x_topic.upper() # do uppercase conversion once here instead of many times inside sql below
        y_topic = y_topic.upper() # do uppercase conversion once here instead of many times inside sql below
        sql = f"""
            -- TOPICS: '{x_topic}' | '{y_topic}'
            SELECT
                rt.user_id
                ,rt.user_created_at
                ,count(distinct case when REGEXP_CONTAINS(upper(rt.status_text), '{x_topic}') then rt.status_id end) as x_count
                ,count(distinct case when REGEXP_CONTAINS(upper(rt.status_text), '{y_topic}') then rt.status_id end) as y_count
            FROM {self.dataset_address}.retweets rt
            WHERE REGEXP_CONTAINS(upper(rt.status_text), '{x_topic}')
                OR REGEXP_CONTAINS(upper(rt.status_text), '{y_topic}')
            GROUP BY 1,2
            HAVING (x_count > 0 and y_count = 0) OR (x_count = 0 and y_count > 0) -- mutually exclusive populations
        """
        return self.execute_query(sql)

    #
    # RETWEET GRAPHS V2 - USER ID LOOKUPS
    #

    def fetch_idless_screen_names(self):
        sql = f"""
            SELECT DISTINCT rt.retweet_user_screen_name as screen_name
            FROM {self.dataset_address}.retweets rt
            LEFT JOIN {self.dataset_address}.tweets t on t.user_screen_name = rt.retweet_user_screen_name
            WHERE t.user_id IS NULL
        """
        return self.execute_query(sql)

    def migrate_user_id_lookups_table(self):
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.user_id_lookups`; "
        sql += f"""
            CREATE TABLE `{self.dataset_address}.user_id_lookups` (
                lookup_at TIMESTAMP,
                counter INT64,
                screen_name STRING,
                user_id STRING,
                message STRING
            );
        """
        return self.execute_query(sql)

    @property
    @lru_cache(maxsize=None)
    def user_id_lookups_table(self):
        return self.client.get_table(f"{self.dataset_address}.user_id_lookups") # an API call (caches results for subsequent inserts)

    def upload_user_id_lookups(self, records):
        """
        Param: records (list of dictionaries)
        """
        rows_to_insert = [list(d.values()) for d in records]
        errors = self.client.insert_rows(self.user_id_lookups_table, rows_to_insert)
        return errors

    def fetch_max_user_id_postlookup(self):
        sql = f"""
            SELECT max(user_id) as max_user_id -- 999999827600650240
            FROM (
                SELECT DISTINCT user_id FROM {self.dataset_address}.tweets -- 3,600,545
                UNION ALL
                SELECT DISTINCT user_id FROM {self.dataset_address}.user_id_lookups WHERE user_id IS NOT NULL -- 14,969
            ) all_user_ids -- 3,615,409
        """
        results = list(self.execute_query(sql))
        return int(results[0]["max_user_id"])

    def fetch_idless_screen_names_postlookup(self):
        sql = f"""
            SELECT distinct upper(screen_name) as screen_name
            FROM {self.dataset_address}.user_id_lookups
            WHERE user_id is NULL
            ORDER BY screen_name
        """
        return self.execute_query(sql)

    def migrate_user_id_assignments_table(self):
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.user_id_assignments`; "
        sql += f"""
            CREATE TABLE `{self.dataset_address}.user_id_assignments` (
                screen_name STRING,
                user_id STRING,
            );
        """
        return self.execute_query(sql)

    @property
    @lru_cache(maxsize=None)
    def user_id_assignments_table(self):
        return self.client.get_table(f"{self.dataset_address}.user_id_assignments") # an API call (caches results for subsequent inserts)

    def upload_user_id_assignments(self, records):
        """
        Param: records (list of dictionaries)
        """
        rows_to_insert = [list(d.values()) for d in records]
        errors = self.client.insert_rows(self.user_id_assignments_table, rows_to_insert)
        return errors

    def migrate_populate_user_screen_names_table(self):
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.user_screen_names`; "
        sql += f"""
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.user_screen_names` as (
                SELECT DISTINCT user_id, upper(screen_name) as screen_name
                FROM (
                    SELECT DISTINCT user_id, user_screen_name as screen_name FROM `{self.dataset_address}.tweets` -- 3,636,492
                    UNION ALL
                    SELECT DISTINCT user_id, screen_name FROM `{self.dataset_address}.user_id_lookups` WHERE user_id IS NOT NULL -- 14,969
                    UNION ALL
                    SELECT DISTINCT user_id, screen_name FROM `{self.dataset_address}.user_id_assignments` -- 2,224
                ) all_user_screen_names -- 3,615,409
                ORDER BY user_id, screen_name
            );
        """
        return self.execute_query(sql)

    def migrate_populate_user_details_table_v2(self):
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.user_details_v2`; "
        sql += f"""
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.user_details_v2` as (
                SELECT
                    user_id
                    ,count(DISTINCT UPPER(screen_name)) as screen_name_count
                    ,ARRAY_AGG(DISTINCT UPPER(screen_name) IGNORE NULLS) as screen_names
                    -- ,ANY_VALUE(screen_name) as screen_name
                FROM `{self.dataset_address}.user_screen_names`
                GROUP BY 1
                ORDER BY 2 desc
                -- LIMIT 100
            );
        """
        return self.execute_query(sql)

    def migrate_populate_retweets_table_v2(self):
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.retweets_v2`; "
        sql += f"""
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.retweets_v2` as (
                SELECT
                    cast(rt.user_id as int64) as user_id
                    ,UPPER(rt.user_screen_name) as user_screen_name
                    ,rt.user_created_at

                    ,cast(sn.user_id as int64) as retweeted_user_id
                    ,UPPER(rt.retweet_user_screen_name) as retweeted_user_screen_name

                    ,rt.status_id
                    ,rt.status_text
                    ,rt.created_at
                FROM `{self.dataset_address}.retweets` rt
                JOIN `{self.dataset_address}.user_screen_names` sn
                    ON UPPER(rt.retweet_user_screen_name) = UPPER(sn.screen_name)
                WHERE rt.user_screen_name <> rt.retweet_user_screen_name -- excludes people retweeting themselves
            );
        """
        return self.execute_query(sql)

    def fetch_retweet_edges_in_batches_v2(self, topic=None, start_at=None, end_at=None):
        """
        For each retweeter, includes the number of times each they retweeted each other user.
            Optionally about a given topic.
            Optionally with within a given timeframe.

        Params:
            topic (str) : the topic they were tweeting about, like 'impeach', '#MAGA', "@politico", etc.
            start_at (str) : a date string for the earliest tweet
            end_at (str) : a date string for the latest tweet
        """
        sql = f"""
            SELECT
                rt.user_id
                ,rt.retweeted_user_id
                ,count(distinct rt.status_id) as retweet_count
            FROM `{self.dataset_address}.retweets_v2` rt
            WHERE rt.user_screen_name <> rt.retweeted_user_screen_name -- excludes people retweeting themselves
        """
        if topic:
            sql+=f"""
                AND upper(rt.status_text) LIKE '%{topic.upper()}%'
            """
        if start_at and end_at:
            sql+=f"""
                AND (rt.created_at BETWEEN '{str(start_at)}' AND '{str(end_at)}')
            """
        sql += """
            GROUP BY 1,2
        """
        return self.execute_query_in_batches(sql)

    def migrate_daily_bot_probabilities_table(self):
        sql = ""
        if self.destructive:
            sql += f"DROP TABLE IF EXISTS `{self.dataset_address}.daily_bot_probabilities`; "
        sql += f"""
            CREATE TABLE `{self.dataset_address}.daily_bot_probabilities` (
                start_date STRING,
                user_id INT64,
                bot_probability FLOAT64,
            );
        """
        return self.execute_query(sql)

    #
    # RETWEET GRAPHS V2 - BOT CLASSIFICATIONS
    #

    @property
    @lru_cache(maxsize=None)
    def daily_bot_probabilities_table(self):
        return self.client.get_table(f"{self.dataset_address}.daily_bot_probabilities") # an API call (caches results for subsequent inserts)

    def upload_daily_bot_probabilities(self, records):
        return self.insert_records_in_batches(self.daily_bot_probabilities_table, records)

    def sql_fetch_bot_ids(self, bot_min=0.8):
        sql = f"""
            SELECT DISTINCT bp.user_id
            FROM `{self.dataset_address}.daily_bot_probabilities` bp
            WHERE bp.bot_probability >= {float(bot_min)}
        """
        return sql

    def fetch_bot_ids(self, bot_min=0.8):
        """Returns any user who has ever had a bot score above the given threshold."""
        return self.execute_query(self.sql_fetch_bot_ids(bot_min))

    def fetch_bot_retweet_edges_in_batches(self, bot_min=0.8):
        """
        For each bot (user with any bot score greater than the specified threshold),
            and each user they retweeted, includes the number of times the bot retweeted them.

        Params:
            bot_min (float) consider users with any score above this threshold as bots
        """
        sql = f"""
            SELECT
                rt.user_id
                ,rt.retweeted_user_id
                ,count(distinct rt.status_id) as retweet_count
            FROM `{self.dataset_address}.retweets_v2` rt
            JOIN (
                {self.sql_fetch_bot_ids(bot_min)}
            ) bp ON bp.user_id = rt.user_id
            WHERE rt.user_screen_name <> rt.retweeted_user_screen_name -- excludes people retweeting themselves
            GROUP BY 1,2
            -- ORDER BY 1,2
        """
        return self.execute_query_in_batches(sql)

    #
    # RETWEET GRAPHS V2 - BOT COMMUNITIES
    #

    #@property
    #@lru_cache(maxsize=None) # don't cache, or cache one for each value of n_communities
    def n_bot_communities_table(self, n_communities):
        return self.client.get_table(f"{self.dataset_address}.{n_communities}_bot_communities") # an API call (caches results for subsequent inserts)

    def destructively_migrate_n_bot_communities_table(self, n_communities):
        sql = f"""
            DROP TABLE IF EXISTS `{self.dataset_address}.{n_communities}_bot_communities`;
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.{n_communities}_bot_communities` (
                user_id INT64,
                community_id INT64,
            );
        """
        return self.execute_query(sql)

    def overwrite_n_bot_communities_table(self, n_communities, records):
        self.destructively_migrate_n_bot_communities_table(n_communities)
        table = self.n_bot_communities_table(n_communities)
        return self.insert_records_in_batches(table, records)

    def download_n_bot_community_tweets_in_batches(self, n_communities):
        sql = f"""
            SELECT
                bc.community_id

                ,t.user_id
                ,t.user_name
                ,t.user_screen_name
                ,t.user_description
                ,t.user_location
                ,t.user_verified
                ,t.user_created_at

                ,t.status_id
                ,t.status_text
                ,t.retweet_status_id
                ,t.reply_user_id
                ,t.is_quote as status_is_quote
                ,t.geo as status_geo
                ,t.created_at as status_created_at

            FROM `{self.dataset_address}.{n_communities}_bot_communities` bc -- 681
            JOIN `{self.dataset_address}.tweets` t on CAST(t.user_id as int64) = bc.user_id
            -- WHERE t.retweet_status_id IS NULL
            -- ORDER BY 1,2
        """
        return self.execute_query_in_batches(sql)

    def download_n_bot_community_retweets_in_batches(self, n_communities):
        sql = f"""
            SELECT
                bc.community_id

                ,ud.user_id
                ,ud.screen_name_count as user_screen_name_count
                ,ARRAY_TO_STRING(ud.screen_names, ' | ')  as user_screen_names
                ,rt.user_created_at

                ,rt.retweeted_user_id
                ,rt.retweeted_user_screen_name

                ,rt.status_id
                ,rt.status_text
                ,rt.created_at as status_created_at

            FROM `{self.dataset_address}.{n_communities}_bot_communities` bc -- 681
            JOIN `{self.dataset_address}.user_details_v2` ud on CAST(ud.user_id  as int64) = bc.user_id
            JOIN `{self.dataset_address}.retweets_v2` rt on rt.user_id = bc.user_id
            -- ORDER BY 1,2
        """
        return self.execute_query_in_batches(sql)

    def destructively_migrate_token_frequencies_table(self, table_address, records):
        print("DESTRUCTIVELY MIGRATING TABLE:", table_address)
        sql = f"""
            DROP TABLE IF EXISTS `{table_address}`;
            CREATE TABLE IF NOT EXISTS `{table_address}` (
                token STRING,
                rank INT64,
                count INT64,
                pct FLOAT64,
                doc_count INT64,
                doc_pct FLOAT64
            );
        """
        self.execute_query(sql)
        table = self.client.get_table(table_address) # API call
        print("INSERTING", len(records), "RECORDS...")
        return self.insert_records_in_batches(table, records)

    def fetch_bot_community_profiles(self, n_communities=2):
        sql = f"""
            SELECT community_id, bot_id as user_id, user_descriptions
            FROM `{self.dataset_address}.{int(n_communities)}_community_profiles`
        """
        return self.execute_query(sql)

    def upload_bot_community_profile_tokens(self, records, community_id, n_communities=2):
        table_address = f"{self.dataset_address}.{n_communities}_community_{community_id}_profile_tokens"
        self.destructively_migrate_token_frequencies_table(table_address=table_address, records=records)

    def upload_bot_community_profile_tags(self, records, community_id, n_communities=2):
        table_address = f"{self.dataset_address}.{n_communities}_community_{community_id}_profile_tags"
        self.destructively_migrate_token_frequencies_table(table_address=table_address, records=records)

    def fetch_bot_community_statuses(self, n_communities, community_id=None, limit=None):
        sql = f"""
            SELECT community_id, user_id, status_id, status_text
            FROM `{self.dataset_address}.{int(n_communities)}_community_labeled_tweets`
        """
        if community_id:
            sql += f" WHERE community_id = {int(community_id)}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.execute_query(sql)

    def upload_bot_community_status_tokens(self, records, community_id, n_communities=2):
        table_address = f"{self.dataset_address}.{n_communities}_community_{community_id}_status_tokens"
        self.destructively_migrate_token_frequencies_table(table_address, records=records)

    def upload_bot_community_status_tags(self, records, community_id, n_communities=2):
        table_address = f"{self.dataset_address}.{n_communities}_community_{community_id}_status_tags"
        self.destructively_migrate_token_frequencies_table(table_address, records=records)

    #
    # BOT FOLLOWER GRAPHS
    #

    def destructively_migrate_user_friends_flat(self):
        sql = f"""
            DROP TABLE IF EXISTS `{self.dataset_address}.user_friends_flat`;
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.user_friends_flat` as (
                SELECT user_id, upper(screen_name) as screen_name, upper(friend_name) as friend_name
                FROM `{self.dataset_address}.user_friends`
                CROSS JOIN UNNEST(friend_names) AS friend_name
            );
        """ # 1,976,670,168 rows WAT
        return self.execute_query(sql)

    def destructively_migrate_bots_table(self, bot_min=0.8):
        bot_min_str = str(int(bot_min * 100)) #> "80"
        sql = f"""
            DROP TABLE IF EXISTS `{self.dataset_address}.bots_above_{bot_min_str}`;
            CREATE TABLE IF NOT EXISTS  `{self.dataset_address}.bots_above_{bot_min_str}` as (
            SELECT
                bp.user_id as bot_id
                ,sn.screen_name as bot_screen_name
                ,count(distinct start_date) as day_count
                ,avg(bot_probability) as avg_daily_score
            FROM `{self.dataset_address}.daily_bot_probabilities` bp
            JOIN `{self.dataset_address}.user_screen_names` sn ON CAST(sn.user_id as int64) = bp.user_id
            WHERE bp.bot_probability >= {float(bot_min)}
            GROUP BY 1,2
            ORDER BY 3 desc
        );
        """
        return self.execute_query(sql)

    def destructively_migrate_bot_followers_table(self, bot_min=0.8):
        bot_min_str = str(int(bot_min * 100)) #> "80"
        sql = f"""
            DROP TABLE IF EXISTS `{self.dataset_address}.bot_followers_above_{bot_min_str}`;
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.bot_followers_above_{bot_min_str}` as (
                SELECT
                    b.bot_id
                    ,b.bot_screen_name
                    ,uff.user_id as follower_id
                    ,uff.screen_name as follower_screen_name
                FROM `{self.dataset_address}.user_friends_flat` uff
                JOIN `{self.dataset_address}.bots_above_{bot_min_str}` b ON upper(b.bot_screen_name) = upper(uff.friend_name)
            );
        """ # 29,861,268 rows WAT
        return self.execute_query(sql)

    def fetch_bot_followers_in_batches(self, bot_min=0.8):
        """
        Returns a row for each bot for each user who follows them.
        Params: bot_min (float) consider users with any score above this threshold as bots (uses pre-computed classification scores)
        """
        bot_min_str = str(int(bot_min * 100)) #> "80"
        sql = f"""
            SELECT DISTINCT bot_id, follower_id
            FROM `{self.dataset_address}.bot_followers_above_{bot_min_str}`
        """
        return self.execute_query_in_batches(sql)

    def fetch_bot_follower_lists(self, bot_min=0.8):
        """
        Returns a row for each bot, with a list of aggregated follower ids.
        Params: bot_min (float) consider users with any score above this threshold as bots (uses pre-computed classification scores)
        """
        bot_min_str = str(int(bot_min * 100)) #> "80"
        sql = f"""
            SELECT bot_id, ARRAY_AGG(distinct follower_id) as follower_ids
            FROM `{self.dataset_address}.bot_followers_above_{bot_min_str}`
            GROUP BY 1
        """ # takes 90 seconds for ~25K rows
        return self.execute_query(sql)

    #
    # NLP (BASILICA)
    #

    @property
    @lru_cache(maxsize=None)
    def basilica_embeddings_table(self):
        return self.client.get_table(f"{self.dataset_address}.basilica_embeddings") # an API call (caches results for subsequent inserts)

    def upload_basilica_embeddings(self, records):
        return self.insert_records_in_batches(self.basilica_embeddings_table, records)

    def fetch_basilica_embedless_partitioned_statuses(self, min_val=0.0, max_val=1.0, limit=None, in_batches=False):
        """Params min_val and max_val reference partition decimal values from 0.0 to 1.0"""
        sql = f"""
            SELECT ps.status_id, ps.status_text
            FROM `{self.dataset_address}.partitioned_statuses` ps
            LEFT JOIN `{self.dataset_address}.basilica_embeddings` emb ON ps.status_id = emb.status_id
            WHERE emb.status_id IS NULL
                AND ps.partition_val BETWEEN {float(min_val)} AND {float(max_val)}
        """
        if limit:
            sql += f" LIMIT {int(limit)};"

        if in_batches:
            print("FETCHING STATUSES IN BATCHES...")
            return self.execute_query_in_batches(sql)
        else:
            print("FETCHING STATUSES...")
            return self.execute_query(sql)

    #
    # NLP (CUSTOM)
    #

    def fetch_labeled_tweets_in_batches(self, limit=None):
        sql = f"""
            SELECT
                status_id
                ,status_text
                ,community_id
                --,community_score
            FROM `{self.dataset_address}.2_community_labeled_tweets`
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
            return self.execute_query(sql)
        else:
            return self.execute_query_in_batches(sql)

    def fetch_unlabeled_statuses_in_batches(self, limit=None):
        sql = f"""
            SELECT s.status_id, s.status_text
            FROM `{self.dataset_address}.statuses` s
            LEFT JOIN `{self.dataset_address}.2_community_labeled_tweets` l ON l.status_id = s.status_id
            WHERE l.status_id IS NULL
        """
        if limit:
            sql += f" LIMIT {int(limit)};"
            return self.execute_query(sql)
        else:
            return self.execute_query_in_batches(sql)

    def destructively_migrate_2_community_predictions_table(self):
        sql = f"""
            DROP TABLE IF EXISTS `{self.dataset_address}.2_community_predictions`;
            CREATE TABLE IF NOT EXISTS `{self.dataset_address}.2_community_predictions` (
                status_id INT64,
                predicted_community_id INT64
            );
        """
        return self.execute_query(sql)

    @property
    @lru_cache(maxsize=None)
    def community_predictions_table(self):
        return self.client.get_table(f"{self.dataset_address}.2_community_predictions") # an API call (caches results for subsequent inserts)

    def upload_predictions_in_batches(self, records):
        return self.insert_records_in_batches(self.community_predictions_table, records)

    def fetch_predictions(self, limit=None):
        sql = f"""
            SELECT status_id, predicted_community_id
            FROM `{self.dataset_address}.2_community_predictions`
        """
        if limit:
            sql += f" LIMIT {int(limit)};"
            return self.execute_query(sql)
        else:
            return self.execute_query_in_batches(sql)

    #
    # API - V0
    # ... ALL ENDPOINTS MUST PREVENT SQL INJECTION

    def fetch_user_details_api_v0(self, screen_name="politico"):
        # TODO: super-charge this with cool stuff, like mention counts, average opinion score, etc.
        # TODO: create some temporary tables, to make the query faster
        sql = f"""
            SELECT
                user_id
                ,user_created_at
                ,tweet_count
                ,screen_name_count
                ,screen_names
                ,user_names
                ,user_descriptions
            FROM `{self.dataset_address}.user_details_v3`
            WHERE UPPER(@screen_name) in UNNEST(SPLIT(screen_names, '|'))
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("screen_name", "STRING", screen_name)])
        return self.client.query(sql, job_config=job_config)

    def fetch_user_tweets_api_v0(self, screen_name="politico"):
        # TODO: create some temporary tables maybe, to make the query faster
        sql = f"""
            SELECT
                t.status_id
                ,t.status_text
                ,t.created_at
                ,p.predicted_community_id as opinion_score
            FROM `{self.dataset_address}.tweets` t
            LEFT JOIN `{self.dataset_address}.2_community_predictions` p ON p.status_id = cast(t.status_id as int64)
            WHERE upper(t.user_screen_name) = upper(@screen_name)
        """
        job_config = QueryJobConfig(query_parameters=[ScalarQueryParameter("screen_name", "STRING", screen_name)])
        return self.client.query(sql, job_config=job_config)

    def fetch_users_most_retweeted_api_v0(self, metric=None, limit=None):
        """
        Params:
            metric : whether to calculate top users based on "retweet_count" or "retweeter_count"
            limit : the number of top users to return for each community (max 1,000)
        """
        metric = metric or "retweet_count"
        limit = limit or 25

        sql = f"""
            (
                SELECT community_id ,retweeted_user_screen_name ,retweeter_count , retweet_count
                FROM `{self.dataset_address}.community_0_users_most_retweeted`
                ORDER BY @metric DESC
                LIMIT @limit
            )
            UNION ALL
            (
                SELECT community_id ,retweeted_user_screen_name ,retweeter_count , retweet_count
                FROM `{self.dataset_address}.community_1_users_most_retweeted`
                ORDER BY @metric DESC
                LIMIT @limit
            )
        """
        job_config = QueryJobConfig(query_parameters=[
            ScalarQueryParameter("metric", "STRING", metric),
            ScalarQueryParameter("limit", "INT64", int(limit)),
        ])
        return self.client.query(sql, job_config=job_config)

    def fetch_statuses_most_retweeted_api_v0(self, metric=None, limit=None):
        """
        Params:
            metric : whether to calculate top statuses based on "retweet_count" or "retweeter_count"
            limit : the number of top statuses to return for each community (max 1,000)
        """
        metric = metric or "retweet_count"
        limit = limit or 25

        sql = f"""
            (
                SELECT community_id ,retweeted_user_screen_name ,status_text ,retweeter_count , retweet_count
                FROM `{self.dataset_address}.community_0_statuses_most_retweeted`
                ORDER BY @metric DESC
                LIMIT @limit
            )
            UNION ALL
            (
                SELECT community_id ,retweeted_user_screen_name ,status_text ,retweeter_count , retweet_count
                FROM `{self.dataset_address}.community_1_statuses_most_retweeted`
                ORDER BY @metric DESC
                LIMIT @limit
            )
        """
        job_config = QueryJobConfig(query_parameters=[
            ScalarQueryParameter("metric", "STRING", metric),
            ScalarQueryParameter("limit", "INT64", int(limit)),
        ])
        return self.client.query(sql, job_config=job_config)

    def fetch_top_profile_tokens_api_v0(self, limit=None):
        """
        Params: limit : the number of top tokens to return for each community
        """
        limit = limit or 20

        sql = f"""
            (
                SELECT 0 as community_id, token, rank, count, pct
                FROM `{self.dataset_address}.2_community_0_profile_tokens`
                ORDER BY rank
                LIMIT @limit
            )
            UNION ALL
            (
                SELECT 1 as community_id, token, rank, count, pct
                FROM `{self.dataset_address}.2_community_1_profile_tokens`
                ORDER BY rank
                LIMIT @limit
            )
        """
        job_config = QueryJobConfig(query_parameters=[ScalarQueryParameter("limit", "INT64", int(limit))])
        return self.client.query(sql, job_config=job_config)

    def fetch_top_profile_tags_api_v0(self, limit=None):
        """
        Params: limit : the number of top tags to return for each community
        """
        limit = limit or 20

        sql = f"""
            (
                SELECT 0 as community_id, token, rank, count, pct
                FROM `{self.dataset_address}.2_community_0_profile_tags`
                ORDER BY rank
                LIMIT @limit
            )
            UNION ALL
            (
                SELECT 1 as community_id, token, rank, count, pct
                FROM `{self.dataset_address}.2_community_1_profile_tags`
                ORDER BY rank
                LIMIT @limit
            )
        """
        job_config = QueryJobConfig(query_parameters=[ScalarQueryParameter("limit", "INT64", int(limit))])
        return self.client.query(sql, job_config=job_config)

    def fetch_top_status_tokens_api_v0(self, limit=None):
        """
        Params: limit : the number of top tokens to return for each community
        """
        limit = limit or 50

        sql = f"""
            (
                SELECT 0 as community_id, token, rank, count, pct, doc_count, doc_pct
                FROM `{self.dataset_address}.2_community_0_status_tokens`
                ORDER BY rank
                LIMIT @limit
            )
            UNION ALL
            (
                SELECT 1 as community_id, token, rank, count, pct, doc_count, doc_pct
                FROM `{self.dataset_address}.2_community_1_status_tokens`
                ORDER BY rank
                LIMIT @limit
            )
        """
        job_config = QueryJobConfig(query_parameters=[ScalarQueryParameter("limit", "INT64", int(limit))])
        return self.client.query(sql, job_config=job_config)

    def fetch_top_status_tags_api_v0(self, limit=None):
        """
        Params: limit : the number of top tokens to return for each community
        """
        limit = limit or 50

        sql = f"""
            (
                SELECT 0 as community_id, token, rank, count, pct, doc_count, doc_pct
                FROM `{self.dataset_address}.2_community_0_status_tags`
                ORDER BY rank
                LIMIT @limit
            )
            UNION ALL
            (
                SELECT 1 as community_id, token, rank, count, pct, doc_count, doc_pct
                FROM `{self.dataset_address}.2_community_1_status_tags`
                ORDER BY rank
                LIMIT @limit
            )
        """
        job_config = QueryJobConfig(query_parameters=[ScalarQueryParameter("limit", "INT64", int(limit))])
        return self.client.query(sql, job_config=job_config)

    #
    # RETWEET GRAPHS V3
    #

    def fetch_retweet_edges_v3(self, start_at=None, end_at=None, topic=None):
        """For querying against the analysis DB"""
        sql = f"""
            SELECT
                user_id
                ,retweeted_user_id
                ,count(distinct status_id) as retweet_count
            FROM `{self.dataset_address}.tweets`
            WHERE retweeted_status_id is not null
                AND user_id <> retweeted_user_id -- excludes people retweeting themselves
        """
        if start_at and end_at:
            sql += f" AND created_at BETWEEN '{start_at}' and '{end_at}' "
        if topic:
            sql += f" AND upper(status_text) LIKE '%{topic.upper()}%' "
        sql += " GROUP BY 1,2 "
        return self.execute_query(sql)






if __name__ == "__main__":

    service = BigQueryService()

    print(f"  CLEANUP MODE: {CLEANUP_MODE}")
    if CLEANUP_MODE:
        service.delete_temp_tables_older_than(days=3)
        seek_confirmation()

    print("--------------------")
    print("FETCHED TOPICS:")
    print([row.topic for row in service.fetch_topics()])

    sql = f"SELECT count(distinct status_id) as tweet_count FROM `{service.dataset_address}.tweets`"
    results = service.execute_query(sql)
    print("--------------------")
    tweet_count = list(results)[0].tweet_count
    print(f"FETCHED {fmt_n(tweet_count)} TWEETS")

    print("--------------------")
    sql = f"SELECT count(distinct user_id) as user_count FROM `{service.dataset_address}.tweets`"
    results = service.execute_query(sql)
    user_count = list(results)[0].user_count
    print(f"FETCHED {fmt_n(user_count)} USERS")

    results = service.user_friend_collection_progress()
    row = list(results)[0]
    collected_count = row.user_count
    pct = collected_count / user_count
    #print("--------------------")
    #print("USERS COLLECTED:", collected_count)
    #print("  PCT COLLECTED:", f"{(pct * 100):.1f}%")
    #print("  AVG DURATION:", row.avg_duration)
    if collected_count > 0:
        print("--------------------")
        print(f"USERS WITH FRIENDS: {row.pct_friendly * 100}%")
        print("  AVG FRIENDS:", round(row.avg_friends_friendly))
        #print("  AVG DURATION:", row.avg_duration_friendly)
