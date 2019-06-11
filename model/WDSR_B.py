import torch
import torch.nn as nn
import torch.nn.init as init
from torch.autograd import Variable


class ResBlock(nn.Module):
    def __init__(
            self, n_feats, kernel_size, wn, act=nn.ReLU(True), res_scale=1):
        super(ResBlock, self).__init__()
        self.res_scale = res_scale
        body = list()
        expand = 6  # todo
        linear = 0.8  # todo
        body.append(
            wn(nn.Conv2d(n_feats, n_feats * expand, 1, padding=1 // 2)))
        body.append(act)
        body.append(
            wn(nn.Conv2d(n_feats * expand, int(n_feats * linear), 1, padding=1 // 2)))
        body.append(
            wn(nn.Conv2d(int(n_feats * linear), n_feats, kernel_size, padding=kernel_size // 2)))

        self.body = nn.Sequential(*body)

    def forward(self, x):
        res = self.body(x) * self.res_scale
        res += x
        return res


class MODEL(nn.Module):
    def __init__(self, cuda=True, scale=4, n_res=8, n_feats=64, res_scale=1, n_colors=3,
                 kernel_size=3, mean=(0.38824835, 0.48927346, 0.50467293)):
        super(MODEL, self).__init__()
        # hyper-params
        act = nn.ReLU(True)

        # wn = lambda x: x
        # wn = lambda x: torch.nn.utils.weight_norm(x)
        def wn(x):
            return torch.nn.utils.weight_norm(x)

        self.rgb_mean = Variable(torch.FloatTensor(mean)).view([1, 3, 1, 1])
        if cuda:
            self.rgb_mean = self.rgb_mean.cuda()

        # define head module
        head = list()
        head.append(wn(nn.Conv2d(n_colors, n_feats, 3, padding=3 // 2)))

        # define body module
        body = list()
        for i in range(n_res):
            body.append(ResBlock(n_feats, kernel_size, wn, act, res_scale))

        # define tail module
        tail = list()
        out_feats = scale * scale * n_colors
        tail.append(wn(nn.Conv2d(n_feats, out_feats, 3, padding=3 // 2)))
        tail.append(nn.PixelShuffle(scale))

        # define skip module
        skip = list()
        skip.append(wn(nn.Conv2d(n_colors, out_feats, 5, padding=5 // 2)))
        skip.append(nn.PixelShuffle(scale))

        # make object members
        self.head = nn.Sequential(*head)
        self.body = nn.Sequential(*body)
        self.tail = nn.Sequential(*tail)
        self.skip = nn.Sequential(*skip)

        # 初始化权重，参考EDVR
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                init.xavier_normal_(m.weight, gain=init.calculate_gain('relu'))
                if m.bias is not None:
                    init.normal_(m.bias, 0.0001)
            elif isinstance(m, nn.Linear):
                init.xavier_normal_(m.weight, gain=init.calculate_gain('relu'))
                if m.bias is not None:
                    init.normal_(m.bias, 0.0001)
        return

    def forward(self, x):
        x = (x - self.rgb_mean * 255) / 127.5
        s = self.skip(x)
        x = self.head(x)
        x = self.body(x)
        x = self.tail(x)
        x += s
        x = x * 127.5 + self.rgb_mean * 255
        return x
