import numpy as np
# ## Upload utils for formatting the tweets
#libraries for text processing 
from wordsegment import load, segment
from gensim.corpora import Dictionary
import re
import string
from nltk.corpus import stopwords
from keras.preprocessing import sequence

#segmentation
load()
def my_replace(match):
    match = match.group()
    return ' '.join(segment(match))

#this function
def process(twt):
    try:
        return(re.sub('#\w+', my_replace, twt))
    except Exception as e:
        return(None)

def clean(twt):
    #remove punctutation
    try:
        twt = twt.translate(str.maketrans('','',string.punctuation))
        twt = twt.split()
        twt = [i.lower() for i in twt]
        twt = [i for i in twt if 'htt' not in i and 
                                      i not in stopwords.words('english')]
        twt = ' '.join(twt)
        return(twt)
    except Exception as e:
        #print(e)
        return(None)


#transform takes a clean tweet and tokenize it
#load dictionary
dictionary = Dictionary.load_from_text('Dictionary/dic.txt')
def transform(twt, seq_len):
    twt = clean(twt).split()
    l = []
    for i in twt:
        try:
            l.append(1 + dictionary.token2id[i])
        except:
            l.append(0)
    twt = sequence.pad_sequences([l], maxlen=seq_len)
    return(twt)
#dictionary_s
dictionary_s = Dictionary.load_from_text('Dictionary/dic_s.txt')
def transform_s(twt, seq_len):
    twt = clean(twt).split()
    l = []
    for i in twt:
        try:
            #print(i)
            l.append(1 + dictionary_s.token2id[i])
        except Exception as e:
            #print(e)
            l.append(0)
    twt = sequence.pad_sequences([l], maxlen=seq_len)
    return(twt)

def main_clean(twt):
    #segment
    twt_s = process(twt)
    #clean
    twt = clean(twt)
    twt_s = clean(twt_s)
    #transform
    twt = transform(twt, 20)
    twt_s = transform_s(twt_s, 20)
    #make x 
    x = [twt, twt_s]
    return(x)
