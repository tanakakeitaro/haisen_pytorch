import numpy as np
import pickle
import codecs
import torch
import torch.nn as nn
import torch.nn.functional as F

from mecab_test import user_input

# 辞書の読み込み
def pickle_load(path):
    with open(path, mode='rb') as f:
        data = pickle.load(f)
        return data
id_to_word = pickle_load('static/id_to_word_marusen575.pickle')
word_to_id = pickle_load('static/word_to_id_marusen575.pickle')

# embedding_dim, hidden_dim, vocab_sizeを指定
embedding_dim = 50
hidden_dim = 128
vocab_size = len(word_to_id)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

#### Seq2Seqモデルの定義 ####
class Encoder(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, batch_size=100):
        super(Encoder, self).__init__()
        self.hidden_dim = hidden_dim
        self.batch_size = batch_size

        self.word_embeddings = nn.Embedding(vocab_size, embedding_dim, )
        self.gru = nn.GRU(embedding_dim, hidden_dim, batch_first=True)

    def forward(self, indices):
        embedding = self.word_embeddings(indices)
        if embedding.dim() == 2:
            embedding = torch.unsqueeze(embedding, 1)
        _, state = self.gru(embedding, torch.zeros(1, self.batch_size, self.hidden_dim, device=device))
        
        return state

class Decoder(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, batch_size=100):
        super(Decoder, self).__init__()
        self.hidden_dim = hidden_dim
        self.batch_size = batch_size

        self.word_embeddings = nn.Embedding(vocab_size, embedding_dim, )
        self.gru = nn.GRU(embedding_dim, hidden_dim, batch_first=True)
        self.output = nn.Linear(hidden_dim, vocab_size)

    def forward(self, index, state):
        embedding = self.word_embeddings(index)
        if embedding.dim() == 2:
            embedding = torch.unsqueeze(embedding, 1)
        gruout, state = self.gru(embedding, state)
        output = self.output(gruout)
        return output, state
#### モデルの定義終わり ####

def ai_return(text):
    # ユーザーのインプット読み込み→形態素解析の結果をword_listに格納→idに変換
    word_list = user_input(text)
    idlist = [word_to_id[w] for w in word_list]
    # 長さを5に合わせるため、2を末尾に加えてパディング
    while len(idlist) < 5:
        idlist.append(2)
    # Encoder, Decoderクラスのインスタンス化
    encoder = Encoder(vocab_size, embedding_dim, hidden_dim, batch_size=1).to(device)
    decoder = Decoder(vocab_size, embedding_dim, hidden_dim, batch_size=1).to(device)
    #推論
    model_name = "static/seq2seq_calculator_v{}.pt".format("90")
    checkpoint = torch.load(model_name)
    encoder.load_state_dict(checkpoint["encoder_model"])
    decoder.load_state_dict(checkpoint["decoder_model"])
    with torch.no_grad():
        # テンソルに変換
        input_tensor = torch.tensor([idlist], device=device)
        # encoderは隠れ状態を返す
        state = encoder(input_tensor)
        # 変数tokenいらないけどわかりやすさのために
        token = '<bos>'
        predict_7 = [word_to_id[token]]
        # 推論
        index = word_to_id[token]
        input_tensor = torch.tensor([index], device=device)
        output, default_state = decoder(input_tensor, state)
        # outputをsoftmaxで確率に変換し、大きい順に並べ替える
        prob = F.softmax(torch.squeeze(output), dim=0)
        indices = torch.argsort(prob.cpu().detach(), descending=True)
        # 並び替えたリストをもとに、値が大きい順（上位3つ）に予測していく
        naka7_list = []
        for i in indices[:3]:
            i = i.item()
            state = default_state
            pre_7 = [i]
            for _ in range(8):
                input_tensor = torch.tensor([i], device=device)
                output, state = decoder(input_tensor, state)
                # 配列の最大値のインデックスを返し、iを更新する
                prob = F.softmax(torch.squeeze(output), dim=0)
                i = torch.argmax(prob.cpu().detach()).item()
                pre_7.append(i)
            # パディングの2を取り除いて新しいリストを生成
            predict = [id_to_word[j] for j in pre_7 if j != 2]
            predict.pop(-1)
            predict = ''.join(predict)
            naka7_list.append(predict)

    return naka7_list
