# WEXEA

WEXEA is an exhaustive Wikipedia entity annotation system, to create a text corpus based on Wikipedia with exhaustive annotations of entity mentions, i.e. linking all mentions of entities to their corresponding articles.

This is a modified version of the [original code](https://github.com/mjstrobl/WEXEA) with which WEXEA's linking results can be easily evaluated using [ELEVANT](https://github.com/ad-freiburg/elevant).

WEXEA runs through several stages of article annotation and the final articles can be found in the 'final_articles' folder in the output directory.
Articles are separately stored in a folder named after the first 3 letters of the title (lowercase) and sentences are split up leading to one sentence per line.
Annotations follow the Wikipedia conventions, just the type of the annotation is added at the end.

**Note:** For the paper introducing WEXEA, Neural EL by Gupta et al. was used to disambiguate certain mentions.
The code for this is not functional anymore and not included in this version of the code, but the authors provide a 
greedy method based on prior probabilities to disambiguate these mentions. This has however only a minor impact on the
linking results, as Neural EL was only used for a small subset of mentions.

## Start CoreNLP toolkit

Download (including models for languages other than English) CoreNLP from https://stanfordnlp.github.io/CoreNLP/index.html

Start server:
```
cd <path to stanford-corenlp-x.x.x>
java -mx16g  -cp "*" edu.stanford.nlp.pipeline.StanfordCoreNLPServer -port 9000 -timeout 15000 -threads 6
```

## Run WEXEA

1. If you want to link text in a language other than English, change language specific keyword variables in `src/language_variables.py`.
2. Install requirements from requirements.txt .
3. In `config/config.json`, provide path of latest wiki dump (xml file), output path (make sure the output folder does 
   not exist yet, it will be created) and the absolute path to the sutime directory within this repository.
4. Make `create_mappings.sh` executable: `chmod 755 create_mappings.sh`
5. Extract the necessary mappings from the Wikipedia dump by running `./create_mappings.sh`
6. If you want to link the entire Wikipedia dump using WEXEA, make `annotate.sh` executable using `chmod 755 annotate.sh` 
   and run `./annotate.sh` (this will take a couple of days). If you want to link a specific benchmark, follow the 
   steps in the next section

## ELEVANT evaluation
Set up [ELEVANT](https://github.com/ad-freiburg/elevant) following the instructions [here](https://github.com/ad-freiburg/elevant/wiki/A-Quick-Start).

To get benchmark articles into WEXEA's expected input format and location use ELEVANT's `write_articles.py` with the 
following options:
        
    python3 scripts/write_articles.py --output_dir <path> --title_in_filename --print_hyperlinks -b <benchmark_name>

Run WEXEA's parser_3.py over the benchmark articles:
   
    python3 src/parser_3.py --input_dir <path> --wiki_id_to_title <elevant_data_path>/wikipedia_mappings/wikipedia_id_to_title.tsv

Run WEXEA's parser_4_greedy.py over the output from the previous script to get the final annotations:
   
    python3 src/parser_4_greedy.py --input_dir <path>_parsed_3

To add the linking results to ELEVANT, run in your ELEVANT directory

    python3 link_benchmark.py "WEXEA" -pfile <path>_parsed_4 -pformat wexea -pname wexea -b <benchmark_name>

Evaluate the linking results with

    python3 evaluate.py evaluation-results/wexea/wexea.<benchmark_name>.linked_articles.jsonl


## Hardware requirements

32GB of RAM are required (it may work with 16, but not tested) and it should take around 2-3d to finish with a full English Wikipedia dump (less for other languages).

## Parsers

Time consumption was measured when running on a Ryzen 7 2700X with 64GB of memory. Data was read from and written to a hard drive. Runtimes lower for languages other than English.

### Parser 1 (~2h 45 min / ~4.6GB memory in total / 20,993,369 articles currently):
Create all necessary dictionaries.

### Parser 2 (~1h 45 mins with 6 processes / ~6,000,000 articles to process)
Removes most Wiki markup, irrelevant articles (e.g. lists or stubs), extracts aliases and separates disambiguation pages.

A number of processes can be set to speed up the parsing process of all articles. However, each process consumes around 7.5GB of memory.

### Parser 3 (~2 days with 6 processes / ~2,700,000 articles to process)

Run CoreNLP NER and find other entities based on alias/redirect dictionaries.

### Parser 4 (~2h / ~2,700,000 articles to process)

Run co-reference resolution and EL.

## Citation

Please cite the following papers:

Original WEXEA publication:

Strobl, Michael, Amine Trabelsi, and Osmar R. Zaïane. "WEXEA: Wikipedia exhaustive entity annotation." Proceedings of the Twelfth Language Resources and Evaluation Conference. 2020.

Updated version (from which the linked datasets above are derived):

Strobl, Michael, Amine Trabelsi, and Osmar R. Zaiane. "Enhanced Entity Annotations for Multilingual Corpora." Proceedings of the Thirteenth Language Resources and Evaluation Conference. 2022.

ELEVANT:

Hannah Bast, Matthias Hertel, Natalie Prange. "ELEVANT: A Fully Automatic Fine-Grained Entity Linking Evaluation and Analysis Tool". EMNLP (Demos) 2022