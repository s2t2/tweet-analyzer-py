from keras.utils import np_utils
from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Embedding, SpatialDropout1D, Flatten
from keras.layers import Input
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.layers.convolutional import Conv1D
from keras.layers.convolutional import MaxPooling1D
from keras.layers.merge import concatenate
#from keras.utils.vis_utils import plot_model
from keras.models import Model

from gensim.corpora import Dictionary

dictionary = Dictionary.load_from_text('Dictionary/dic.txt')
dictionary_s = Dictionary.load_from_text('Dictionary/dic_s.txt')

# In[10]:
dictionary_size = len(dictionary)
dictionary_size_s = len(dictionary_s)


# In[11]:

def load_model():
	#import model architecture
	seq_len = 20
	#input1
	inputs1 = Input(shape=(seq_len,))
	embedding1 = Embedding(dictionary_size + 1, 128)(inputs1)
	conv1 = Conv1D(filters=32, kernel_size=3, activation='relu', padding='valid')(embedding1)
	drop1 = Dropout(0.2)(conv1)
	pool1 = MaxPooling1D(pool_size=2)(drop1)
	flat1 = Flatten()(pool1)
	#Input2
	inputs2 = Input(shape=(seq_len,))
	embedding2 = Embedding(dictionary_size_s + 1, 128)(inputs2)
	conv2 = Conv1D(filters=32, kernel_size=3, activation='relu', padding='valid')(embedding2)
	drop2 = Dropout(0.2)(conv2)
	pool2 = MaxPooling1D(pool_size=2)(drop2)
	flat2 = Flatten()(pool2)
	#merge via concatenation
	merged = concatenate([flat1, flat2])
	#dense
	dense1 = Dense(64, activation='relu')(merged)
	dense2 = Dense(32, activation='relu')(dense1)
	outputs = Dense(2, activation='softmax')(dense2)
	model = Model(inputs=[inputs1, inputs2], outputs=outputs)
	#print(model.summary())

	#load model weights 
	model.load_weights('Final_weights/final_weights.hdf5')
	return(model)

