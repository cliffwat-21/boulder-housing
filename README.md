# Boulder Housing Watch

A small personal tool that checks rental listing sites once a day for studios and
1-bedrooms anywhere in Boulder within ~5 miles of the East Boulder office
(2000 Central Ave) under $1,750, and publishes the results to a webpage you can
bookmark. "Within 5 miles" is approximated by covering all of Boulder city and
applying a ZIP guardrail (80301-80305, 80503) — these sites don't expose a true
radius filter, but all of Boulder city happens to sit inside that radius anyway.

No notifications, no accounts beyond a free GitHub account, no cost.

---

## What you're setting up

1. A **GitHub repository** (free) to hold this code.
2. **GitHub Actions** runs the checker automatically once a day.
3. **GitHub Pages** publishes the results as a webpage you bookmark.

You don't need to know how to code. Just follow the steps below in order.

---

## One-time setup (about 15 minutes)

### Step 1 — Make a free GitHub account
Go to https://github.com and sign up if you don't already have an account.

### Step 2 — Create a new repository
1. Click the **+** in the top-right corner → **New repository**.
2. Name it something like `gunbarrel-housing`.
3. Set it to **Private** (only you can see it).
4. Do NOT check "Add a README" (we already have one).
5. Click **Create repository**.

### Step 3 — Upload these files
On your new empty repo page:
1. Click **uploading an existing file** (it's a link in the middle of the page).
2. Drag in ALL the files and folders from this project, keeping the structure:
   - `check_listings.py`
   - `README.md`
   - `.gitignore`
   - the `.github` folder (contains `workflows/check.yml`)
   - the `docs` folder (contains the starter `index.html`)
3. Click **Commit changes**.

> Tip: GitHub's web uploader can be finicky about folders. If dragging the
> `.github` folder doesn't work, see "Troubleshooting" at the bottom.

### Step 4 — Turn on GitHub Pages
1. In your repo, go to **Settings** → **Pages** (left sidebar).
2. Under "Build and deployment" → "Source", choose **Deploy from a branch**.
3. Branch: pick **main**, folder: pick **/docs**. Click **Save**.
4. After a minute, this section will show your live URL, something like:
   `https://YOURNAME.github.io/gunbarrel-housing/`
   **That's the page you bookmark.**

### Step 5 — Let the Action write to your repo
1. Go to **Settings** → **Actions** → **General** (left sidebar).
2. Scroll to "Workflow permissions".
3. Select **Read and write permissions**. Click **Save**.

### Step 6 — Run it once to test
1. Go to the **Actions** tab at the top of your repo.
2. If prompted to enable Actions, click the green button to enable them.
3. Click **Check Gunbarrel Listings** in the left list.
4. Click **Run workflow** → **Run workflow** (green button).
5. Wait ~1 minute, refresh. A green check means it worked.
6. Open your GitHub Pages URL from Step 4 — you should see results.

That's it. From now on it runs by itself once a day.

---

## Checking your listings
Just open your bookmarked GitHub Pages URL whenever you like. Listings marked
**NEW** appeared since the last run; listings marked **★** are at or under your
$1,500 ideal.

---

## Changing the search later
Open `check_listings.py` on GitHub (click the file, then the pencil icon to edit)
and change the values near the top:
- `MAX_RENT` — your hard ceiling
- `IDEAL_RENT` — the "star this" threshold
- `MAX_BEDS` — set to 2 if you want to include 2BRs
- `ALLOWED_ZIPS` — the ZIP guardrail for the ~5-mile zone. Add `"80027"` to
  include Louisville, or remove ZIPs to tighten the area.

Commit the change and the next run uses the new settings.

## Changing how often it runs
Edit `.github/workflows/check.yml`, the `cron:` line. It's in UTC.
`"0 14 * * *"` = once daily. For every 12 hours: `"0 */12 * * *"`.

---

## Important honesty notes
- **Some sites block bots.** Zillow and Apartments.com actively try to stop
  automated checks. When they block us, they show as "blocked" on the page and
  you should check those manually. Apartment List is the most reliable source.
- **This does NOT check Facebook Marketplace or Craigslist.** Those require a
  logged-in session and forbid automated access — keep using their own saved-search
  alerts for those.
- **Always verify listing details directly.** The checker only reads what's in the
  listing card; confirm in-unit W/D, parking, and outdoor space with the source.

---

## Troubleshooting
**The `.github` folder won't upload via drag-and-drop.**
Create it manually: on your repo page, click **Add file → Create new file**, then
in the name box type `.github/workflows/check.yml` (the slashes create the folders),
paste the contents of that file, and commit.

**The Action failed with a permissions error.**
Re-check Step 5 — "Read and write permissions" must be enabled.

**The page shows all sites "blocked."**
That can happen if the sites are blocking GitHub's servers. Apartment List is
usually the survivor. There's not much to be done about Zillow/Apartments.com
blocking — it's expected some of the time.
