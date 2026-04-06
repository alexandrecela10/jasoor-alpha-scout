---
description: Optimize Gemini prompts for better extraction quality
---
1. **Grounding instruction** — Already in `GROUNDING_INSTRUCTION` constant:
   - Cite sources for every claim
   - Return "N/A" if not found
   - Never invent data

2. **Specify exact JSON schema** with field descriptions:
```
"name": "Company Name (MUST appear in source)"
"source_snippet": "EXACT quote (max 100 chars)"
```

3. **Add length limits** to verbose fields to prevent truncation

4. **Remove fields** retrievable later in pipeline (e.g., founders)

5. **Test edge cases**:
   - Empty results
   - Truncated responses
   - Non-English content

6. **Monitor quality** via Langfuse `llm_judge_score`
