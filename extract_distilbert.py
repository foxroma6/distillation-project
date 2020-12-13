# coding=utf-8
# Copyright 2019-present, the HuggingFace Inc. team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Preprocessing script before training DistilBERT.
Specific to BERT -> DistilBERT.
"""
from transformers import BertForMaskedLM
import torch
import argparse
import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Extraction some layers of the full BertForMaskedLM or RObertaForMaskedLM for Transfer Learned Distillation")
    parser.add_argument("--model_type", default="bert", choices=["bert"])
    parser.add_argument("--model_name", default='monologg/kobert-lm', type=str)
    parser.add_argument("--vocab_transform", action='store_true')
    parser.add_argument("--num_layer", default=3, type=int)
    args = parser.parse_args()

    args.dump_checkpoint = 'serialization_dir/{}_layer.pth'.format(args.num_layer)

    if not os.path.exists('serialization_dir'):
        os.mkdir('serialization_dir')

    if args.model_type == 'bert':
        model = BertForMaskedLM.from_pretrained(args.model_name)
        prefix = 'bert'
    else:
        raise ValueError(f'args.model_type should be "bert".')

    state_dict = model.state_dict()
    compressed_sd = {}

    for w in ['word_embeddings', 'position_embeddings']:
        compressed_sd[f'distilbert.embeddings.{w}.weight'] = \
            state_dict[f'{prefix}.embeddings.{w}.weight']
    for w in ['weight', 'bias']:
        compressed_sd[f'distilbert.embeddings.LayerNorm.{w}'] = \
            state_dict[f'{prefix}.embeddings.LayerNorm.{w}']

    std_idx = 0
    layer_lst = []
    if args.num_layer == 6:
        layer_lst = [0, 2, 4, 7, 9, 11]
    elif args.num_layer == 3:
        layer_lst = [0, 4, 8]
    elif args.num_layer == 1:
        layer_lst = [5]
    else:
        raise Exception("Num of layer only 1, 3, 6")

    for teacher_idx in layer_lst:
        for w in ['weight', 'bias']:
            compressed_sd[f'distilbert.transformer.layer.{std_idx}.attention.q_lin.{w}'] = \
                state_dict[f'{prefix}.encoder.layer.{teacher_idx}.attention.self.query.{w}']
            compressed_sd[f'distilbert.transformer.layer.{std_idx}.attention.k_lin.{w}'] = \
                state_dict[f'{prefix}.encoder.layer.{teacher_idx}.attention.self.key.{w}']
            compressed_sd[f'distilbert.transformer.layer.{std_idx}.attention.v_lin.{w}'] = \
                state_dict[f'{prefix}.encoder.layer.{teacher_idx}.attention.self.value.{w}']

            compressed_sd[f'distilbert.transformer.layer.{std_idx}.attention.out_lin.{w}'] = \
                state_dict[f'{prefix}.encoder.layer.{teacher_idx}.attention.output.dense.{w}']
            compressed_sd[f'distilbert.transformer.layer.{std_idx}.sa_layer_norm.{w}'] = \
                state_dict[f'{prefix}.encoder.layer.{teacher_idx}.attention.output.LayerNorm.{w}']

            compressed_sd[f'distilbert.transformer.layer.{std_idx}.ffn.lin1.{w}'] = \
                state_dict[f'{prefix}.encoder.layer.{teacher_idx}.intermediate.dense.{w}']
            compressed_sd[f'distilbert.transformer.layer.{std_idx}.ffn.lin2.{w}'] = \
                state_dict[f'{prefix}.encoder.layer.{teacher_idx}.output.dense.{w}']
            compressed_sd[f'distilbert.transformer.layer.{std_idx}.output_layer_norm.{w}'] = \
                state_dict[f'{prefix}.encoder.layer.{teacher_idx}.output.LayerNorm.{w}']
        std_idx += 1

    compressed_sd[f'vocab_projector.weight'] = state_dict[f'cls.predictions.decoder.weight']
    compressed_sd[f'vocab_projector.bias'] = state_dict[f'cls.predictions.bias']
    if args.vocab_transform:
        for w in ['weight', 'bias']:
            compressed_sd[f'vocab_transform.{w}'] = state_dict[f'cls.predictions.transform.dense.{w}']
            compressed_sd[f'vocab_layer_norm.{w}'] = state_dict[f'cls.predictions.transform.LayerNorm.{w}']

    print(f'N layers selected for distillation: {std_idx}')
    print(f'Number of params transfered for distillation: {len(compressed_sd.keys())}')

    print(f'Save transfered checkpoint to {args.dump_checkpoint}.')
    torch.save(compressed_sd, args.dump_checkpoint)