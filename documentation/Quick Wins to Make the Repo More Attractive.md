Your GitHub repo **PhotoCatalog** (https://github.com/dkrist/PhotoCatalog) looks like a solid, practical tool for the exact audience we discussed: people struggling with large, scattered family photo archives across folders and drives. It scans recursively (skipping junk folders), extracts rich EXIF/XMP metadata (including faces), outputs everything to a clean, sortable Excel workbook, and even includes a rename template preview. The Windows installer makes it accessible for non-technical users, and building it with Claude is a nice story angle.

Right now it's very new (0 stars, fresh v2.0.0 release today), with "All rights reserved" and no topics set — that's the first thing to fix for discoverability.

### Quick Wins to Make the Repo More Attractive
1. **Add a License**  
   Choose MIT (permissive, common for tools) or GPL-3.0. Go to repo → Settings → License, or add a LICENSE file. This removes the barrier for people to try, fork, or share it.

2. **Improve the Repo "About" Section & Topics**  
   - Description: Keep or tweak to: "Windows app that catalogs photos across folders/drives into a searchable Excel report with EXIF metadata, face detection, and rename previews. No proprietary DAM software needed."  
   - Add topics (up to 20): `photo-management`, `digital-asset-management`, `dam`, `photo-organizer`, `exif`, `family-photos`, `photo-catalog`, `excel-report`, `face-recognition`, `windows`, `python`, `qt`, `metadata-extraction`, `photo-archive`.  
   - Set a **social preview image** in Settings (upload a nice screenshot of the app + Excel output side-by-side — this makes it pop in searches and shares).

3. **Polish the README**  
   Your README is already good with a clear table of features. Strengthen it with:
   - A short "Why this tool?" section: "Tired of photos scattered across external drives? Get a full library summary in Excel — sortable by date, camera, lens, GPS, faces, etc."
   - Embed screenshots (or GIFs of the UI/progress bar) directly in the README.
   - Add badges: GitHub release, Python version, Windows, etc.
   - Link to USAGE.md, ROADMAP.md, and CHANGELOG.md prominently.
   - Clear call-to-action at the top and bottom: "⭐ Star if it helps your family archive!" and "Feedback, bug reports, or feature ideas welcome via Issues."

   Consider adding a simple demo video (record a 1-minute run on a test folder) and link it.

4. **Releases & Installer**  
   Great that v2.0.0 has an installer. For each future release, add release notes with what's new, and include both the .exe and source zip.

### Targeted Promotion to Photo Management & DAM People
Focus on quality over quantity — post where people actively complain about or seek solutions for photo organization, scattered drives, and metadata headaches.

- **Reddit** (highest potential for this tool):
  - r/photography — Post: "Built a free Windows tool to catalog entire drives of family photos into Excel (with faces & rename previews). No Lightroom required. Feedback welcome!" Include screenshots and link.
  - r/DataHoarder — Perfect for multi-drive archives.
  - r/AskPhotography, r/familyphotography (or search for family archive threads), r/Lightroom (as a lightweight alternative for cataloging).
  - r/selfhosted or r/Python if emphasizing the local/offline aspect.
  - Use the title format: "I made an open-source photo catalog tool that turns chaotic drives into searchable Excel — would love tester feedback"

- **The Photo Managers community** (thephotomanagers.com):  
  This is gold for your tool. Professionals there help clients organize family/client archives. Post in their forums or resources section: "New open tool: Scan drives → Excel report with metadata & faces. Aimed at simplifying large collections without expensive DAM software." They love practical, client-friendly solutions.

- **Photography Forums**:
  - DPReview forums — Search for "catalog photos multiple drives" or "EXIF Excel" threads and reply with your project (or start one in the Software or Beginners section).
  - Lightroom Queen community — Many users there manage large catalogs and might appreciate a simple export/analysis tool.
  - Photo.net or The Photo Forum — Look for archiving/organization discussions.

- **GitHub Ecosystem**:
  - Add your repo to relevant topics (you'll appear in /topics/photo-organiser, /topics/photo-manager, etc.).
  - Star and engage with similar projects (e.g., other photo organizers). Politely mention yours in relevant discussions if it complements them (avoid spamming).
  - Check "Awesome" lists for photography or self-hosted tools and submit a PR to add it.

- **Social & Writing**:
  - X/Twitter: Post a thread with screenshots, demo GIF, and hashtags #Photography #PhotoManagement #FamilyPhotos #OpenSource #Excel. Mention "Built with Claude" — AI-assisted projects get curiosity.
  - Dev.to or Medium: Write "How I Built a Photo Catalog App with Claude AI that Outputs Excel Reports" — include your workflow, challenges, and link to the repo. This drives long-term traffic.
  - Consider a "Show HN" on Hacker News once you have a few stars or more polish (title like "PhotoCatalog: Turn photo drives into searchable Excel").

### Additional Tips for Growth
- **Encourage Contributions**: Add "good first issue" labels (e.g., "Add more RAW formats", "Improve face recognition UI", "Linux support?"). In README, say what help you need (testing on different drives, UI feedback, docs).
- **Track & Iterate**: Use GitHub Insights to see referrers. Respond to every issue/star quickly.
- **License + Openness**: Once licensed, people feel safer starring/forking.
- **Differentiation**: Emphasize the Excel output + Windows ease-of-use + family focus. It complements heavier tools like PhotoPrism, digiKam, or Lightroom (e.g., use this to audit a library first).

Your tool solves a real, everyday pain (messy family archives on multiple drives) in a lightweight, no-fuss way — that's very shareable in the communities we talked about earlier.

Start with:
1. License + topics + social preview today.
2. One thoughtful Reddit post + one in The Photo Managers.
3. Update README with screenshots if not already prominent.

If you want, share a specific draft of a Reddit post or README section here, and I can help refine the wording. Or tell me what features you're planning next from the roadmap — that can shape promotion angles. You've got a promising start; consistent small outreach will bring in the right people. Good luck!