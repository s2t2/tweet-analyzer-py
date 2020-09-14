#!/usr/bin/env python
# coding: utf-8

#upload libraries
import pandas as pd
import numpy as np
import json
from os import listdir
from os.path import isfile, join
from itertools import islice
import re
import progressbar
import csv



# In[17]:
#seperate tweets into their users
def seperate(tweets):
    '''
    takes as input tweets and seperate them into their own users 
    return a dictionary with keys as user ids and values as description and all tweets of this user in input tweets
    '''
    users = dict()
    bar = progressbar.ProgressBar()
    for twt in bar(tweets):
        id_ = twt['user']['id']
        try:
            users[id_]['tweets'].append(twt['text'])
        except:
            u = dict()
            #this user does not exist
            u['description'] = twt['user']['description']
            u['tweets'] = [twt['text']]
            users[id_] = u
    return(users)

#keywords for democrats
hash_rep = list(pd.read_csv("hashtags_rep.txt", sep = ",", skiprows= list(range(9)), names= ['hashtag']).hashtag)
hash_rep = [''.join(re.findall('[0-9A-Za-z]', hash_rep[i])) for i in range(len(hash_rep))]
keywords_rep = '|'.join(hash_rep)
#keywords for democrats
hash_dem = list(pd.read_csv("hashtags_dem.csv", sep = ",", skiprows= list(range(9)), names= ['hashtag']).hashtag)
hash_dem = [''.join(re.findall('[0-9A-Za-z]', hash_dem[i])) for i in range(len(hash_dem))]
keywords_dem = '|'.join(hash_dem) #for regex 

def rep_or_dem(description):
    if bool(re.search(keywords_rep, description, re.IGNORECASE)):
        return(0)
    elif bool(re.search(keywords_dem, description, re.IGNORECASE)):
        return(1)
    else:
        return(None)

def rep_dem(users):
    #list of rep, dem tweets
    rep = []
    dem = []
    bar = progressbar.ProgressBar()
    for usr in bar(users.keys()):
        description = users[usr]['description']
        #see if rep/dem/None
        ind = rep_or_dem(description)
        if ind == 1: #democrat
            dem.extend(list(users[usr]['tweets']))
        elif ind == 0: #republican
            rep.extend(list(users[usr]['tweets']))
        else:
            pass
    return(rep, dem)



#get list of files in our directory so we can loop through them 

path = '/Volumes/Seagate_Backup_Plus_Drive/Twitter_Data/2016_Presidential_Election/tweets_final/'
#path = 'example/'
all_files = [f for f in listdir(path) if isfile(join(path, f))]

print('files are: ', all_files)


#create csv where we will store data

with open('Data/labeled_tweets.csv', 'wb') as myfile:
    wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
    #wr.writerow(['index', 'tweet', 'label'])




def get_data(int_files, n_max, party = None):
    count = 0
    n_tweets = 0
    for file in int_files:
        path_file = path + file
        n = 5000  # Or whatever chunk size you want
        with open(path_file, 'r') as f:
            rep, dem = [], []
            for tweets in iter(lambda: list(islice((json.loads(line) for line in f), n)), []):
                users = seperate(tweets)
                rep_, dem_ = rep_dem(users) #this gives us a list of republican and democrats tweets
                rep.extend(rep_)
                dem.extend(dem_)
                count += 1
                #save every 10 chunks of data (i.e. 50000 tweets)
                if count % 1 == 0:
                    rep = [[i, 0] for i in rep_]
                    dem = [[i, 1] for i in dem_]
                    if party == 'rep':
                        all_ = rep
                    elif party == 'dem':
                        all_ = dem
                    else:
                        all_ = rep + dem
                    df = pd.DataFrame(all_, columns = ['tweet', 'label'])
                    n_tweets += df.shape[0]
                    print(n_tweets)
                    #print(df.head(10))
                    with open('Data/labeled_tweets.csv', 'a',  encoding = 'utf-8') as f_data:
                        df.to_csv(f_data, header=False)
                if n_tweets > n_max:
                    print('stop: maximum number of tweets reached')
                    break

n_max = 100000 #max_number of tweets
int_files = all_files
get_data(int_files, n_max, party = 'rep')
                    

