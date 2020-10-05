
import os
from pprint import pprint

from dotenv import load_dotenv

from app import DATA_DIR, seek_confirmation
from app.decorators.datetime_decorators import logstamp
from app.gcs_service import GoogleCloudStorageService

load_dotenv()

DIRPATH = os.getenv("DIRPATH", default="example/file_storage")
WIFI = (os.getenv("WIFI", default="true") == "true")

class FileStorage:

    def __init__(self, dirpath=None, gcs_service=None, wifi=WIFI):
        """
        Saves and loads files, using local storage and/or Google Cloud Storage.

        Params:
            dirpath (str) a subpath of the data dir
            wifi (bool) whether or not to attempt uploads

        """
        self.wifi = wifi
        self.gcs_service = gcs_service or GoogleCloudStorageService()

        self.dirpath = dirpath or DIRPATH
        self.gcs_dirpath = self.compile_gcs_dirpath(self.dirpath)
        self.local_dirpath = self.compile_local_dirpath(self.dirpath)

        print("-------------------------")
        print("FILE STORAGE...")
        print("   BUCKET:",  self.gcs_service.bucket_name.upper())
        print("   DIRPATH:",  self.dirpath)
        print("   GCS DIRPATH:", self.gcs_dirpath)
        print("   LOCAL DIRPATH:", os.path.abspath(self.local_dirpath))
        print("   WIFI ENABLED:", self.wifi)

        seek_confirmation()

        if not os.path.exists(self.local_dirpath):
            os.makedirs(self.local_dirpath)

    @staticmethod
    def compile_local_dirpath(dirpath):
        return os.path.join(DATA_DIR, dirpath)

    @staticmethod
    def compile_gcs_dirpath(dirpath):
        return os.path.join("storage", "data", dirpath)

    #
    # REMOTE STORAGE
    #

    def upload_file(self, local_filepath, remote_filepath):
        print(logstamp(), "UPLOADING FILE...", os.path.abspath(local_filepath))
        blob = self.gcs_service.upload(local_filepath, remote_filepath)
        print(logstamp(), blob) #> <Blob: impeachment-analysis-2020, storage/data/2020-05-26-0002/metadata.json, 1590465770194318>

    def download_file(self, remote_filepath, local_filepath):
        print(logstamp(), "DOWNLOADING FILE...", remote_filepath)
        self.gcs_service.download(remote_filepath, local_filepath)
