

import os
from pprint import pprint

from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", default="google-credentials.json")
GCS_BUCKET_NAME=os.getenv("GCS_BUCKET_NAME", default="my-bucket") # "gs://my-bucket"

class GoogleCloudStorageService:
    def __init__(self, bucket_name=GCS_BUCKET_NAME):
        self.client = storage.Client() # implicit check for GOOGLE_APPLICATION_CREDENTIALS
        self.bucket_name = bucket_name
        self.bucket = self.get_bucket()

    def get_bucket(self):
        return self.client.bucket(self.bucket_name)

    def upload(self, local_filepath, remote_filepath):
        blob = self.bucket.blob(remote_filepath)

        # avoid timeout errors when uploading a large file
        # h/t: https://github.com/googleapis/python-storage/issues/74
        #
        # https://googleapis.dev/python/storage/latest/blobs.html
        # chunk_size (int) – (Optional) The size of a chunk of data whenever iterating (in bytes).
        # This must be a multiple of 256 KB per the API specification.
        #
        max_chunk_size = 5 * 1024 * 1024  # 5 MB
        blob.chunk_size = max_chunk_size
        blob._MAX_MULTIPART_SIZE = max_chunk_size

        blob.upload_from_filename(local_filepath)
        return blob

if __name__ == "__main__":

    service = GoogleCloudStorageService()

    print("------------")
    print("BUCKETS:")
    for bucket in service.client.list_buckets():
        print(bucket)

    print("------------")
    print("BUCKET:")
    bucket = service.get_bucket()
    print(bucket)

    if bucket:
        print("------------")
        print("UPLOADING LOCAL FILES:")
        for filename in ["mock_graph.gpickle", "mock_network.csv"]:
            local_filepath = os.path.join(os.path.dirname(__file__), "..", "test", "data", filename)
            remote_filepath = os.path.join("storage", "data", filename)

            blob = bucket.blob(remote_filepath)
            #print(blob) #> <Blob: impeachment-analysis-2020, storage/data/mock_graph.gpickle, None>

            blob.upload_from_filename(local_filepath)
            print(blob) #> <Blob: impeachment-analysis-2020, storage/data/mock_graph.gpickle, 1590433751346995>
            #print(blob.exists()) #> True

            #upload_from_file
            #upload_from_filename
            #upload_from_string