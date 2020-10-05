
import os
import datetime
import time
from functools import lru_cache

from dotenv import load_dotenv
import numpy as np
from pandas import DataFrame
import matplotlib.pyplot as plt

from conftest import compile_mock_rt_graph
from app import APP_ENV
from app.decorators.number_decorators import fmt_n, fmt_pct
from app.friend_graphs.graph_analyzer import GraphAnalyzer
from app.botcode_v2.network_classifier_helper import getLinkDataRestrained as get_link_data_restrained # TODO: deprecate
from app.botcode_v2.network_classifier_helper import psi as link_energy
from app.botcode_v2.network_classifier_helper import computeH as compute_energy_graph
from app.botcode_v2.network_classifier_helper import compute_bot_probabilities

load_dotenv()

DRY_RUN = (os.getenv("DRY_RUN", default="true") == "true")

MU = float(os.getenv("MU", default="1"))
ALPHA_PERCENTILE = float(os.getenv("ALPHA_PERCENTILE", default="0.999"))

LAMBDA_00 = float(os.getenv("LAMBDA_00", default="0.61")) # TODO: interpretation of what this means
LAMBDA_11 = float(os.getenv("LAMBDA_11", default="0.83")) # TODO: interpretation of what this means

class NetworkClassifier:
    def __init__(self, rt_graph, weight_attr="weight", mu=MU, alpha_percentile=ALPHA_PERCENTILE, lambda_00=LAMBDA_00, lambda_11=LAMBDA_11):
        """
        Takes all nodes in a retweet graph and assigns each user a score from 0 (human) to 1 (bot).
        Then writes the results to CSV file.
        """
        self.rt_graph = rt_graph
        self.weight_attr = weight_attr

        # PARAMS FOR THE LINK ENERGY FUNCTION...
        self.mu = mu
        self.alpha_percentile = alpha_percentile
        self.lambda_00 = lambda_00
        self.lambda_11 = lambda_11
        self.epsilon = 10**(-3) #> 0.001
        #self.lambda_01 = 1
        #self.lambda_10 = self.lambda_00 + self.lambda_11 - self.lambda_01 + self.epsilon

        # ARTIFACTS OF THE BOT CLASSIFICATION PROCESS...
        self.energy_graph = None
        self.bot_ids = None
        self.user_data = None

    @property
    @lru_cache(maxsize=None)
    def links(self):
        """TODO: deprecate"""
        print("-----------------")
        print("LINKS...")
        return get_link_data_restrained(self.rt_graph, weight_attr=self.weight_attr)

    @property
    @lru_cache(maxsize=None)
    def in_degrees(self):
        return self.rt_graph.in_degree(weight=self.weight_attr)

    @property
    @lru_cache(maxsize=None)
    def out_degrees(self):
        return self.rt_graph.out_degree(weight=self.weight_attr)

    @property
    @lru_cache(maxsize=None)
    def alpha(self):
        """Params for the link_energy function"""
        in_degrees_list = [v for _,v in self.in_degrees]
        out_degrees_list = [v for _,v in self.out_degrees]
        print("MAX IN:", fmt_n(max(in_degrees_list))) #> 76,617
        print("MAX OUT:", fmt_n(max(out_degrees_list))) #> 5,608

        alpha_in = np.quantile(in_degrees_list, self.alpha_percentile)
        alpha_out = np.quantile(out_degrees_list, self.alpha_percentile)
        print("ALPHA IN:", fmt_n(alpha_in)) #> 2,252
        print("ALPHA OUT:", fmt_n(alpha_out)) #> 1,339

        return [self.mu, alpha_out, alpha_in]

    @property
    @lru_cache(maxsize=None)
    def link_energies(self):
        """TODO: refactor by looping through the edges in the RT graph instead....
            link[0] is the edge[0]
            link[1] is the edge[1]
            link[4] is the weight attr value
        """
        print("-----------------")
        print("ENERGIES...")
        return [(
            link[0],
            link[1],
            link_energy(
                link[0], link[1], link[4],
                self.in_degrees, self.out_degrees,
                self.alpha, self.lambda_00, self.lambda_11, self.epsilon
            )
        ) for link in self.links]

    @property
    @lru_cache(maxsize=None)
    def prior_probabilities(self):
        return dict.fromkeys(list(self.rt_graph.nodes), 0.5) # set all screen names to 0.5

    def compile_energy_graph(self):
        print("COMPILING ENERGY GRAPH...")
        self.energy_graph, self.bot_ids, self.user_data = compute_energy_graph(self.rt_graph, self.prior_probabilities, self.link_energies, self.out_degrees, self.in_degrees)
        #self.human_names = list(set(self.rt_graph.nodes()) - set(self.bot_ids))
        print("-----------------")
        print("ENERGY GRAPH:", type(self.energy_graph))
        print("NODE COUNT:", fmt_n(self.energy_graph.number_of_nodes()))
        print(f"BOT COUNT: {fmt_n(len(self.bot_ids))} ({fmt_pct(len(self.bot_ids) / self.energy_graph.number_of_nodes())})")
        print("USER DATA:", fmt_n(len(self.user_data.keys())))

    @property
    @lru_cache(maxsize=None)
    def bot_probabilities(self):
        if not self.energy_graph and not self.bot_ids:
            self.compile_energy_graph()

        return compute_bot_probabilities(self.rt_graph, self.energy_graph, self.bot_ids)

    @property
    @lru_cache(maxsize=None)
    def bot_probabilities_df(self):
        df = DataFrame(list(self.bot_probabilities.items()), columns=["user_id", "bot_probability"])
        df.index.name = "row_id"
        df.index = df.index + 1
        print("--------------------------")
        print("CLASSIFICATION COMPLETE!")
        print(df.head())
        print("... < 50% (NOT BOTS):",    fmt_n(len(df[df["bot_probability"] < 0.5])))
        print("... = 50% (NOT BOTS):",    fmt_n(len(df[df["bot_probability"] == 0.5])))
        print("... > 50% (MAYBE BOTS):",  fmt_n(len(df[df["bot_probability"] > 0.5])))
        print("... > 60% (MAYBE BOTS):",  fmt_n(len(df[df["bot_probability"] > 0.6])))
        print("... > 70% (MAYBE BOTS):",  fmt_n(len(df[df["bot_probability"] > 0.7])))
        print("... > 80% (MAYBE BOTS):",  fmt_n(len(df[df["bot_probability"] > 0.8])))
        print("... > 90% (LIKELY BOTS):", fmt_n(len(df[df["bot_probability"] > 0.9])))
        return df

    def generate_bot_probabilities_histogram(self, img_filepath=None, show_img=None, title="Bot Probability Scores"):
        show_img = show_img or (APP_ENV == "development")

        probabilities = self.bot_probabilities_df["bot_probability"]
        num_bins = round(len(probabilities) / 10)
        counts, bin_edges = np.histogram(probabilities, bins=num_bins) # ,normed=True #> "VisibleDeprecationWarning: Passing `normed=True` on non-uniform bins has always been broken"...
        cdf = np.cumsum(counts)

        plt.plot(bin_edges[1:], cdf / cdf[-1])
        plt.grid()
        plt.xlabel("Bot probability")
        plt.ylabel("CDF")

        plt.hist(probabilities[probabilities < 0.5])
        plt.hist(probabilities[probabilities > 0.5])
        plt.grid()
        plt.xlabel("Bot probability (0.5 excluded)")
        plt.ylabel("Frequency")
        plt.title(title)

        if img_filepath:
            plt.savefig(img_filepath)

        if show_img:
            plt.show()

