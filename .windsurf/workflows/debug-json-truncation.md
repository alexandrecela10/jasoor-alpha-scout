---
description: Debug and fix JSON parsing errors from LLM responses
---
1. Check error log for truncation (incomplete JSON, missing `]` or `}`)
2. Verify `max_output_tokens` in `llm_client.py` (currently 16384)
3. If still truncating, simplify extraction schema — remove non-essential fields
4. Ensure `parse_json_response()` fallback strategies work (repair, regex)
5. Test with smaller batch if needed
