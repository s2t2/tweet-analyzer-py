import os

from networkx import DiGraph

from app import seek_confirmation
from app.decorators.datetime_decorators import dt_to_s
from app.retweet_graphs_v3.date_range_generator import DateRangeGenerator
from app.retweet_graphs_v3.file_storage import FileStorage
from app.retweet_graphs_v3.retweet_grapher import RetweetGrapher
from app.botcode_v2.classifier import NetworkClassifier as BotClassifier
from app.retweet_graphs_v3.bot_similarity_grapher import BotSimilarityGrapher

RETWEET_GRAPH_FILENAME = "retweet_graph.gpickle"
BOTS_FILENAME = "bot_probabilities.csv"
BOTS_HISTOGRAM_FILENAME = "bot_probabilities_histogram.png"

BOT_MIN = float(os.getenv("BOT_MIN", default="0.7"))
BOT_RETWEET_GRAPH_FILENAME = "bot_retweet_graph.gpickle"
BOT_SIMILARITY_GRAPH_FILENAME = "bot_similarity_graph.gpickle"

if __name__ == "__main__":

    generator = DateRangeGenerator()
    n_days = generator.n_days

    for date_range in generator.date_ranges:
        start_date = date_range.start_date
        end_date = date_range.end_date
        print("START:", start_date)
        print("END:", end_date)

        storage_dirpath = f"retweet_graphs_v3/n_days/{n_days}/{start_date}"
        storage = FileStorage(dirpath=storage_dirpath)

        #
        # BOT CLASSIFICATION
        #

        if storage.local_file_exists(RETWEET_GRAPH_FILENAME):
            retweet_graph = storage.load_gpickle(RETWEET_GRAPH_FILENAME)
        else:
            retweet_graph = RetweetGrapher(start_date=dt_to_s(date_range.start_at), end_date=dt_to_s(date_range.end_at)).perform()
            storage.save_gpickle(retweet_graph, filename=RETWEET_GRAPH_FILENAME)

        if storage.local_file_exists(BOTS_FILENAME):
            bots_df = storage.load_df(BOTS_FILENAME)
        else:
            bot_classifier = BotClassifier(retweet_graph, weight_attr="weight")

            bots_df = bot_classifier.bot_probabilities_df.copy()
            bots_df = bots_df[bots_df["bot_probability"] > 0.5]
            storage.save_df(bots_df, BOTS_FILENAME)

            bot_classifier.generate_bot_probabilities_histogram(
                title=f"Bot Probability Scores for Period {start_date} - {end_date}",
                img_filepath=storage.local_filepath(BOTS_HISTOGRAM_FILENAME))
            storage.upload_file(BOTS_HISTOGRAM_FILENAME)

            ## UPLOAD SELECTED ROWS TO BIG QUERY (IF POSSIBLE, OTHERWISE CAN ADD FROM GCS LATER)
            #try:
            #    bots_df = clf.bot_probabilities_df[clf.bot_probabilities_df["bot_probability"] > 0.5]
            #    records = [{**{"start_date": date_range.start_date}, **record}
            #                for record in bots_df.to_dict("records")]
            #    print("UPLOADING", len(records), "BOT SCORES TO BQ...")
            #    bq_service.upload_daily_bot_probabilities(records)
            #
            #except Exception as err:
            #    print("OOPS", err)

        #
        # BOT COMMUNITIES
        #

        seek_confirmation() # might want to review the histogram and choose a different bot min and start over #TODO: automatically choose the bot min. a reasonable percentage is 1% of all users
        bot_ids = bots_df[bots_df["bot_probability"] > BOT_MIN]["user_id"].tolist()

        if storage.local_file_exists(BOT_RETWEET_GRAPH_FILENAME):
            bot_retweet_graph = storage.load_gpickle(BOT_RETWEET_GRAPH_FILENAME)
        else:
            bot_retweet_graph = DiGraph()
            for user_id, retweeted_user_id, data in retweet_graph.edges(data=True):
                if user_id in bot_ids:
                    bot_retweet_graph.add_edge(user_id, retweeted_user_id, weight=data["weight"])
            storage.save_gpickle(bot_retweet_graph, filename=BOT_RETWEET_GRAPH_FILENAME)

        if storage.local_file_exists(BOT_SIMILARITY_GRAPH_FILENAME):
            bot_similarity_graph = storage.load_gpickle(BOT_SIMILARITY_GRAPH_FILENAME)
        else:
            bot_similarity_graph = BotSimilarityGrapher(bot_ids=bot_ids, bot_retweet_graph=bot_retweet_graph).perform()
            storage.save_gpickle(bot_similarity_graph, filename=BOT_SIMILARITY_GRAPH_FILENAME)
