
# Tweet Analysis (Python)

So you've [collected](https://github.com/zaman-lab/tweet-collection-py) tens of millions of tweets about a given topic and stored them in Google BigQuery. Now it's time to analyze them.

This project builds upon the research of Tauhid Zaman, Nicolas Guenon Des Mesnards, et. al., as described by the paper: ["Detecting Bots and Assessing Their Impact in Social Networks"](https://arxiv.org/abs/1810.12398).

## Table of Contents

Version 1 (works in progress, investigations, archive):

  + [Tweet Collection v1](/app/tweet_collection/README.md)
  + [Friend Collection v1](/app/friend_collection/README.md)
    + [Friend Graphs v1](/app/friend_graphs/README.md)
  + [PG Pipeline](/app/pg_pipeline/README.md) (Local Database Migrations)
  + [Retweet Graphs v1](/app/retweet_graphs/README.md)
    + [Bot Classification v1](/app/botcode)
    + [Bot Classification v2](/app/retweet_graphs/README.md#Bot-Classification)
    + [KS Tests v1](/app/retweet_graphs/README.md#KS-Tests)
  + [Retweet Graphs v2](/app/retweet_graphs_v2/README.md)
    + [Bot Classification v3 (Daily Periods)](/app/retweet_graphs_v2/README.md#k-days-bot-classification)
    + [Bot Communities v1](/app/bot_communities/README.md#Assignment)
    + [Bot Community Analysis v1](/app/bot_communities/README.md#Analysis)
      + [Bot Follower Graphs](/app/bot_follower_graphs/README.md)

Version 2 (reproduction, with some improvements):

  + [Tweet Collection v2](/app/tweet_collection_v2/README.md)
  + [Retweet Graphs v3](/app/retweet_graphs_v3/README.md)
    + [Bot Classification v4](/app/retweet_graphs_v3/README.md#Bot-Classification)
    + [Bot Communities v2](/app/retweet_graphs_v3/README.md#Bot-Communities)
    + [Bot Community Analysis v2](/app/retweet_graphs_v3/README.md#Bot-Community-Analysis)


## Installation

Dependencies:

  + Git
  + Python 3.8
  + PostgreSQL (optional)

Clone this repo onto your local machine and navigate there from the command-line:

```sh
cd tweet-analysis-py/
```

Create and activate a virtual environment, using anaconda for example, if you like that kind of thing:

```sh
conda create -n tweet-analyzer-env-38 python=3.8
conda activate tweet-analyzer-env-38
```

Install package dependencies:

```sh
pip install -r requirements.txt
```

## Setup

### Twitter API Credentials

If you want to collect tweets or user friends, obtain credentials which provide read access to the Twitter API. Set the environment variables `TWITTER_CONSUMER_KEY`, `TWITTER_CONSUMER_SECRET`, `TWITTER_ACCESS_TOKEN`, and `TWITTER_ACCESS_TOKEN_SECRET` accordingly (see environment variable setup below).

### Google BigQuery and API Credentials

The massive volume of tweets are stored in a Google BigQuery database, so we'll need BigQuery credentials to access the data. From the [Google Cloud console](https://console.cloud.google.com/), enable the BigQuery API, then generate and download the corresponding service account credentials. Move them into the root directory of this repo as "credentials.json", and set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable accordingly (see environment variable setup below).

### Google Cloud Storage

There will be many twitter user network graph objects generated, and they can be so large that trying to construct them on a laptop is not feasible due to memory constraints. So there may be need to run various graph construction scripts on a larger remote server. File storage on a Heroku server is ephemeral, so we'll save the files to a Google Cloud Storage bucket so they persist. Create a new bucket or gain access to an existing bucket, and set the `GCS_BUCKET_NAME` environment variable accordingly (see environment variable setup below).

FYI: in the bucket, there will also exist some temporary tables used by BigQuery during batch job performances, so we're namespacing the storage of graph data under "storage/data", which is a mirror of the local "data" directory.

### SendGrid Emails

The app will run scripts that take a long time. To have those scripts send emails when they are done, first obtain a [SendGrid API Key](https://app.sendgrid.com/settings/api_keys), then set it as an environment variable (see environment variable setup below).

### Basilica Credentials

If using the Basilica API, obtain a [Basilica API Key](https://www.basilica.ai/api-keys/) and set the `BASILICA_API_KEY` environment variable accordingly (see environment variable setup below).

### Local Database

To download some of the data from BigQuery into a local database, first create a local PostgreSQL database called something like "impeachment_analysis", then set the `DATABASE_URL` environment variable accordingly (see environment variable setup below).

### Environment Variables

Create a new file in the root directory of this repo called ".env", and set your environment variables there, as necessary:

```sh
# example .env file

#
# GOOGLE APIs
#

GOOGLE_APPLICATION_CREDENTIALS="/path/to/tweet-analysis-py/credentials.json"
BIGQUERY_PROJECT_NAME="tweet-collector-py"
BIGQUERY_DATASET_NAME="impeachment_development"
GCS_BUCKET_NAME="impeachment-analysis-2020"

#
# LOCAL PG DATABASE
#

# DATABASE_URL="postgresql://USERNAME:PASSWORD@localhost/impeachment_analysis"

#
# EMAIL
#

# SENDGRID_API_KEY="__________"
# MY_EMAIL_ADDRESS="hello@example.com"

#
# NLP
#

# BASILICA_API_KEY="______________"
```

## Usage

Testing the Google BigQuery connection:

```sh
python -m app.bq_service
```

Testing the Google Cloud Storage connection, saving some mock files in the specified bucket:

```sh
python -m app.gcs_service
```

## Testing

Run tests:

```sh
APP_ENV="test" pytest
```

On the CI server, skips web requests:

```sh
CI="true" APP_ENV="test" pytest
```

## [Deploying](/DEPLOYING.md)

## [License](/LICENSE.md)
