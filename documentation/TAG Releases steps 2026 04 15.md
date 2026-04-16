## Here are the git tag steps for v3.0.0. Run these from the PhotoCatalog repo root (same folder that contains `scripts/` and `README.md`).

**1. Make sure everything is committed**

```
git status
```

If anything is modified or untracked that you want in the tag, stage and commit it first:

```
git add -A
git commit -m "v3.0.0: smart-hash optimization, Detect-Dupes-on-Workbook, UI refinements"
```

**2. Create an annotated tag**

Annotated (`-a`) is the right choice for releases — it stores your name, date, and a message, and `git describe` will find it:

```
git tag -a v3.0.0 -m "PhotoCatalog v3.0.0 - destination reorganization, smart-hash duplicate detection, in-bar progress, Detect-Dupes-on-Existing-Workbook"
```

**3. Verify**

```
git tag
git show v3.0.0
```

`git show v3.0.0` will print the tag message, the tagger info, and the commit it points to.

**4. Push the tag to the remote (if you have one)**

Pushing commits does *not* push tags by default — you have to do it explicitly:

```
git push origin v3.0.0
```

Or push all local tags at once:

```
git push origin --tags
```

**If you need to redo it**

If you tag and then realize you missed a commit, delete locally and on the remote before re-tagging:

```
git tag -d v3.0.0
git push origin :refs/tags/v3.0.0
```

Then re-run step 2.

Want me to run `git status` for you so we can see what's sitting uncommitted before you tag?