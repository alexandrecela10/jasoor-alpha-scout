---
description: Add screenshots or media to README
---
1. Save files to `assets/` with URL-friendly names (no spaces):
```bash
mv "Screenshot 2026-04-05.png" assets/feature-name.png
```

2. Add image to README:
```markdown
![Alt text](assets/filename.png)
*Caption in italics*
```

3. For videos >50MB: Upload to YouTube, embed link

4. Add large files to `.gitignore`:
```bash
echo "assets/*.mov" >> .gitignore
```

5. If push fails, increase buffer:
// turbo
```bash
git config http.postBuffer 524288000
```
