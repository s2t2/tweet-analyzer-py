import pandas as pd 


data = pd.read_csv('Data/labeled_tweets.csv', index_col = 0)
data.columns = ['tweet', 'label']
#see how many are in each group
dem = data.label.sum()
rep = data.shape[0] - data.label.sum()

print('Dems: percentage : ', dem/data.shape[0], ' number :', dem)
print('Reps: percentage : ', rep/data.shape[0], ' number :', rep)

if dem < rep:
		maj = 0
		min_ = 1
		party_min = 'dem'
else:
	maj = 1
	min_ = 0
	party_min = 'rep'

def downsample():
	'''
	takes original dataset and downsample it
	output a smaller dataset
	'''
	majority = data[data.label == maj].sample(min(dem, rep))
	minority = data[data.label == min_]
	#concatenate the two 
	data = pd.concat([majority, minority], axis = 0)
	print('after balancing the data:')
	dem = data.label.sum()
	rep = data.shape[0] - data.label.sum()
	print('Dems: percentage : ', dem/data.shape[0], ' number :', dem)
	print('Reps: percentage : ', rep/data.shape[0], ' number :', rep)
	data.to_csv('labeled_data_balanced.csv')
	return(data)


def increase(): 
	'''
	takes as input the minority party and increases your original dataset 
	'''
	from label import get_data
	int_files = [] #Warning do not include previous files used for original dataset. You'll end up iwth duplicates
	n_max = max(dem, rep) #as we want to match it 
	get_data(int_files, n_max, party = party_min)


#choose which method you want to use 
#WARNING: the increase method directly increases the data to your oiriginal dataset. 
increase()
#downsample()






