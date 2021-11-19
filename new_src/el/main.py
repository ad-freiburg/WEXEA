import random
import sqlite3
import json
import re
import torch
from tqdm import tqdm
import numpy as np
from model import BertForEntityClassification
from transformers import (
    AdamW,BertTokenizer, BertForNextSentencePrediction
)

class OurDataset(torch.utils.data.Dataset):
    def __init__(self, encodings):
        self.encodings = encodings
    def __getitem__(self, idx):
        return {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
    def __len__(self):
        return len(self.encodings.input_ids)

RE_LINKS = re.compile(r'\[{2}(.*?)\]{2}', re.DOTALL | re.UNICODE)
wexea_directory = '/media/michi/Data/wexea/new/'

id2title = json.load(open(wexea_directory + 'dictionaries/id2title.json'))
title2id = json.load(open(wexea_directory + 'dictionaries/title2Id.json'))
title2filename = json.load(open(wexea_directory + 'dictionaries/title2filename.json'))
#aliases = json.load(open(wexea_directory + 'dictionaries/aliases_pruned.json'))
priors = json.load(open(wexea_directory + 'dictionaries/priors_sorted.json'))
redirects = json.load(open(wexea_directory + 'dictionaries/redirects.json'))

stubs = json.load(open(wexea_directory + 'dictionaries/stubs.json'))
aliases = json.load(open(wexea_directory + 'dictionaries/aliases.json'))

MAX_NUM_CANDIDATES = 3
EPOCHS = 10

tokenizer = BertTokenizer.from_pretrained('bert-base-cased')
num_added_toks = tokenizer.add_tokens(["<e>","</e>"])
added_tokens = tokenizer.get_added_vocab()
print('We have added', num_added_toks, 'tokens')
model = BertForNextSentencePrediction.from_pretrained('bert-base-cased')
model.resize_token_embeddings(len(tokenizer))

def get_abstract(title):
    try:
        with open(title2filename[title]) as f:
            for line in f:
                line = line.strip()
                if len(line) > 0:
                    while True:
                        match = re.search(RE_LINKS, line)
                        if match:
                            start = match.start()
                            end = match.end()
                            entity = match.group(1)
                            alias = entity
                            pos_bar = entity.find('|')
                            if pos_bar > -1:
                                alias = entity[pos_bar + 1:]
                                entity = entity[:pos_bar]
                            line = line[:start] + alias + line[end:]

                        else:
                            break

                    return line

    except:
        pass
    return ""


def process(document):
    sentence_a = []
    sentence_b = []
    ps = []
    res = []
    ss = []
    labels = []

    test_dataset = {'contexts':[], 'candidates':[], 'ids':[]}

    found = 0
    not_found = 0
    not_found_but_title = 0

    mention_in_stubs = 0
    mention_in_stubs_correct = 0
    mention_single = 0
    mention_in_aliases = 0

    match_id = 0
    not_match_id = 0

    for tuple in document:
        sentence = tuple[0]
        mentions = tuple[1]
        for tuple in mentions:
            start = tuple[0]
            id = int(tuple[1])
            end = tuple[2]

            mention = ' '.join(sentence[start:end])
            current_text = (sentence[:start],mention, sentence[end:])

            context = ' '.join(current_text[0]) + ' <e>' + current_text[1] + '</e> ' + ' '.join(current_text[2])
            context = context.strip()

            test_dataset['contexts'].append(context)


            candidates = []
            if mention in priors:
                candidates.extend(priors[mention])
            if mention.lower() in priors:
                candidates.extend(priors[mention.lower()])
            elif mention[0].upper() + mention[1:].lower() in priors:
                candidates.extend(priors[mention[0].upper() + mention[1:].lower()])

            if mention in redirects:
                candidates.append((redirects[mention],3.0))
            if mention in stubs:
                candidates.append((mention, 2.0))

            new_candidates = []
            seen = set()
            for candidate in candidates:
                name = candidate[0]
                p = candidate[1]

                if name not in seen:
                    new_candidates.append((name,p))
                    seen.add(name)

            candidates = new_candidates

            if len(candidates) > 0:
                new_candidates = []
                for candidate in candidates:
                    if candidate[0] in title2id:
                        new_candidates.append(candidate)

                candidates = new_candidates

            if len(candidates) > 0:

                test_dataset['ids'].append(id)
                if len(candidates) > MAX_NUM_CANDIDATES:
                    candidates = candidates[:MAX_NUM_CANDIDATES]

                candidate_l = []


                if len(candidates) == 1:
                    candidate_name = candidates[0][0]
                    if candidate_name in title2id and title2id[candidate_name] == id:
                        match_id += 1
                    else:
                        if str(id) in id2title:
                            title = id2title[str(id)]
                            #print(candidate_name + " vs " + title + " (" + mention + ")")

                        not_match_id += 1


                for candidate in candidates:
                    abstract = get_abstract(candidate[0])
                    sentence_a.append(context)
                    sentence_b.append(abstract)
                    prior = candidate[1]
                    redirect = 0
                    stub = 0
                    if prior == 2.0:
                        # stub
                        stub = 1
                        prior = 0.0
                    elif prior == 3.0:
                        # redirect
                        redirect = 1
                        prior = 0.0

                    ps.append(prior)
                    ss.append(stub)
                    res.append(redirect)

                    if title2id[candidate[0]] == id:
                        labels.append(1)
                        found += 1
                    else:
                        labels.append(0)
                    candidate_l.append((abstract, candidate[0], candidate[1]))
                test_dataset['candidates'].append(candidate_l)
                if len(candidate_l) == 1:
                    mention_single += 1
            else:
                not_found += 1
                test_dataset['ids'].append(id)
                test_dataset['candidates'].append([])

    inputs = tokenizer(sentence_a, sentence_b, return_tensors='pt', max_length=128, truncation=True,padding='max_length')
    inputs['labels'] = torch.LongTensor([labels]).T
    inputs['priors'] = torch.FloatTensor([ps]).T
    inputs['redirects'] = torch.FloatTensor([res]).T
    inputs['stubs'] = torch.FloatTensor([ss]).T

    dataset = OurDataset(inputs)

    print("Found: " + str(found))
    print("not found: " + str(not_found))
    print("not found but title: " + str(not_found_but_title))
    print("mention in aliases: " + str(mention_in_aliases))
    print("mention in stubs: " + str(mention_in_stubs))
    print("mention in stubs correct: " + str(mention_in_stubs_correct))
    print("mention single: " + str(mention_single))
    print("match title: " + str(match_id))
    print("not match title: " + str(not_match_id))

    return dataset,test_dataset


def get_dataset(type=None):
    print("get: " + type)
    filename = '/media/michi/Data/datasets/el/datasets/aida_' + type + ".txt"
    with open(filename) as f:
        current_sentence = []
        document = []
        mentions = []
        for line in f:
            line = line.strip()
            if len(line) == 0 or line.startswith("DOCSTART") or line.startswith("DOCEND") or line == "*NL*":
                if len(mentions) > 0:
                    # process(current_sentence,mentions)
                    document.append((current_sentence, mentions))

                current_sentence = []
                mentions = []
            else:
                if line.startswith("MMSTART"):
                    mentions.append([len(current_sentence)])
                    mentions[-1].append(line[8:])
                elif line.startswith("MMEND"):
                    mentions[-1].append(len(current_sentence))
                else:
                    current_sentence.append(line)

        if len(mentions) > 0:
            # process(current_sentence, mentions)
            document.append((current_sentence, mentions))

        return process(document)

def metrics(preds, out_label_ids):
    tp = 0
    fp = 0
    fn = 0

    for i in range(len(preds)):
        prediction = preds[i]
        label = out_label_ids[i]

        if prediction == 1 and label == 1:
            tp += 1
        elif prediction == 1 and label == 0:
            fp += 1
        elif prediction == 0 and label == 1:
            fn += 1


    precision = 0.0
    recall = 0.0
    f1 = 0.0
    if tp > 0 or fp > 0:
        precision = tp / (tp + fp)
    if tp > 0 or fn > 0:
        recall = tp / (tp + fn)
    if precision > .0 or recall > .0:
        f1 = (2 * precision * recall) / (precision + recall)

    return precision, recall, f1, tp, fp, fn

def run_test(test_dataset):
    correct = 0
    incorrect = 0

    one_candidate = {'correct':0,'incorrect':0}
    zero_candidate = 0
    more_candidates = {'correct':0,'incorrect':0}

    data_length = len(test_dataset['contexts'])
    for i in range(data_length):
        context = test_dataset['contexts'][i]
        candidates = test_dataset['candidates'][i]
        id = test_dataset['ids'][i]

        if len(candidates) == 0:
            incorrect += 1
            zero_candidate += 1
        elif len(candidates) == 1:
            candidate = candidates[0][1]
            if title2id[candidate] == id:
                correct += 1
                one_candidate['correct'] += 1
            else:
                incorrect += 1
                one_candidate['incorrect'] += 1
        else:
            best_candidate_pred = 0.0
            best_candidate = None
            for j in range(len(candidates)):
                abstract = candidates[j][0]
                candidate = candidates[j][1]
                prior = candidates[j][2]
                redirect = 0
                stub = 0
                if prior == 2.0:
                    #stub
                    stub = 1
                    prior = 0.0
                elif prior == 3.0:
                    #redirect
                    redirect = 1
                    prior = 0.0



                sentence_a = [context]
                sentence_b = [abstract]
                ps = [prior]
                ss = [stub]
                res = [redirect]

                inputs = tokenizer(sentence_a, sentence_b, return_tensors='pt', max_length=128, truncation=True,
                                   padding='max_length')
                inputs['priors'] = torch.FloatTensor([ps]).T
                inputs['redirects'] = torch.FloatTensor([res]).T
                inputs['stubs'] = torch.FloatTensor([ss]).T



                input_ids = inputs['input_ids'].to(device)
                token_type_ids = inputs['token_type_ids'].to(device)
                attention_mask = inputs['attention_mask'].to(device)
                is_redirect = batch['redirects'].to(device)
                is_stub = batch['stubs'].to(device)

                ps = inputs['priors'].to(device)

                outputs = model(input_ids, attention_mask=attention_mask,is_redirect=is_redirect,is_stub=is_stub, token_type_ids=token_type_ids, priors=ps)

                logits = outputs[0]

                preds = logits.detach().cpu().numpy()
                f_x = np.exp(preds[0]) / np.sum(np.exp(preds[0]))
                prediction = f_x[1]
                if prediction > best_candidate_pred:
                    best_candidate_pred = prediction
                    best_candidate = candidate

            if id == title2id[best_candidate]:
                correct += 1
                more_candidates['correct'] += 1
            else:
                incorrect += 1
                more_candidates['incorrect'] += 1

    print("correct: " + str(correct))
    print("incorrect: " + str(incorrect))
    print("more candidates: ")
    print(more_candidates)
    print("one candidate:")
    print(one_candidate)
    print("zero candidate: " + str(zero_candidate))
    acc = correct / (correct + incorrect)
    print("acc: " + str(acc))

def evaluate(loader):
    eval_loss = 0.0
    nb_eval_steps = 0
    preds = None
    out_label_ids = None
    for batch in tqdm(loader, desc="Evaluating"):
        model.eval()
        input_ids = batch['input_ids'].to(device)
        token_type_ids = batch['token_type_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        is_redirect = batch['redirects'].to(device)
        is_stub = batch['stubs'].to(device)

        ps = batch['priors'].to(device)

        labels = batch['labels'].to(device)

        with torch.no_grad():
            outputs = model(input_ids, attention_mask=attention_mask,is_redirect=is_redirect,is_stub=is_stub,
                            token_type_ids=token_type_ids, priors=ps, labels=labels)

            tmp_eval_loss, logits = outputs[:2]

            eval_loss += tmp_eval_loss.mean().item()
        nb_eval_steps += 1
        if preds is None:
            preds = logits.detach().cpu().numpy()
            out_label_ids = labels.detach().cpu().numpy()
        else:
            preds = np.append(preds, logits.detach().cpu().numpy(), axis=0)
            out_label_ids = np.append(out_label_ids, labels.detach().cpu().numpy(), axis=0)

    preds = np.argmax(preds, axis=1)
    precision, recall, f1, tp, fp, fn = metrics(preds, out_label_ids)
    print("precision: %f, recall: %f, f1: %f" % (precision, recall, f1))
    print("tp: %d, fp: %d, fn: %d" % (tp, fp, fn))


dataset_train, test_dataset_train = get_dataset(type='train')
dataset_dev, test_dataset_dev = get_dataset(type='dev')
dataset_test, test_dataset_test = get_dataset(type='test')

loader_train = torch.utils.data.DataLoader(dataset_train, batch_size=16, shuffle=True)
loader_dev = torch.utils.data.DataLoader(dataset_dev, batch_size=16, shuffle=False)

weight_decay = 0.0
learning_rate = 5e-5
adam_epsilon = 1e-8

no_decay = ["bias", "LayerNorm.weight"]
optimizer_grouped_parameters = [
    {
        "params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
        "weight_decay": weight_decay,
    },
    {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
optim = AdamW(optimizer_grouped_parameters, lr=learning_rate, eps=adam_epsilon)

model.to(device)


for epoch in range(EPOCHS):
    # setup loop with TQDM and dataloader
    loop = tqdm(loader_train, leave=True)
    loss_acc = 0.0
    batches = 0.0
    for batch in loop:
        batches += 1.0
        # initialize calculated gradients (from prev step)
        optim.zero_grad()
        # pull all tensor batches required for training
        input_ids = batch['input_ids'].to(device)
        token_type_ids = batch['token_type_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        is_redirect = batch['redirects'].to(device)
        is_stub = batch['stubs'].to(device)

        ps = batch['priors'].to(device)

        labels = batch['labels'].to(device)

        outputs = model(input_ids, attention_mask=attention_mask,is_redirect=is_redirect,is_stub=is_stub,
                        token_type_ids=token_type_ids,priors=ps,
                        labels=labels)
        # extract loss
        loss = outputs.loss

        loss_acc += loss.item()


        # calculate loss for every parameter that needs grad update
        loss.backward()
        # update parameters
        optim.step()
        # print relevant info to progress bar
        loop.set_description(f'Epoch {epoch}')
        loop.set_postfix(loss=loss_acc/batches)

    print("evaluate")
    evaluate(loader_dev)


# test_dataset = {'contexts':[], 'candidates':[], 'titles':[]}
print("test dev")
run_test(test_dataset_dev)

print("test test")
run_test(test_dataset_test)





