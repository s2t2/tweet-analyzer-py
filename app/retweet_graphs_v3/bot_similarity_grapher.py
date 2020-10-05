
import os
from functools import lru_cache

from networkx import jaccard_coefficient, Graph

from app import seek_confirmation
from app.job import Job
from app.decorators.number_decorators import fmt_n

BATCH_SIZE = int(os.getenv("BATCH_SIZE", default="25000"))

class BotSimilarityGrapher(Job):
    def __init__(self, bot_ids, bot_retweet_graph, batch_size=BATCH_SIZE):
        """Params:

            bot_ids (list) a unique list of bot ids, which should all be included as nodes in the bot retweet graph.
                The retweet graph will also contain retweeted users. So that's why we need a separate list.
                The bot ids will be used as nodes in the similarity graph.

            bot_retweet_graph (networkx.DiGraph) a retweet graph between all the bots and all the users they retweeted, with edge weight as the retweet count
        """
        self.bot_ids = bot_ids
        self.bot_retweet_graph = bot_retweet_graph

        self.batch_size = batch_size

        print("BOT SIMILARITY GRAPHER...")
        print("  BATCH SIZE:", self.batch_size)

    @property
    @lru_cache(maxsize=None)
    def jaccard_results(self):
        self.start()
        node_pairs = []
        for i, bot_id in enumerate(self.bot_ids):
            for other_bot_id in self.bot_ids[i+1:]:
                if self.bot_retweet_graph.has_node(other_bot_id) and self.bot_retweet_graph.has_node(bot_id):
                    node_pairs.append((bot_id, other_bot_id))
        # could maybe just take the combinations between all nodes in the bot graph
        # because we can assume they were assembled using the same bot ids as the ones here
        # but the point is to be methodologically sound and it doesn't take that long
        print("NODE PAIRS:", fmt_n(len(node_pairs)))

        results = jaccard_coefficient(self.bot_retweet_graph.to_undirected(), node_pairs)
        #> returns an iterator of 3-tuples in the form (u, v, p)
        #> where (u, v) is a pair of nodes and p is their Jaccard coefficient.
        print("JACCARD COEFFICIENTS BETWEEN EACH NODE PAIR - COMPLETE!") #, fmt_n(len(list(results))))
        self.end()
        return results

    def perform(self):
        """ Returns a similarity graph (networkx.Graph), where the similarity is based on the Jaccard index.
            For each pair of bots we calculate the Jaccard index based on the sets of people they retweet.
            If two bots retweet exactly the same users, their Jaccard index is one.
            If they don't retweet anyone in common, their Jaccard index is zero.
        """
        self.jaccard_results
        self.start()
        print("CONSTRUCTING SIMILARITY GRAPH...")
        self.similarity_graph = Graph()

        for bot_id, other_bot_id, similarity_score in self.jaccard_results:
            if similarity_score > 0:
                self.similarity_graph.add_edge(bot_id, other_bot_id, weight=similarity_score)
                #edge_count += 1

            self.counter += 1
            if self.counter % self.batch_size == 0:
                self.progress_report()

        self.end()
        return self.similarity_graph
