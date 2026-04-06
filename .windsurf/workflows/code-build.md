---
description: Build code with minimal lines, clear docs, auto-compile verification
---
1. Write minimal code — prefer single-purpose functions
2. Add docstring explaining what/why (not how)
3. Verify syntax immediately:
// turbo
```bash
python3 -m py_compile <file.py>
```
4. If function is complex, add inline comment for non-obvious logic
5. Run full test after changes:
// turbo
```bash
python3 -c "from <module> import <function>; print('OK')"
```
