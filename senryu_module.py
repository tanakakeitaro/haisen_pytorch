import numpy as np
import pickle
import torch
import torch.nn as nn
import torch.nn.functional as F
import re
import MeCab
from transformers import BertJapaneseTokenizer

embedding_dim = 300
hidden_dim = 256
vocab_size = 32000
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer = BertJapaneseTokenizer.from_pretrained('cl-tohoku/bert-base-japanese-whole-word-masking')

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

# 中七が七音か判定する関数
def judge_7(predict):
    m = MeCab.Tagger()
    node = m.parseToNode(predict).next # 解析してノードに変換
    pronunciation = ''
    while node.next: # nodeがfalseになるまで
        yomi = node.feature.split(",")[-2] # 分析結果から読みを取得
        node = node.next # 次の要素に移動（末尾の場合はfalseになる）
        pronunciation += yomi
    kana_count = [letter for letter in re.findall(r'.[ァィゥェォャュョ]?', pronunciation)]

    return pronunciation

# 上五に対して中七を返す関数
def senryu_return(text):
    id_list = tokenizer.encode(text)
    del id_list[0]
    del id_list[-1]
    # 長さを合わせるためパディング
    while len(id_list) < 10:
        id_list.append(0)
    # Encoder, Decoderクラスのインスタンス化
    encoder = Encoder(vocab_size, embedding_dim, hidden_dim, batch_size=1).to(device)
    decoder = Decoder(vocab_size, embedding_dim, hidden_dim, batch_size=1).to(device)
    #推論
    model_name = "static/seq2seq_bert_test_v{}.pt".format("200")
    checkpoint = torch.load(model_name, map_location='cpu')
    encoder.load_state_dict(checkpoint["encoder_model"])
    decoder.load_state_dict(checkpoint["decoder_model"])

    with torch.no_grad(): # 勾配計算させない
        # テンソルに変換
        input_tensor = torch.tensor([id_list], device=device)
        # encoderは隠れ状態を返す
        state = encoder(input_tensor)
        # 変数tokenいらないけどわかりやすさのために
        token = '[CLS]'
        predict_7 = [tokenizer.convert_tokens_to_ids(token)]
        # 推論
        index = tokenizer.convert_tokens_to_ids(token)
        input_tensor = torch.tensor([index], device=device)
        output, default_state = decoder(input_tensor, state)
        # outputをsoftmaxで確率に変換し、大きい順に並べ替える
        prob = F.softmax(torch.squeeze(output), dim=0)
        indices = torch.argsort(prob.cpu().detach(), descending=True)
        # 並び替えたリストをもとに、値が大きい順（上位3つ）に予測していく
        naka7_list = []
        for i in indices[:]:
            i = i.item()
            state = default_state
            pre_7 = [i]
            while i != 3:
                input_tensor = torch.tensor([i], device=device)
                output, state = decoder(input_tensor, state)
                # 配列の最大値のインデックスを返し、iを更新する
                prob = F.softmax(torch.squeeze(output), dim=0)
                i = torch.argmax(prob.cpu().detach()).item()
                pre_7.append(i)
            # [SEP]の3を取り除いて新しいリストを生成
            predict = [tokenizer.convert_ids_to_tokens(j) for j in pre_7 if j != 3]
            predict = ''.join(predict).replace('#', '').replace('[UNK]', '')
            # 中の句が七音だった場合はリストに加える
            pronunciation = judge_7(predict)
            if len(pronunciation) == 7:
                naka7_list.append(predict)
            # リストに中七が三つ入ったらbreak
            if len(naka7_list) == 3:
                break

        # 七音の中の句が三つにならなかった場合は、先頭の中七を三つ返す
        if len(naka7_list) < 3:
            naka7_list = list(naka7_list[0]*3)

    return naka7_list