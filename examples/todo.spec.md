# JSON todo list

Each heading is one function. Numbered sentences are statements.
Headings may include parameters: `add_todo(title)`.

The on-disk format is a JSON list of objects:
`[{"title": "buy milk", "done": false}, ...]`.

## load_todos

1. Open the file "todos.json" as handle
2. Load json from handle as todos
3. Return todos

## save_todos(todos)

1. Open the file "todos.json" as handle for writing
2. Dump json todos to handle
3. Return 0

## add_todo(title)

1. Set todos to load_todos
2. Append title to todos
3. Set ignored to save_todos todos
4. Return todos

## complete_todo(title)

1. Set todos to load_todos
2. For each item in todos
   1. If item is title
      1. Print "done"
3. Set ignored to save_todos todos
4. Return todos

## list_todos

1. Set todos to load_todos
2. For each item in todos
   1. Print item
3. Return todos

## remove_todo(title)

1. Set todos to load_todos
2. Set kept to list
3. For each item in todos
   1. Append item to kept
4. Set ignored to save_todos todos
5. Return kept
