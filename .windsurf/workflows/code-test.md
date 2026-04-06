---
description: Test code changes before committing
---
1. **Syntax Check** — Does it compile?
// turbo
```bash
python3 -m py_compile <file.py>
```

2. **Import Check** — Do all imports resolve?
// turbo
```bash
python3 -c "import <module>"
```

3. **Smoke Test** — Does the main function run?
```bash
python3 -c "from <module> import <function>; <function>(<test_args>)"
```

4. **Edge Cases** — Test boundaries:
   - Empty input
   - None/null values
   - Very large input
   - Invalid types

5. **Integration** — Does it work with the app?
```bash
streamlit run app.py
# Test the specific feature manually
```

6. **Regression** — Did we break anything else?
// turbo
```bash
python3 -m py_compile *.py && echo "All files OK"
```
