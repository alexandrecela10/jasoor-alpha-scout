---
description: Review code for quality, security, and maintainability
---
1. **Readability** — Can someone understand this in 30 seconds?
   - Function names describe action (verb_noun)
   - Variables are descriptive, not abbreviated
   - No magic numbers — use constants

2. **Single Responsibility** — Does each function do ONE thing?
   - If >20 lines, consider splitting
   - If >3 parameters, consider a config object

3. **Error Handling** — What happens when things fail?
   - Catch specific exceptions, not bare `except:`
   - Log errors with context (what failed, why)
   - Return graceful fallbacks where possible

4. **Security** — Any risks?
   - No hardcoded secrets (use env vars)
   - Validate user inputs
   - Sanitize data before logging

5. **Performance** — Any obvious bottlenecks?
   - Avoid N+1 queries/API calls
   - Use batch operations where possible
   - Consider caching for repeated lookups

6. **Quick Check**:
// turbo
```bash
python3 -m py_compile <file.py> && echo "Syntax OK"
```