if __name__ == "__main__":

    manager = GraphAnalyzer()

    #
    # LOAD RT GRAPH
    #

    if DRY_RUN:
        rt_graph = compile_mock_rt_graph()
        print("RT GRAPH:", type(rt_graph))
        print("  NODES:", fmt_n(rt_graph.number_of_nodes()))
        print("  EDGES:", fmt_n(rt_graph.number_of_edges()))
    else:
        rt_graph = manager.graph
        manager.report()

    if APP_ENV == "development":
        if input("CONTINUE? (Y/N): ").upper() != "Y":
            print("EXITING...")
            exit()

    #
    # PERFORM BOT CLASSIFICATION
    #

    classifier = Classifier(rt_graph, weight_attr="rt_count")

    df = classifier.bot_probabilities_df

    #
    # SAVE ARTIFACTS
    #

    artifacts_dir = os.path.join(manager.local_dirpath, "botcode_v2")
    if not os.path.isdir(artifacts_dir):
        os.mkdir(artifacts_dir)

    if DRY_RUN:
        csv_filepath = os.path.join(artifacts_dir, "mock_probabilities.csv")
        img_filepath = os.path.join(artifacts_dir, "mock_probabilities_histogram.png")
    else:
        csv_filepath = os.path.join(artifacts_dir, f"bot_probabilities_{classifier.lambda_00}_{classifier.lambda_11}.csv")
        img_filepath = os.path.join(artifacts_dir, f"bot_probabilities_{classifier.lambda_00}_{classifier.lambda_11}_histogram.png")

    print("----------------")
    print("SAVING CSV FILE...")
    print(csv_filepath)
    df.to_csv(csv_filepath)

    print("----------------")
    print("SAVING HISTOGRAM...")
    print(img_filepath)
    classifier.generate_bot_probabilities_histogram(img_filepath=img_filepath, show_img=(APP_ENV=="development"))
