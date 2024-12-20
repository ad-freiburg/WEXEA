import argparse
import re
import os
import json
import time
import datetime
import gender_guesser.detector as gender
from utils import create_file_name_and_directory, create_filename, RE_LINKS, CLEANUP
from entity_linker.readers.inference_reader import InferenceReader
from entity_linker.models.figer_model.el_model import ELModel
from entity_linker.readers.config import Config
from entity_linker.readers.vocabloader import VocabLoader
import tensorflow as tf

ARTICLE_OUTPUTPATH = "articles_final"
NER_TAGS = {"SET", "ORDINAL", "PER", "LOC", "ORG", "DATE","NUMBER","MISC","LOCATION","PERSON","ORGANIZATION",'DURATION','MONEY','PERCENT','TIME'}


def process_article(text, title, corefs, aliases_reverse, coref_assignments, reader, model, new_filename):

    current_corefs = {}
    complete_content = ''
    for line in text.split('\n'):
        # Natalie Prange: Strip only newlines, not rogue trailing whitespaces
        line = line.strip("\n")

        if len(line) == 0:
            complete_content += '\n'
            continue

        if line.startswith('='):
            complete_content += '\n' + line
            continue

        while not args.input_dir:
            # Natalie Prange: We don't want a cleanup for our benchmarks, since it changes the article
            # text and thus messes with span starts and ends
            found = False
            for tuple in CLEANUP:
                # re.sub(tuple[0],tuple[1])
                match = re.search(tuple[0], line)
                if match:
                    found = True
                    start = match.start()
                    end = match.end()
                    line = line[:start] + tuple[1] + line[end:]

            if not found:
                break

        positions = []
        el_idxs = []
        found_some_corefs = False
        previous_end = 0
        ignore_line = False
        while True:
            match = re.search(RE_LINKS, line)
            if match:
                start = match.start()
                end = match.end()
                entity = match.group(1)
                parts = entity.split('|')
                if (len(parts) != 3 and parts[-1] not in NER_TAGS) or '[[' in entity or ']]' in entity:
                    #TODO: investigate why this happens, it could be a thumbnail in the middle or end of a paragraph of text. ignore it for now.
                    ignore_line = True
                    break

                alias = parts[-2]

                if ("multiple" in parts[-1] or 'part_of_seen_entity' in parts[-1]) and '###' in parts[0]:
                    # use entity linker, which we will deal with later
                    el_idxs.append(len(positions))
                elif 'PERSON' in parts[-1] and parts[0].lower() in coref_assignments and coref_assignments[parts[0].lower()] in current_corefs:
                    # found a coref of a person
                    parts = [current_corefs[coref_assignments[parts[0].lower()]], alias, 'PERSON_coref']
                elif parts[0] in corefs:
                    for c in corefs[parts[0]]:
                        c = c.strip()
                        if c == 'he':
                            c = 'male'
                        elif c == 'she':
                            c = 'female'
                        current_corefs[c] = parts[0]
                elif "PERSON" in parts[-1]:
                    tokens = parts[0].split(' ')
                    types = {'male': 0, 'female': 0, 'unknown': 0, 'andy': 0}
                    for token in tokens:
                        t = gender_detector.get_gender(token)
                        if t.startswith('mostly_'):
                            t = t[7:]
                        types[t] += 1

                    if types['male'] > 0 and types['female'] == 0:
                        current_corefs['male'] = parts[0]
                    elif types['male'] == 0 and types['female'] > 0:
                        current_corefs['female'] = parts[0]

                positions.append((start, len(alias), parts))

                text_in_between = line[previous_end:start].lower()
                line = line[:start] + alias + line[end:]

                for c in current_corefs:
                    if c != 'male' and c != 'female':
                        current_idx = 0
                        while True:
                            idx = text_in_between[current_idx:].find(c)
                            if idx > -1:
                                found_some_corefs = True
                                start = idx + current_idx
                                entity = current_corefs[c]
                                positions.append((start + previous_end, len(c), [entity, c, 'non_person_coref']))
                                current_idx = start + len(c)
                            else:
                                break

                previous_end = match.start() + len(alias)

            else:
                text_in_between = line[previous_end:].lower()
                for c in current_corefs:
                    if c != 'male' and c != 'female':
                        current_idx = 0
                        while True:
                            idx = text_in_between[current_idx:].find(c)
                            if idx > -1:
                                found_some_corefs = True
                                start = idx + current_idx
                                entity = current_corefs[c]
                                positions.append((start + previous_end, len(c), [entity, c, 'non_person_coref']))
                                current_idx = start + len(c)
                            else:
                                break
                break


        if ignore_line:
            continue

        # disambiguate here!
        if len(el_idxs) > 0:
            el_text = line

            disambiguated = False
            try:
                for i in reversed(range(len(el_idxs))):
                    position = positions[el_idxs[i]]
                    start = position[0]
                    length = position[1]
                    parts = position[2]

                    el_text = el_text[:start] + '[[' + '|'.join(parts) + ']]' + el_text[start+length:]

                reader.loadTestDoc(el_text)

                mentions = reader.mentions

                if reader.disambiguations_counter > 0:
                    # print(reader.disambiguations_counter)
                    (predTypScNPmat_list,
                     widIdxs_list,
                     priorProbs_list,
                     textProbs_list,
                     jointProbs_list,
                     evWTs_list,
                     pred_TypeSetsList) = model.doInference()

                new_mentions = {}
                mentionnum = 0
                for i in range(len(mentions)):
                    mention = mentions[i]
                    alias = mention.surface
                    mention_start = mention.char_start
                    mention_length = mention.link_len
                    sent_idx = mention.sentence_idx
                    mention_type = mention.type

                    if sent_idx not in new_mentions:
                        new_mentions[sent_idx] = []

                    if i in reader.disambiguations and len(mention.entities) > 1:

                        [evWTs, evWIDS, evProbs] = evWTs_list[mentionnum]
                        disambiguation = mention.wikititles[evWIDS[2]]
                        entity = disambiguation
                        mentionnum += 1
                    else:
                        entity = mention.entities[0]

                    position = positions[el_idxs[i]]
                    start = position[0]
                    length = position[1]
                    parts = position[2]
                    positions[el_idxs[i]] = (start, length, [entity, parts[-2], parts[-1]])

                disambiguated = True
            except:
                disambiguated = False

            if not disambiguated:
                for i in reversed(range(len(el_idxs))):
                    position = positions[el_idxs[i]]
                    start = position[0]
                    length = position[1]
                    parts = position[2]
                    alias = parts[-2]
                    candidates = parts[0].split('###')

                    best_candidate = candidates[0]
                    max_matches = 0
                    for candidate in candidates:
                        if candidate in aliases_reverse and alias in aliases_reverse[candidate] and \
                                aliases_reverse[candidate][alias] > max_matches:
                            max_matches = aliases_reverse[candidate][alias]
                            best_candidate = candidate
                    entity = best_candidate
                    parts = [entity, alias, parts[-1]]

                    positions[el_idxs[i]] = (start, length, [entity, alias, parts[-1]])


        # sort positions and then resolve if found some non person corefs
        if found_some_corefs:
            positions.sort(key=lambda x: x[0])


        for i in reversed(range(len(positions))):
            tuple = positions[i]
            start = tuple[0]
            length = tuple[1]
            annotation = '|'.join(tuple[2])

            line = line[:start] + '[[' + annotation + ']]' + line[start + length:]

        complete_content += '\n' + line

    if args.input_dir:
        filename = new_filename
    else:
        filename = create_file_name_and_directory(title, outputpath + ARTICLE_OUTPUTPATH + '/')
    with open(filename, 'w') as f:
        f.write(complete_content.strip())


