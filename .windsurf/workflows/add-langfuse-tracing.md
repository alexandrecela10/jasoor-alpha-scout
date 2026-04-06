---
description: Add Langfuse tracing to a new function or agent
---
1. Import from `tracing.py`:
```python
from tracing import create_trace, create_generation, log_scores
```

2. Create trace at function entry:
```python
trace = create_trace(
    name="function_name",
    input_data={"key": value},
    user_id=user_id,
    session_id=session_id
)
```

3. Wrap LLM calls with generation:
```python
generation = create_generation(name="llm_call", model=model, input_data=prompt)
# ... call LLM ...
generation.update(output=response)
generation.end()
```

4. Log batch metrics:
```python
log_scores(trace, {"metric_name": value})
```

5. Verify in Langfuse dashboard
