---
description: Add a new filter option to the enrichment pipeline
---
1. Add filter function in `source_enrichment.py` (e.g., `is_early_stage()`)
2. Update `enrich_search_results()` to accept new parameter
3. Add UI control in `app.py` sidebar (radio/checkbox)
4. Pass parameter through call chain to enrichment
5. Update filter reason messages for blacklist
6. Test both filter values
