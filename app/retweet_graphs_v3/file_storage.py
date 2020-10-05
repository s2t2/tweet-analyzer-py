
import os
from pprint import pprint

from dotenv import load_dotenv
from networkx import write_gpickle, read_gpickle
from pandas import read_csv

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
    # LOCAL
    #

    def local_filepath(self, filename):
        return os.path.join(self.local_dirpath, filename)

    def local_file_exists(self, filename):
        return os.path.exists(self.local_filepath(filename))

    # REMOTE

    def gcs_filepath(self, filename):
        return os.path.join(self.gcs_dirpath, filename)

    def upload_file(self, filename):
        print(logstamp(), "UPLOADING FILE...", filename)
        blob = self.gcs_service.upload(self.local_filepath(filename), self.gcs_filepath(filename))
        print(logstamp(), blob) # > <Blob: impeachment-analysis-2020, storage/data/2020-05-26-0002/metadata.json, 1590465770194318>

    def download_file(self, filename):
        print(logstamp(), "DOWNLOADING FILE...", filename)
        self.gcs_service.download(self.gcs_filepath(filename), self.local_filepath(filename))

    # COMBO

    def save_gpickle(self, obj, filename):
        """ Params: the object to save, and the name of the file to save it as"""
        write_gpickle(obj, self.local_filepath(filename))
        self.upload_file(filename)

    def save_df(self, df, filename):
        """ Params: the object to save, and the name of the file to save it as"""
        df.to_csv(self.local_filepath(filename))
        self.upload_file(filename)

    def load_gpickle(self, filename):
        if not self.local_file_exists(filename):
            self.download_file(filename)
        return read_gpickle(self.local_filepath(filename))

    def load_df(self, filename):
        if not self.local_file_exists(filename):
            self.download_file(filename)
        return read_csv(self.local_filepath(filename))
