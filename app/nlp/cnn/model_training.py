
import os

import numpy as np
from keras.preprocessing import sequence
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

from app.nlp.cnn.model_helper import get_xy



n_tweets = 10000 #for example
X, X_s, Y, dictionary_size, dictionary_size_s, seq_len = get_xy(n_tweets)

seed = np.random.random(X.shape[0])

np.random.seed(1)
np.random.shuffle(X)
np.random.seed(1)
np.random.shuffle(Y)
np.random.seed(123)
np.random.shuffle(X_s)







#train dataset 80% - 20%

split = int(X.shape[0]*0.8)

train_X = X[:split,:]
train_Y = Y[:split,]

test_X = X[split:,:]
test_Y = Y[split:,]

#to be added to the LSTM, we need to change y to specific format

train_Y = np_utils.to_categorical(train_Y, 2)


#train dataset 80% - 20%
split = int(X_s.shape[0]*0.8)
train_X_s = X_s[:split,:]
test_X_s = X_s[split:,:]

#to be added to the LSTM, we need to change Y_s to specific format










#
# Architecture
#

seq_len = train_X.shape[1]
#earlystopping
es = EarlyStopping(monitor='val_loss', min_delta=0, patience=3, verbose=0, mode='auto')

outputFolder = './model-checkpoint'
if not os.path.exists(outputFolder):
    os.makedirs(outputFolder)

filepath= outputFolder + "/weights-improvement-{epoch:02d}-{val_acc:.2f}.hdf5"

save = ModelCheckpoint(filepath, monitor='val_acc', verbose=1, save_best_only=True, mode='max')

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

#merge
merged = concatenate([flat1, flat2])

#dense
dense1 = Dense(64, activation='relu')(merged)
dense2 = Dense(32, activation='relu')(dense1)
outputs = Dense(2, activation='softmax')(dense2)

model = Model(inputs=[inputs1, inputs2], outputs=outputs)

model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
print(model.summary())
#plot_model(model, show_shapes=True, to_file='multichannel.png')

#
# TRAINING
#

model.fit([train_X, train_X_s], train_Y,
    epochs=100,
    batch_size=256,
    callbacks=[es, save],
    validation_split=0.2
)

#
# TESTING
#

print('testing ...')
test_pred = model.predict([test_X, test_X_s])
test_pred = (test_pred[:,0] <= 0.5).astype(int)

print("test set accuracy: ", float(sum(test_Y == test_pred)) / test_Y.shape[0])
print("base line accuracy: ", 1 - sum(Y[:split,])/len(Y[:split,]))
