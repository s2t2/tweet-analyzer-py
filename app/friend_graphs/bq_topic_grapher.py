
import os

from networkx import DiGraph
from memory_profiler import profile
from dotenv import load_dotenv

from app.decorators.datetime_decorators import logstamp
from app.decorators.number_decorators import fmt_n
from app.friend_graphs.bq_grapher import BigQueryGrapher

load_dotenv()

USERS_LIMIT = int(os.getenv("USERS_LIMIT", default="1000")) # forces us to have a limit, unlike the base grapher version
TOPIC = os.getenv("TOPIC", default="impeach")
START_AT = os.getenv("START_AT", default="2020-01-01 01:00:00") # On 1/15, The House of Representatives names seven impeachment managers and votes to transmit articles of impeachment to the Senate
END_AT = os.getenv("END_AT", default="2020-01-30 01:00:00")

class BigQueryTopicGrapher(BigQueryGrapher):

    def __init__(self, users_limit=USERS_LIMIT, topic=TOPIC, convo_start_at=START_AT, convo_end_at=END_AT,
                bq_service=None, gcs_service=None):
        super().__init__(bq_service=bq_service, gcs_service=gcs_service)
        self.users_limit = users_limit
        self.topic = topic
        self.convo_start_at = convo_start_at
        self.convo_end_at = convo_end_at

        print("---------------------------------------")
        print("CONVERSATION FILTERS...")
        print(f"  USERS LIMIT: {self.users_limit}")
        print(f"  TOPIC: '{self.topic.upper()}' ")
        print(f"  BETWEEN: '{self.convo_start_at}' AND '{self.convo_end_at}'")

    @property
    def metadata(self):
        return {**super().metadata, **{"conversation": {
            "users_limit": self.users_limit,
            "topic": self.topic,
            "start_at": self.convo_start_at,
            "end_at": self.convo_end_at,
        }}} # merges dicts

    @profile
    def perform(self):
        self.write_metadata_to_file()
        self.upload_metadata()

        self.start()
        self.graph = DiGraph()
        self.running_results = []

        users = list(self.bq_service.fetch_random_users(limit=self.users_limit, topic=self.topic,
                                                        start_at=self.convo_start_at, end_at=self.convo_end_at))
        print("FETCHED", len(users), "USERS")
        screen_names = sorted([row["user_screen_name"] for row in users])

        for row in self.bq_service.fetch_specific_user_friends(screen_names=screen_names):
            self.counter += 1

            if not self.dry_run:
                self.graph.add_edges_from([(row["screen_name"], friend) for friend in row["friend_names"]])

            if self.counter % self.batch_size == 0:
                rr = {"ts": logstamp(), "counter": self.counter, "nodes": len(self.graph.nodes), "edges": len(self.graph.edges)}
                print(rr["ts"], "|", fmt_n(rr["counter"]), "|", fmt_n(rr["nodes"]), "|", fmt_n(rr["edges"]))
                self.running_results.append(rr)

        self.end()
        self.report()
        self.write_results_to_file()
        self.upload_results()
        self.write_graph_to_file()
        self.upload_graph()

if __name__ == "__main__":


    grapher = BigQueryTopicGrapher.cautiously_initialized()

    grapher.perform()

    grapher.sleep()
