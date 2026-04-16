Good morning. That's a meaningful jump — going from "rename in place" to "consolidate and restructure a drive" is a real scope change, and I agree it deserves a major version (v3.0.0 feels right). Let me think through it with you before we lock anything in.

**The core shift**

v2.1.x has been: *one folder → scan → rename files where they sit*.

v3 becomes: *messy source (possibly nested, possibly multiple drives) → restructured destination with a folder hierarchy you define → files moved into it*. That means the rename template grows a sibling — a **folder template** — and the whole pipeline needs a destination root that isn't the source.

**Design questions I'd want to settle before coding**

*Folder template vs. combined path template.* Two reasonable shapes:

- Separate: one field for folder path `%Date_YYYY%\%Date_MM% - %Date_Month%\` and another for filename `%Date_YYYYMMDD%_%File_Name%.%File_Extension%`. Cleaner mental model, easier to validate each piece.
- Combined: a single template where `\` or `/` is meaningful. More flexible but harder to preflight and easier to mess up.

I'd lean toward **separate templates** given how much mileage we got from the viability checker — two smaller, well-validated surfaces beat one big one.

*Move vs. copy vs. stage.* Moving is irreversible in the user's head even if we keep a rollback log. I'd propose three modes: **Preview** (workbook only, nothing touched), **Copy** (safe, doubles disk usage), **Move** (fast, needs strong confirmation + log). Default to Copy.

*Destination root.* A required field. We should block if destination is inside source (recursive scan eats its own tail) or if the drive can't hold the copy.

*Collision handling gets harder.* Today collisions are scoped per-parent-folder because the parent is fixed. When you're consolidating `C:\Messy\2019\IMG_0001.jpg` and `C:\Messy\Phone backup\IMG_0001.jpg` into the same `2019\06 - June\` bucket, they collide. Options: auto-suffix (`_2`, `_3`), include a hash/sequence token in the template, or flag as `[ERROR]` and refuse. I'd make the behavior explicit in the template ("guarantee uniqueness with `%File_Seq%`" as a warning like we did for `%File_Name%`).

*Duplicate detection.* Strongly related. Are two files with the same `File_Name` + `File_SizeBytes` + `DateTimeOriginal` actually the same photo? If yes, do we merge (keep one), or keep both with suffix? This is where a hash column (new in v3?) might earn its keep.

*Sidecars and pairs.* RAW+JPG pairs (`IMG_0001.NEF` + `IMG_0001.JPG`), `.xmp` sidecars, Lightroom previews. If the logic moves one but not the other, you've quietly broken an edit history. v3 should probably detect and move stem-mates together.

*Source cleanup.* After a successful move, do we leave empty folders, prune them, or leave everything and let the user clean up? I'd vote leave-alone by default, with an optional "Remove empty source folders" checkbox.

*Rollback.* A CSV/JSON journal per run: `old_path, new_path, operation, timestamp`. "Undo last move run" button. This is the kind of feature that turns a scary operation into an acceptable one.

*The workbook's role.* Does the existing `.xlsx` drive the moves (reads File_RenameName + new File_DestPath columns), or is the workbook a byproduct? I'd keep it driving — same pattern as v2.1 rename. Adds columns: `File_DestFolder`, `File_DestPath`, `File_MoveStatus`.

*Backward compatibility.* If folder template is empty, behave exactly like v2.1.1 (rename in place). That lets v2.1.x workflows keep working without forcing the move model on anyone.

**What I'd love to hear from you**

Which of these resonate, which are over-engineered, and what have I missed? Particularly:

1. Is **Copy as the default** acceptable to you, or does "it's always been move" feel right?
2. How do you think about **duplicates** — merge silently, merge with log, always keep both?
3. Should v3 introduce a **hash column** (MD5/SHA1) as part of extract, so duplicate detection becomes trivial? It's a non-trivial scan-time cost on big drives.
4. Do you have a **folder layout in mind** already? Something like `YYYY\MM - Month Name\` or deeper/shallower? That'll shape which new tokens we need.
5. Anything about the **source side** — multiple source roots in one run? Recursive by default? Filter by extension?

Happy to keep this at design level until we've talked through the shape. No code yet.