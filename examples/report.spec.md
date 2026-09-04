# Process report

Each heading is one function. Numbered sentences become statements.

## load_rows

1. Open the file "data.csv" as handle
2. Read lines from handle as lines
3. Return lines

## filter_active

1. Set result to list
2. For each row in rows
   1. Split row by ","
   2. If status is "active"
      1. Append row to result
3. Return result

## write_out

1. Open the file "out.csv" as handle
2. For each row in rows
   1. Write row to handle
3. Return 0
