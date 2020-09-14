README

The folder is organized as follows:

#Polarities Folder

- model.py is where the model sits. It has the architecture of the model. It loads the weights from the file called Final_weights/. If you need to use the model, it suffices to do:
from model import load_model
model = load_model()

Note: If you want to use the model you will need to have the processed tweet. For that, we have the script helper_text that does that for us. 

- helper_text: It has a number of functions that you can read. They're pretty easy to understand. (cleaning, stemming, segmenting ... etc) The main function is main_clean. This function takes as input a raw tweet (e.g. @zlisto likes music #musicfan) and will output one list of two vectors. The first one is processed with hashtages (not segmented), and the other with hashtags segmented. These two will be the input to the model if you would like to predict whether this tweet is Rep/Dem. 

Example: 
from model import load_model
from helper_text import main_clean
twt = 'RT @US_Army_Vet: Americans First In Jobs &amp; In Security! VOTE TRUMP For Our Kids Future! @KimEstes20 @trumpkin007 @SpecialKMB1969 #USA'
x, x_s = main_clean(twt)
#predict
dem_pol = model.predict([x, x_s])[:,1] #this is the probability this tweet is democrat. 

Note: Both helper_text and model make use of the dictionaries (i.e. vocabulary). They are available in Dictionary/ folder

- get_polarity: This is the file you can use to mine through the dataset and extract polarity of users. The only thing you need to specify is the files in the dataset that you would like to mine. It is a list called int_files at the bottom of the script. You can specify them either by their index in the hardrive (0-index: all_files[0] refers to 'democratic-candidate-timelines_tweets.txt') or you can set them by their name as in the hard drive. 

Note: If you specify int_files to be all_files (i.e. int_files = all_files) and run the code. You will go through the ENTIRE files in 'Twitter_Data/2016_Presidential_Election/tweets_final/'. This will take a couple of days or so. 

Note: 'polarities.csv' is the result of mining 'republican-party-timelines_tweets.txt' and 'second-debate_tweets.txt', which took one whole night. 

- superseded: random file to keep things that you're not sure you might need in the future. Feel free to delete. 


############

If you're unhappy with the model and probably want to train on more data. First, you will have to label more data. 


#Labeling Folder:

If you happen to need a better labeled dataset, or even a whole different dataset different form the US one. You can go to taleling/. The script label.py will help you buikd a labeled dataset in a systematic way. This can be done in 4 steps:
1. define key words for each party: 
these are found in the two files hashtags_rep and hashtags_dem. They do not necessarily ahve to be hashtags nor do they have to be preceded by a hash (#) sign. Just type each keyword that can identify that party. The keywords are then mapped again each user's profile description.
2. Run label.py: For this, you'll have to specify a number of things. How many tweets you want (n_max) and the files you want to use from the hard drive to mine for these tweets. (int_files). If you set int_files to all_files, the program will go through the whole 1TB of data. 
3. Balance the dataset: Depending on the keywords for each party and the distribution of tweets in the files you chose, the dataset can be very unbalanced. There are two ways to balance it: increase the number tweets from the minority party (through mining) or decrease the number of tweets from the majority parity (downsampling). 
balance.py: this script has two functions that allow you to each of the methods above. Please pay attention to the warnings commented. 
4. If you want to use this to train your model, make sure you copy and paste the labeling/Data/labeled_dataset OR labeling/Data/labeled_dataset_balanced to training/Data and rename it as modeling1_1.csv *

* I keep these laborious step to avoid overwriting some data and regretting after. (happened many times :)) 


#Training Folder:

train.py: After labeling the data, and you want to train your new model, This is the script you want to use. All you have to do is to specify how much data (i.e. number of tweets) you want your model to train on. The model will then process this data from the one you labeled and outputs brand new X, X_s, Y, sequence length and dictionary sizes. The latter two are needed for the deep learning architecture. The model will then train and outputs the train and test accuracy. 

Note: Obviously when you train a new model, you get new weights. These are available in model-chekpoint. 

#New polarities:

With a new model, you want new polarities. For this, you'll have to go back to the polarities folder and update three things: 
- Dictionary: When you processed your data in the train.py, two new dictionaries were generaties in the folder trainin/Dictionary. Use them to replace the old dictionaries in polarities/Dictionary.
- Weights: New model come with new weights. As the model is trained with early stoppping, the best weights are often the last few ones. Choose the ones with the highest accuracy from the folder training/model-checkpoint. WARNING: Make sure you don't take the weights of some previous old model you trained. (check Data modified for caution). Replace the new weights in polarities/Final_weights and rename them to final_weights.hdf5

Note: Please be cautious when replacing the weights and dictionaries. Don't delete them completely. Keep them in superseded file or something in case things go wrong. 
















