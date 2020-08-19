import os
#from pprint import pprint
from collections import Counter

import numpy as np
import pandas as pd
import re
import spacy
from nltk.corpus import stopwords
from spacy.lang.en.stop_words import STOP_WORDS as SPACY_STOP_WORDS
from gensim.parsing.preprocessing import STOPWORDS as GENSIM_STOPWORDS
#from spacy.tokenizer import Tokenizer
from nltk.stem import PorterStemmer

import matplotlib.pyplot as plt
import squarify
#import plotly.express as px

from app import APP_ENV, seek_confirmation
from app.bot_communities.bot_retweet_grapher import BotRetweetGrapher
from app.bot_communities.clustering import K_COMMUNITIES
from app.decorators.datetime_decorators import s_to_date #dt_to_s, logstamp, dt_to_date, s_to_dt
#from app.decorators.number_decorators import fmt_n

STOP_WORDS = set(stopwords.words("english")) | SPACY_STOP_WORDS | GENSIM_STOPWORDS | {
    "rt", "httpstco", "amp",
    #"impeach", "impeachment", "impeached", "president", "rep", "presidents",
    # "trump", "articles", "trial", "house", "senate"
    "today", "tonight", "tomorrow", "time", "ago",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "want", "wants", "like", "says", "told",
    "th", "im", "hes", "hi", "thi"
}
STOP_WORDS = STOP_WORDS | set([stop_word.replace("'","") for stop_word in STOP_WORDS if "'" in stop_word]) # adds "dont" version of "don't"

print("----------------")
print("STOP WORDS:", sorted(list(STOP_WORDS)))

ALPHANUMERIC_PATTERN = r'[^a-zA-Z ^0-9]'  # same as "[^a-zA-Z ^0-9]"

#class WordcloudMaker:
#    def __init__(self):
#        self.ps = PorterStemmer()
#        self.nlp = spacy.load("en_core_web_md")
#        self.stop_words = STOP_WORDS

ps = PorterStemmer()
print("PORTER STEMMER", type(ps))

#nlp = spacy.load("en_core_web_lg")
nlp = spacy.load("en_core_web_md")
print("NLP", type(nlp))

def custom_stem(token):
    if token in ["impeach", "impeachment", "impeached"]:
        token = "impeach"
    if token in ["trump", "trumps"]:
        token = "trump"
    return token

def tokenize(doc):
    """
    Params: doc (str) the document to tokenize
    Returns: a list of tokens like ["___", "_____", "____"]
    """
    doc = doc.lower() # normalize case
    doc = re.sub(ALPHANUMERIC_PATTERN, "", doc)  # keep only alphanumeric characters
    tokens = doc.split()
    tokens = [token for token in tokens if token not in STOP_WORDS] # remove stopwords
    return tokens

def tokenize_porter_stems(doc):
    """
    Params: doc (str) the document to tokenize
    Returns: a list of stems like ["___", "_____", "____"]
    """
    doc = doc.lower() # normalize case
    doc = re.sub(ALPHANUMERIC_PATTERN, "", doc)  # keep only alphanumeric characters
    tokens = doc.split()
    tokens = [token for token in tokens if token not in STOP_WORDS] # remove stopwords
    stems = [ps.stem(token) for token in tokens]  # word stems only
    stems = [stem for stem in stems if stem not in STOP_WORDS] # remove stopwords again
    return stems

def tokenize_custom_stems(doc):
    """
    Params: doc (str) the document to tokenize
    Returns: a list of stems like ["___", "_____", "____"]
    """
    doc = doc.lower() # normalize case
    doc = re.sub(ALPHANUMERIC_PATTERN, "", doc)  # keep only alphanumeric characters
    tokens = doc.split()
    tokens = [token for token in tokens if token not in STOP_WORDS] # remove stopwords
    stems = [custom_stem(token) for token in tokens]  # custom word stems only
    stems = [stem for stem in stems if stem not in STOP_WORDS] # remove stopwords again
    return stems

def tokenize_spacy_lemmas(doc):
    """
    Params:
        my_doc (str) the document to tokenize
        my_nlp (spacy.lang.en.English) one of spacy's natural language models
    Returns: a list of tokens
    """
    doc = nlp(doc) #> <class 'spacy.tokens.doc.Doc'>
    lemmas = [token.lemma_.lower() for token in doc if token.is_stop == False
                                                    and token.is_punct == False
                                                    and token.is_space == False
                                                    and token not in STOP_WORDS] # double stopword removal!!!

    return lemmas












