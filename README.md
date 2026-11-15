# Web Reader

A free personal reader app for sites without RSS — currently following the kipi.ai blog. A GitHub job checks the blog once a day,
and the app installs on your iPhone's Home Screen.

## One-time setup (about 15 minutes)

### 1. Create the repository
1. On github.com, click **+ → New repository**.
2. Name it `web-reader`, choose **Public** or **Private** (see "Public or private?" below), and click **Create repository**.

### 2. Upload the files
1. On the new repo page, click **uploading an existing file**.
2. Unzip `web-reader.zip` on your computer, and drag everything inside the `web-reader` folder
   (index.html, app.js, styles.css, sw.js, manifest.webmanifest, README.md, and the
   `data`, `icons`, `scripts` folders) into the upload box. Click **Commit changes**.
3. The `.github` folder is hidden on Mac/Windows and often gets skipped, so add it by hand:
   **Add file → Create new file**, type the name
   `.github/workflows/update-posts.yml`
   (typing the `/` creates the folders), paste the contents of that file from the zip,
   and click **Commit changes**.

### 3. Allow the daily job to save data
**Settings → Actions → General → Workflow permissions →** choose **Read and write permissions → Save**.

### 4. Turn on the website
**Settings → Pages → Build and deployment → Source: Deploy from a branch →
Branch: `main`, folder `/ (root)` → Save.**
After a minute or two your app is live at
`https://<your-github-username>.github.io/web-reader/`

### 5. Load the posts the first time
**Actions tab → Update posts → Run workflow.** The first run takes a few minutes
because it collects all past posts. After that it runs automatically every morning
(about 6:47 am IST).

### 6. Install on your iPhone
Open the app link in **Safari → Share → Add to Home Screen → Add.**

## Public or private?
- **Public (simplest):** GitHub Pages is free for public repos. Nothing personal is in the repo —
  only post titles, short descriptions and links. Your read/saved lists live on your phone.
- **Private:** free GitHub accounts can't serve Pages from a private repo. Instead, skip step 4 and use
  **Cloudflare Pages** (free): sign up at pages.cloudflare.com → Create → Connect to Git → pick
  `web-reader` → Framework preset **None**, build command empty, output directory `/` → Deploy.
  Every daily commit redeploys automatically. Your app link becomes `https://web-reader-xxx.pages.dev`.
  The daily GitHub job still works on a private repo (it uses about 2 of the 2,000 free minutes a month).

## Using it
- **Chips:** All / Unread / Saved / each blog category, with counts.
- **Tap a post** to open the article on kipi.ai; it's marked read automatically.
- **☆** saves a post for later. **Mark all read** clears the current list.
- **New** marks posts that arrived since your last visit.
- Read and saved lists are stored on your phone only.

## Optional: Telegram alert for new posts
1. In Telegram, message **@BotFather → /newbot**, and copy the **bot token**.
2. Send any message to your new bot, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the `chat` → `id` number.
3. In the repo: **Settings → Secrets and variables → Actions → New repository secret**:
   `TELEGRAM_BOT_TOKEN` = token, `TELEGRAM_CHAT_ID` = id.
From the next run, you'll get a message whenever new posts appear.

## If something breaks
- **Actions run fails with "No posts found":** the blog's layout probably changed.
  The scraper leaves your data untouched; the fix is usually in the URL patterns
  at the top of `scripts/fetch_posts.py`.
- **App doesn't show updates:** close and reopen it; it refreshes whenever it comes to the foreground.

This is a personal reader: it fetches politely once a day, stores only titles and short
descriptions, and always links to the original articles on kipi.ai.
