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


#get list of files in our directory so we can loop through them 

path = '/Volumes/Seagate_Backup_Plus_Drive/Twitter_Data/2016_Presidential_Election/tweets_final/'
all_files = [f for f in listdir(path) if isfile(join(path, f))]

print('files are: ', all_files)


# In[17]:
#seperate tweets into their users
def seperate(tweets):
    '''
    takes as input:
    users: dictionary where keys are users_id and values are the user's information and polarity
    tweets: dictionary of tweets as available in The Hard Drive 
    Output:
    users: Update the users dictionary entered with new information from the tweets data input
    '''
    users = dict()
    bar = progressbar.ProgressBar()
    for twt in bar(tweets):
        id_ = twt['user']['id']
        try:
            users[id_]['tweets'].append(twt['text'])
        except:
            #this user does not exist
            u['description'] = twt['user']['description']
            u['tweets'] = [twt['text']]
            users[id_] = u
    return(users)

def rep_dem(users):
    #list of rep, dem tweets
    rep = []
    dem = []
    bar = progressbar.ProgressBar()
    for usr in bar(users.keys()):
        