def summarize(token_sets):
    """
    Param: token_sets a list of token lists
    """

    print("COMPILING TOKEN SUMMARY TABLE...")
    token_counter = Counter()
    doc_counter = Counter()

    for tokens in token_sets:
        token_counter.update(tokens)
        # removes duplicate tokens so they only get counted once per doc!
        doc_counter.update(set(tokens))

    token_counts = zip(token_counter.keys(), token_counter.values())
    doc_counts = zip(doc_counter.keys(), doc_counter.values())

    token_df = pd.DataFrame(token_counts, columns=["token", "count"])
    doc_df = pd.DataFrame(doc_counts, columns=["token", "doc_count"])

    df = doc_df.merge(token_df, on="token")
    total_tokens = df["count"].sum()
    total_docs = len(token_sets)

    df["rank"] = df["count"].rank(method="first", ascending=False)

    # df["token_count"].apply(lambda x: x / total_tokens)
    df["pct"] = df["count"] / total_tokens

    df = df.sort_values(by="rank")
    df["running_pct"] = df["pct"].cumsum()

    # df["doc_count"].apply(lambda x: x / total_docs)
    df["doc_pct"] = df["doc_count"] / total_docs

    ordered_columns = ["token", "rank", "count", "pct", "running_pct", "doc_count", "doc_pct"]
    return df.reindex(columns=ordered_columns).sort_values(by="rank")


if __name__ == "__main__":

    print("----------------")
    print("K COMMUNITIES:", K_COMMUNITIES)

    grapher = BotRetweetGrapher()
    local_dirpath = os.path.join(grapher.local_dirpath, "k_communities", str(K_COMMUNITIES)) # dir should be already made by cluster maker
    if not os.path.exists(local_dirpath):
        os.makedirs(local_dirpath)

    print("----------------")
    print("LOADING RETWEETS...")
    local_csv_filepath = os.path.join(local_dirpath, "retweets.csv")
    print(os.path.abspath(local_csv_filepath))
    df = pd.read_csv(local_csv_filepath)
    print(df.head())

    print("----------------")
    print("TRANSFORMING RETWEETS...")
    df["status_created_date"] = df["status_created_at"].apply(s_to_date)

    print("----------------")
    print("GENERATING WORDCLOUDS...")
    local_wordclouds_dirpath = os.path.join(local_dirpath, "wordclouds")
    if not os.path.exists(local_wordclouds_dirpath):
        os.makedirs(local_wordclouds_dirpath)

    for group_name, filtered_df in df.groupby(["status_created_date", "community_id"]):
        date = group_name[0]
        community_id = group_name[1]
        print(date, community_id)

        # TOKENIZE

        status_tokens = filtered_df["status_text"].apply(lambda txt: tokenize_spacy_lemmas(txt))
        print(status_tokens)
        status_tokens = status_tokens.values.tolist()

        # SUMMARIZE

        print("TOP TOKENS:")
        pivot_df = summarize(status_tokens)
        top_tokens_df = pivot_df[pivot_df["rank"] <= 20]
        print(top_tokens_df)

        print("PLOTTING TOP TOKENS...")
        chart_title = f"Word Cloud for Community {community_id} on '{date}'"
        local_wordcloud_filepath = os.path.join(local_wordclouds_dirpath, f"{date}-community-{community_id}.png")
        print(os.path.abspath(local_wordcloud_filepath))

        squarify.plot(sizes=top_tokens_df["pct"], label=top_tokens_df["token"], alpha=0.8)
        plt.title(chart_title)
        plt.axis("off")
        if APP_ENV == "development":
            plt.show()
        plt.savefig(local_wordcloud_filepath)
        # why are previous chart's words showing up? need to clear plt or something?
        plt.clf()

        #top_tokens_df.sort_values("Retweet Count", ascending=True, inplace=True)
        #fig = px.treemap(top_tokens_df, values="token", title=chart_title)
        #if APP_ENV == "development":
        #    fig.show()
        #fig.write_image(local_wordcloud_filepath)

        seek_confirmation()