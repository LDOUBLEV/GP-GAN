import chainer
import chainer.links as L
import chainer.functions as F

from chainer import cuda

def init_conv(array):
    xp = cuda.get_array_module(array)
    array[...] = xp.random.normal(loc=0.0, scale=0.02, size=array.shape)
def init_bn(array):
    xp = cuda.get_array_module(array)
    array[...] = xp.random.normal(loc=1.0, scale=0.02, size=array.shape)

class ReLU(chainer.Chain):
    def __init__(self):
        super(ReLU, self).__init__()

    def __call__(self, x):
        return F.relu(x)

class Tanh(chainer.Chain):
    def __init__(self):
        super(Tanh, self).__init__()

    def __call__(self, x):
        return F.tanh(x)

class LeakyReLU(chainer.Chain):
    def __init__(self):
        super(LeakyReLU, self).__init__()

    def __call__(self, x):
        return F.leaky_relu(x)

class Decoder(chainer.ChainList):
    def __init__(self, isize, nc, ndf, conv_init=None, bn_init=None):
        cndf, tisize = ndf//2, 4
        while tisize != isize:
            cndf = cndf * 2
            tisize = tisize * 2

        layers = []
        # input is Z, going into a convolution
        layers.append(L.Deconvolution2D(None, cndf, ksize=4, stride=1, pad=0, initialW=conv_init, nobias=True))
        layers.append(L.BatchNormalization(cndf, initial_gamma=bn_init))
        layers.append(ReLU())
        csize= 4
        while csize < isize//2:
            layers.append(L.Deconvolution2D(None, cndf//2, ksize=4, stride=2, pad=1, initialW=conv_init, nobias=True))
            layers.append(L.BatchNormalization(cndf//2, initial_gamma=bn_init))
            layers.append(ReLU())
            cndf = cndf // 2
            csize = csize * 2
        layers.append(L.Deconvolution2D(None, nc, ksize=4, stride=2, pad=1, initialW=conv_init, nobias=True))

        super(Decoder, self).__init__(*layers)

    def __call__(self, x, test=False):
        for i in range(len(self)):
            if isinstance(self[i], L.BatchNormalization):
                x = self[i](x, test=test)
            else:
                x = self[i](x)
        return x

class Encoder(chainer.ChainList):
    def __init__(self, isize, nef, nz=100, conv_init=None, bn_init=None):
        layers = []
        layers.append(L.Convolution2D(None, nef, ksize=4, stride=2, pad=1, initialW=conv_init, nobias=True))
        layers.append(LeakyReLU())
        csize, cnef = isize // 2, nef
        while csize > 4:
            out_feat = cnef * 2
            layers.append(L.Convolution2D(None, out_feat, ksize=4, stride=2, pad=1, initialW=conv_init, nobias=True))
            layers.append(L.BatchNormalization(out_feat, initial_gamma=bn_init))
            layers.append(LeakyReLU())

            cnef = cnef * 2
            csize = csize // 2
        # state size. K x 4 x 4
        layers.append(L.Convolution2D(None, nz, ksize=4, stride=1, pad=0, initialW=conv_init, nobias=True))

        super(Encoder, self).__init__(*layers)

    def __call__(self, x, test=False):
        for i in range(len(self)):
            if isinstance(self[i], L.BatchNormalization):
                x = self[i](x, test=test)
            else:
                x = self[i](x)

        return x

class EncoderDecoder(chainer.Chain):
    def __init__(self, nef, ndf, nc, nBottleneck, image_size=64, conv_init=None, bn_init=None):
        super(EncoderDecoder, self).__init__(
            # encoder = Encoder(image_size, nef, nBottleneck, conv_init, bn_init),
            encoder = L.VGG16Layers(),
            # bn      = L.BatchNormalization(nBottleneck, initial_gamma=bn_init),
            decoder = Decoder(image_size, nc, ndf, conv_init, bn_init)
        )

    def __call__(self, x, test=False):
        # h = self.encoder(x, test=test)
        h = self.encoder(x, layers=['pool5'], test=True)['pool5']
        h = F.average_pooling_2d(h, h.shape[-2:])
        h.unchain_backward()
        # h = F.leaky_relu(self.bn(h, test=test))
        h = self.decoder(h, test=test)

        return h

class RealismCNN(chainer.Chain):
    def __init__(self, w_init=None):
        super(RealismCNN, self).__init__(
            conv1_1=L.Convolution2D(None, 64, ksize=3, stride=1, pad=1, initialW=w_init),
            conv1_2=L.Convolution2D(None, 64, ksize=3, stride=1, pad=1, initialW=w_init),

            conv2_1=L.Convolution2D(None, 128, ksize=3, stride=1, pad=1, initialW=w_init),
            conv2_2=L.Convolution2D(None, 128, ksize=3, stride=1, pad=1, initialW=w_init),

            conv3_1=L.Convolution2D(None, 256, ksize=3, stride=1, pad=1, initialW=w_init),
            conv3_2=L.Convolution2D(None, 256, ksize=3, stride=1, pad=1, initialW=w_init),
            conv3_3=L.Convolution2D(None, 256, ksize=3, stride=1, pad=1, initialW=w_init),

            conv4_1=L.Convolution2D(None, 512, ksize=3, stride=1, pad=1, initialW=w_init),
            conv4_2=L.Convolution2D(None, 512, ksize=3, stride=1, pad=1, initialW=w_init),
            conv4_3=L.Convolution2D(None, 512, ksize=3, stride=1, pad=1, initialW=w_init),

            conv5_1=L.Convolution2D(None, 512, ksize=3, stride=1, pad=1, initialW=w_init),
            conv5_2=L.Convolution2D(None, 512, ksize=3, stride=1, pad=1, initialW=w_init),
            conv5_3=L.Convolution2D(None, 512, ksize=3, stride=1, pad=1, initialW=w_init),

            fc6=L.Convolution2D(None, 4096, ksize=7, stride=1, pad=0, initialW=w_init),
            fc7=L.Convolution2D(None, 4096, ksize=1, stride=1, pad=0, initialW=w_init),
            fc8=L.Convolution2D(None, 2, ksize=1, stride=1, pad=0, initialW=w_init)
        )

    def __call__(self, x, dropout=True):
        h = F.relu(self.conv1_1(x))
        h = F.relu(self.conv1_2(h))
        h = F.max_pooling_2d(h, ksize=2, stride=2)

        h = F.relu(self.conv2_1(h))
        h = F.relu(self.conv2_2(h))
        h = F.max_pooling_2d(h, ksize=2, stride=2)

        h = F.relu(self.conv3_1(h))
        h = F.relu(self.conv3_2(h))
        h = F.relu(self.conv3_3(h))
        h = F.max_pooling_2d(h, ksize=2, stride=2)

        h = F.relu(self.conv4_1(h))
        h = F.relu(self.conv4_2(h))
        h = F.relu(self.conv4_3(h))
        h = F.max_pooling_2d(h, ksize=2, stride=2)

        h = F.relu(self.conv5_1(h))
        h = F.relu(self.conv5_2(h))
        h = F.relu(self.conv5_3(h))
        h = F.max_pooling_2d(h, ksize=2, stride=2)

        h = F.dropout(F.relu(self.fc6(h)), train=dropout)
        h = F.dropout(F.relu(self.fc7(h)), train=dropout)
        h = self.fc8(h)

        return h