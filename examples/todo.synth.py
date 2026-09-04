"""Synthesized from markdown spec. Search-based, no LLM."""
from __future__ import annotations

import csv
import json
import math
import os
import random
import re
from datetime import datetime
from pathlib import Path

def load_todos():
    """load_todos."""
    # 1. Open the file "todos.json" as handle
    handle = open('todos.json')
    # 2. Load json from handle as todos
    todos = json.load(handle)
    # 3. Return todos
    return todos

def save_todos(todos):
    """save_todos(todos)."""
    # 1. Open the file "todos.json" as handle for writing
    handle = open('todos.json', 'w')
    # 2. Dump json todos to handle
    json.dump(todos, handle)
    # 3. Return 0
    return 0

def add_todo(title):
    """add_todo(title)."""
    # 1. Set todos to load_todos
    todos = load_todos()
    # 2. Append title to todos
    todos.append(title)
    # 3. Set ignored to save_todos todos
    ignored = save_todos(todos)
    # 4. Return todos
    return todos

def complete_todo(title):
    """complete_todo(title)."""
    # 1. Set todos to load_todos
    todos = load_todos()
    # 2. For each item in todos
    for item in todos:
        # 1. If item is title
        if item == title:
            # 1. Print "done"
            print('done')
    # 3. Set ignored to save_todos todos
    ignored = save_todos(todos)
    # 4. Return todos
    return todos

def list_todos():
    """list_todos."""
    # 1. Set todos to load_todos
    todos = load_todos()
    # 2. For each item in todos
    for item in todos:
        # 1. Print item
        print(item)
    # 3. Return todos
    return todos

def remove_todo(title):
    """remove_todo(title)."""
    # 1. Set todos to load_todos
    todos = load_todos()
    # 2. Set kept to list
    kept = []
    # 3. For each item in todos
    for item in todos:
        # 1. Append item to kept
        kept.append(item)
    # 4. Set ignored to save_todos todos
    ignored = save_todos(todos)
    # 5. Return kept
    return kept


if __name__ == "__main__":
    load_todos()
