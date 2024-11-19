#!/bin/sh

echo "Start parser 3: Add new annotations."
python src/parser_3.py

echo "Start parser 4: Co-reference resolution and entity linking."
python src/parser_4_greedy.py

echo "Move important files and compress (if desired)."
# python src/dataset_creator.py
