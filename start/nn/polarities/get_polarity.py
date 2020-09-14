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

# In[1]:
from helper_text import main_clean
from model import load_model


model = load_model()


#Example
print('Example: ')
twt = 'RT @US_Army_Vet: Americans First In Jobs &amp; In Security! VOTE TRUMP For Our Kids Future! @KimEstes20 @trumpkin007 @SpecialKMB1969 #USA https…'
print(twt)
x, x_s = main_clean(twt)
#predict
dem_pol = model.predict([x, x_s])[:,1]
print('the probability this tweet is democrat is ', dem_pol[0])


# In[16]:


#get list of files in our directory so we can loop through them 

path = '/Volumes/Seagate_Backup_Plus_Drive/Twitter_Data/2016_Presidential_Election/tweets_final/'
all_files = [f for f in listdir(path) if isfile(join(path, f))]

print('files are: ', all_files)


# In[17]:
def update(users, tweets):
    '''
    takes as input:
    users: dictionary where keys are users_id and values are the user's information and polarity
    tweets: dictionary of tweets as available in The Hard Drive 
    Output:
    users: Update the users dictionary entered with new information from the tweets data input
    '''
    bar = progressbar.ProgressBar()
    for twt in bar(tweets):
        id_ = twt['user']['id']
        u = dict()
        u['id'] = id_
        u['n_followers'] = twt['user']['followers_count']
        u['description'] = twt['user']['description']
        u['n_friends'] = twt['user']['friends_count']
        u['location'] = twt['user']['location']
        u['name'] = twt['user']['name']
        u['screen_name'] = twt['user']['screen_name']
        u['n_tweets_user'] = twt['user']['statuses_count']
        u['created_at'] = twt['user']['created_at']
        #here we want to keep track of how many tweets are used to compute the polarity
        try:
            u['n_tweets_model'] = users[id_]['n_tweets_model'] + 1
        except Exception as e:
            #print(e)
            u['n_tweets_model'] = 1
        #get tweet
        x, x_s = main_clean(twt['text'])
        p = model.predict([x, x_s])[:,1][0]
        #we want to update polarity
        try:
            n = u['n_tweets_model']
            u['polarity'] = (n-1)/n * users[id_]['polarity'] + 1/n * p
        except Exception as e:
            #print(e)
            u['polarity'] = p
            #u['polarity'] = [p]
        users[id_] = u
    return(users)


#define dictionary where users are keys 
users =dict()
count = 0. #to track how many batches of data we visited 
'''
Choose the files you want below. (either use index or name as in the Hard Drive)
'''
int_files = [all_files[-4], all_files[-3]] #choose the files we want to mine through

print('files used: ', int_files)
for file in int_files:
    path_file = path + file
    n = 5000  # Or whatever chunk size you want
    with open(path_file, 'r') as f:
        for tweets in iter(lambda: list(islice((json.loads(line) for line in f), n)), []):
            users = update(users, tweets)
            print(len(users))
            count += 1
            #save every 10 chunks of data (This is just a precaution in case of memory failure, we would have saved something)
            if count % 10 == 0:
                file_name = 'polarities_checkpoint/users_polarities_' + str(len(users)) + '.npy'
                np.save(file_name, users)

print('number of users in total: ', len(users))

#sae final file
file_name = 'polarities_checkpoint/users_polarities_' + str(len(users)) + '.npy'
np.save(file_name, users)

#save as csv
pd.DataFrame.from_dict(users).T.to_csv('polarities_new.csv')