def process_articles(filename2title,filenames, corefs, aliases_reverse, coref_assignments, reader, model):
    start_time = time.time()

    print('start processing')

    counter_all = 0

    new_filename2title = {}

    for i in range(len(filenames)):
        filename = filenames[i]
        title = filename2title[filename]

        if args.input_dir:
            new_filename = articlepath + filename[filename.rfind("/") + 1:]
        else:
            new_filename, _, _, _ = create_filename(title, outputpath + ARTICLE_OUTPUTPATH + '/')
        new_filename2title[new_filename] = title

        if not os.path.isfile(new_filename) or args.input_dir:
            with open(filename) as f:
                text = f.read()
                process_article(text,title,corefs, aliases_reverse, coref_assignments, reader, model, new_filename)

        counter_all += 1
        if counter_all % 1000 == 0:
            time_per_article = (time.time() - start_time) / counter_all
            print("articles: " + str(counter_all) + ", avg time: " + str(time_per_article), end='\r')

    print("articles processed: " + str(counter_all))

    if not args.input_dir:
        with open(dictionarypath + 'filename2title_final.json', 'w') as f:
            json.dump(new_filename2title, f)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print("elapsed time: %s" % str(datetime.timedelta(seconds=elapsed_time)))


if (__name__ == "__main__"):
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_dir", type=str, help="Input directory with articles")
    args = parser.parse_args()

    config = json.load(open('config/config.json'))
    num_processes = config['processes']
    wikipath = config['wikipath']
    outputpath = config['outputpath']
    dictionarypath = outputpath + 'dictionaries/'
    articlepath = outputpath + ARTICLE_OUTPUTPATH + '/' if not args.input_dir else args.input_dir.strip("/")[:-1] + "4/"

    if args.input_dir and not args.input_dir.strip("/").endswith("_parsed_3"):
        print("Input directory must be the output of parser_3.py")
        exit(1)

    try:
        mode = 0o755
        os.mkdir(articlepath, mode)
    except OSError:
        print("directories exist already")

    language = 'en'
    if 'language' in config:
        language = config['language']

    print("LANGUAGE: " + language)

    if language == 'de':
        coref_assignments = {'er': 'male', 'ihn': 'male', 'ihm': 'male', 'sein': 'male', 'seine': 'male', 'seiner': 'male', 'seinem': 'male', 'seinen': 'male', 'seines': 'male',
                             'sie': 'female', 'ihr': 'female', 'ihre': 'female', 'ihrem': 'female', 'ihres': 'female', 'ihrer': 'female'}
    elif language == 'fr':
        coref_assignments = {'il': 'male', 'lui': 'male', 'elle': 'female'}
    else:
        coref_assignments = {'he': 'male', 'his': 'male', 'him': 'male', 'himself': 'male', 'she': 'female', 'her': 'female', 'herself': 'female'}

    if args.input_dir:
        # Create custom filename2title dictionary for the articles in the input directory
        filename2title = {}
        for filename in os.listdir(args.input_dir):
            with open(args.input_dir.strip("/")[:-len("_parsed_3")] + "/" + filename) as f:
                title = f.readline().strip()
                filename2title[args.input_dir + filename] = title
    else:
        filename2title = json.load(open(dictionarypath + 'filename2title_3.json'))
    filenames = list(filename2title.keys())
    aliases_reverse = json.load(open(dictionarypath + 'aliases_reverse.json'))

    corefs = json.load(open('data/corefs.json'))
    gender_detector = gender.Detector()

    print("Read dictionaries.")

    config_proto = tf.compat.v1.ConfigProto()
    config_proto.allow_soft_placement = True
    config_proto.gpu_options.allow_growth = True

    tf.compat.v1.disable_eager_execution()

    checkpoint_dir = config['original_el_model']
    model_checkpoint_path = config['neural_el_model']
    replace_from = 'RNN/MultiRNNCell/Cell0/BasicLSTMCell'
    replace_to = 'rnn/multi_rnn_cell/cell_0/basic_lstm_cell'
    add_prefix = None
    state_dict = {}
    with tf.compat.v1.Session() as sess:
        # with sess.as_default():

        checkpoint = tf.train.get_checkpoint_state(checkpoint_dir)
        for var_name, _ in tf.train.list_variables(checkpoint_dir):
            # Load the variable
            var = tf.train.load_variable(checkpoint_dir, var_name)

            # Set the new name
            new_name = var_name
            if None not in [replace_from, replace_to]:
                new_name = new_name.replace(replace_from, replace_to)
                new_name = new_name.lower()
                new_name = new_name.replace('linear/matrix', 'kernel')
                new_name = new_name.replace('linear/bias', 'bias')
            if add_prefix:
                new_name = add_prefix + new_name

            if new_name != var_name:
                print('Renaming %s to %s.' % (var_name, new_name))
            var = tf.Variable(var, name=new_name)

        # Save the variables
        saver = tf.compat.v1.train.Saver()
        sess.run(tf.compat.v1.global_variables_initializer())
        saver.save(sess, model_checkpoint_path)

    tf.compat.v1.reset_default_graph()

    with tf.compat.v1.Session() as sess:
        config_el = Config('src/entity_linker/configs/config.ini', verbose=False)
        vocabloader = VocabLoader(config_el)
        reader = InferenceReader(config=config_el,
                                 vocabloader=vocabloader,
                                 num_cands=30,
                                 batch_size=1,
                                 strict_context=False,
                                 pretrain_wordembed=True,
                                 coherence=True)

        model = ELModel(
            sess=sess, reader=reader,
            max_steps=32000,
            pretrain_max_steps=32000,
            word_embed_dim=300,
            context_encoded_dim=100,
            context_encoder_num_layers=1,
            context_encoder_lstmsize=100,
            coherence_numlayers=1,
            jointff_numlayers=1,
            learning_rate=0.005,
            dropout_keep_prob=1.0,
            reg_constant=0.00,
            checkpoint_dir="/tmp",
            optimizer='adam',
            strict=False,
            pretrain_word_embed=True,
            typing=True,
            el=True,
            coherence=True,
            textcontext=True,
            WDLength=100,
            Fsize=5,
            entyping=False)

        model_var_dict = {}

        model_checkpoint_path = config['neural_el_model']
        saver = tf.compat.v1.train.Saver()
        saver.restore(sess, model_checkpoint_path)

        tf.compat.v1.get_default_graph().finalize()

    process_articles(filename2title,filenames, corefs, aliases_reverse, coref_assignments, reader, model)
