
import os
from collections import Counter

from pandas import DataFrame, read_csv
import re

from app.bq_service import BigQueryService
from app.file_storage import FileStorage
from app.job import Job
from app.decorators.number_decorators import fmt_n

LIMIT = os.getenv("LIMIT") # 1000 # None  # os.getenv("LIMIT")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", default="25_000")) # 100
DESTRUCTIVE = (os.getenv("DESTRUCTIVE", default="false") == "true") # True
TAGS_DESTRUCTIVE = (os.getenv("TAGS_DESTRUCTIVE", default="false") == "true") # True

TWITTER_PATTERN = r'[^a-zA-Z ^0-9 # @]' # alphanumeric, plus hashtag and handle symbols (twitter-specific)

def download_tweets():
    job = Job()
    bq_service = BigQueryService()

    job.start()
    records = []
    for row in bq_service.fetch_statuses_with_tags(limit=LIMIT):
        #print(row)
        records.append(dict(row))

        job.counter +=1
        if job.counter % BATCH_SIZE == 0:
            job.progress_report()
    job.end()

    return DataFrame(records)

def parse_hashtags(status_text):
    txt = re.sub(TWITTER_PATTERN, "", status_text.upper())
    tags = [token.upper() for token in status_text.split() if token.startswith("#") and not token.endswith("#")]
    return tags

def summarize_token_frequencies(token_sets, rank_metric="token_count"):
    """
    Param token_sets : a list of tokens for each document in a collection

    Returns a DataFrame with a row per topic and columns for various TF/IDF-related scores.
    """
    print("COMPUTING TOKEN AND DOCUMENT FREQUENCIES...")

    token_counter = Counter()
    doc_counter = Counter()

    for tokens in token_sets:
        token_counter.update(tokens)
        doc_counter.update(set(tokens)) # removes duplicate tokens so they only get counted once per doc!

    df = DataFrame(zip(doc_counter.keys(), doc_counter.values()), columns=["token", "doc_count"]).merge(
        DataFrame(zip(token_counter.keys(), token_counter.values()), columns=["token", "token_count"]), on="token"
    )

    df["token_pct"] = df["token_count"] / df["token_count"].sum()
    df["doc_pct"] = df["doc_count"] / len(token_sets)

    #df["naive_tfidf"] = df["token_count"] / (1 - df["doc_count"]) # not sure about the denominator

    df["rank"] = df[rank_metric].rank(method="first", ascending=False)

    return df.reindex(columns=["token", "rank", "token_count", "token_pct", "doc_count", "doc_pct"]).sort_values(by="rank")


if __name__ == "__main__":

    storage = FileStorage(dirpath="bot_analysis")

    tweets_csv_filepath = os.path.join(storage.local_dirpath, "statuses_with_tags.csv")
    if os.path.isfile(tweets_csv_filepath) and not DESTRUCTIVE:
        print("LOADING TWEETS...")
        tweets_df = read_csv(tweets_csv_filepath)
    else:
        print("DOWNLOADING TWEETS...")
        tweets_df = download_tweets()
        print("TOKENIZING TWEETS...")
        tweets_df["status_tags"] = tweets_df["status_text"].apply(parse_hashtags)
        print(tweets_df.head())
        tweets_df.to_csv(tweets_csv_filepath, index=False)
    print(fmt_n(len(tweets_df)))
    print(tweets_df.head())




    breakpoint()

    print("----------------------")
    print("ANALYZING TWEETS...")

    tags_csv_filepath = os.path.join(storage.local_dirpath, "top_tags.csv")
    if os.path.isfile(tags_csv_filepath) and not TAGS_DESTRUCTIVE:
        print("LOADING TOP TAGS...")
        tags_df = read_csv(tags_csv_filepath)
    else:
        print("SUMMARIZING...")
        tags_df = summarize_token_frequencies(tweets_df["status_tags"].tolist())
        tags_df.head(1000).to_csv(tags_csv_filepath, index=False)
    print(tags_df.head())

    for is_bot, filtered_df in tweets_df.groupby(["is_bot"]):
        bot_or_human = {True: "bot", False: "human"}[is_bot]
        tags_csv_filepath = os.path.join(storage.local_dirpath, f"top_tags_{bot_or_human}.csv")
        print(bot_or_human.upper())

        bot_or_human_tags_df = summarize_token_frequencies(filtered_df["status_tags"].tolist())
        print(bot_or_human_tags_df.head())
        bot_or_human_tags_df.head(1000).to_csv(tags_csv_filepath, index=False)
