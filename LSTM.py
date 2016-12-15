import numpy as np
from utils import initw
from utils import softmax
import sys
from datetime import datetime

class LSTM:

    @staticmethod
    def init(input_size, hidden_size, output_size):

        model = {}

        model['WLSTM'] = initw(input_size + hidden_size + 1, 4 * hidden_size)
        model['Wd'] = initw(hidden_size, output_size)
        model['bd'] = np.zeros((1, output_size))

        update = ['WLSTM', 'Wd', 'bd']

        return { 'model' : model, 'update' : update}

    @staticmethod
    def forward(Xs, model, **kwargs):

        X = Xs

        WLSTM = model['WLSTM']
        Wd = model['Wd']
        bd = model['bd']
        #n = X.shape[0]
        n = len(X)
        d = model['Wd'].shape[0]

        Hin = np.zeros((n, WLSTM.shape[0]))
        Hout = np.zeros((n, d))
        IFOG = np.zeros((n,d * 4))
        IFOGf = np.zeros((n, d * 4))
        C = np.zeros((n, d))

        for t in xrange(n):
            prev = np.zeros(d) if t == 0 else Hout[t-1]
            
            Hin[t, 0] = 1
            #Hin[t, 1:1+d] = X[t]
            Hin[t, 1:1+d] = prev # one hot representation            
            Hin[t, 1+d+X[t]] = 1

            IFOG[t] = Hin[t].dot(WLSTM)

            IFOGf[t, :3*d] = 1.0/(1.0 + np.exp(-IFOG[t, :3*d]))
            IFOGf[t, 3*d:] = np.tanh(IFOG[t, 3*d:])

            C[t] = IFOGf[t, :d] * IFOGf[t, 3*d:]
            if t>0: C[t] += IFOGf[t, d:2*d] * C[t-1]

            Hout[t] = IFOGf[t, 2*d:3*d] * np.tanh(C[t])

        #Y = Hout[1:, :].dot(Wd) + bd
        Y = Hout.dot(Wd) + bd
        Y = softmax(Y)

        cache = {}

        cache['WLSTM'] = WLSTM
        cache['Hout'] = Hout
        cache['Wd'] = Wd
        cache['IFOGf'] = IFOGf
        cache['IFOG'] = IFOG
        cache['C'] = C
        cache['X'] = X
        cache['Hin'] = Hin

        return Y, cache

    @staticmethod
    def backword(dY, cache):

        Wd = cache['Wd']

        Hout = cache['Hout']
        IFOG = cache['IFOG']
        IFOGf = cache['IFOGf']
        C = cache['C']
        Hin = cache['Hin']
        WLSTM = cache['WLSTM']
        X = cache['X']

        dWd = Hout.transpose().dot(dY)
        dbd = np.sum(dY, axis=0, keepdims=True)
        dHout = dY.dot(Wd.transpose())

        dIFOG = np.zeros(IFOG.shape)
        dIFOGf = np.zeros(IFOGf.shape)
        dWLSTM = np.zeros(WLSTM.shape)
        dHin = np.zeros(Hin.shape)
        dC = np.zeros(C.shape)
        #dX = np.zeros(X.shape)
        #dX = np.zeros((len(X)+1, Wd.shape[1]))
        n, d = Hout.shape

        for t in reversed(xrange(n)):
            tanhC = np.tanh(C[t])
            dIFOGf[t, 2*d:3*d] = tanhC * dHout[t]
            dC[t] += (1 - tanhC**2) * (IFOGf[t, 2*d:3*d] * dHout[t])

            #forget gate
            if t > 0:
                dIFOGf[t, d:2*d] = C[t-1] * dC[t]
                dC[t-1] += IFOGf[t, d:2*d] * dC[t]

            #input gate
            dIFOGf[t, :d] = IFOGf[t, 3*d:] * dC[t]
            dIFOGf[t, 3*d:] = IFOGf[t, :d] * dC[t]

            dIFOG[t, 3*d:] = (1 - IFOGf[t, 3*d:] ** 2) * dIFOGf[t, 3*d:]
            y = IFOGf[t, :3*d]
            dIFOGf[t, :3*d] = (y*(1.0-y)) * dIFOGf[t, :3*d]

            dWLSTM +=  np.outer(Hin[t], dIFOG[t])
            dHin[t]  = dIFOG[t].dot(WLSTM.transpose())

            #dX[t] = dHin[t,:d]
            if t > 0:
                dHout[t-1] += dHin[t, 1:1+d]
                #dHout[t-1] += dHin[t, d:]

        #return {'WLSTM' : dWLSTM, 'Wd' : dWd, 'bd' : dbd, 'dX' : dX }
        return {'WLSTM' : dWLSTM, 'Wd' : dWd, 'bd' : dbd}

    @staticmethod
    def predict(Xs, model, **kwargs):
        
        Y, cache = LSTM.forward(Xs, model)

        return np.argmax(Y, axis=1)

    @staticmethod
    def calc_total_loss(Xs, y, model):
        L = 0
        N = np.sum(len(y_i) for y_i in y)
        
        for i in xrange(len(y)):
            #print 'shuchu', i
            #print len(Xs), len(y)
            py, cache = LSTM.forward(Xs[i], model)
            #print 'input ', Xs[i]
            #print 'output ', np.argmax(softmax(py), axis=1)
            correct_word_prediction = py[np.arange(len(y[i])), y[i]]
            #print correct_word_prediction
            L += -1 * np.sum(np.log(correct_word_prediction))

        return L / N


    @staticmethod
    def sgd_step(Xs, y, learning_rate, model):
        py, cache = LSTM.forward(Xs, model)
       # print len(py), len(y)
        y = np.reshape(y,(len(y),-1))
        dY = py
        dY[np.arange(len(y)), y] -= 1
        #print 'dY: ', dY

        bp = LSTM.backword(dY, cache)
        dWLSTM = bp['WLSTM']
        dWd = bp['Wd']
        dbd = bp['bd']

        #print 'ddddd', model['bd'], dbd
        model['WLSTM'] -= learning_rate * dWLSTM
        model['Wd'] -= learning_rate * dWd
        model['bd'] -= learning_rate *dbd

    @staticmethod
    def train_with_sgd(model, Xs, y, learning_rate=0.005, nepoch=1, evaluate_loss_after=5):
        losses = []
        num_examples_seen = 0
        #print 'cjjc', len(Xs), len(y)
        for epoch in xrange(nepoch):
            if(epoch % evaluate_loss_after ==0):
                loss = LSTM.calc_total_loss(Xs, y, model)
                losses.append((num_examples_seen, loss))
                time = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
                print '%s loss %f %d' %(time, loss, num_examples_seen)
                if(len(losses) > 1 and losses[-1][1] > losses[-2][1]):
                    learning_rate *= 0.5
                    print "Setting learning rate to %f" % learning_rate
                sys.stdout.flush()

            
            for i in xrange(len(y)):
                LSTM.sgd_step(Xs[i], y[i], learning_rate, model)
                num_examples_seen += 1


