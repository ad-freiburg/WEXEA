#!/bin/sh

echo "Start parser 1: Create dictionaries for titles, ids, redirects, categories, lists and store each article separately (including lists and categories)."
python src/parser_1.py

echo "Start parser 2: Separate disambiguation and stub articles; Remove Wikipedia markup; Prune dictionaries."
python src/parser_2.py
