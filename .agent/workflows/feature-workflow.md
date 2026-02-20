---
description: how to develop and ship a new feature branch
---

# Feature Development Workflow

// turbo-all

## Current Goal

Port and merge features that were hastily added to `D:\Ace-Step-Latest\ACE-Step-1.5-for-windows-custombuild` into `D:\Ace-Step-Latest\ACE-Step-1.5-for-windows` **one by one**, each on its own feature branch. Each feature branch is pushed to GitHub and merged into the main branch (`qinglong`).

- **Source (messy):** `ACE-Step-1.5-for-windows-custombuild` — contains working but unstructured features
- **Target (clean):** `ACE-Step-1.5-for-windows` — each feature gets a clean branch, review, and merge

## Setup

The repo is at `D:\Ace-Step-Latest\ACE-Step-1.5-for-windows`.

- **origin** → `sdbds/ACE-Step-1.5-for-windows` (upstream qinglong fork)
- **myfork** → `scragnog/ACE-Step-1.5-for-windows` (our fork)
- **Default branch:** `qinglong`

## Steps

1. Make sure you're on the latest `qinglong` branch:
```
cd D:\Ace-Step-Latest\ACE-Step-1.5-for-windows
git checkout qinglong
git pull myfork qinglong
```

2. Create a new feature branch:
```
git checkout -b feature/<feature-name>
```

3. Develop the feature — make commits as you go.

4. Push the feature branch to the fork:
```
git push --no-recurse-submodules myfork feature/<feature-name>
```
   - If the `ace-step-ui` submodule was modified, push it separately first:
```
cd ace-step-ui
git push myfork qinglong
cd ..
```

5. **WAIT for user to test locally before merging.** Do NOT merge until they confirm it works.

6. Merge the feature into `qinglong`:
```
git checkout qinglong
git merge feature/<feature-name> --no-edit
git push myfork qinglong
```

6. Update `FEATURES.md` in the repo root with the new feature details. Use the commented template at the bottom of the file.

7. Commit and push the `FEATURES.md` update:
```
git add FEATURES.md
git commit -m "docs: add <feature-name> to FEATURES.md"
git push myfork qinglong
```
