# GitHub Pages Landing Page

This folder contains the GitHub Pages landing page for Among Us IRL.

## 🌐 Public URL

Once GitHub Pages is enabled, your landing page will be available at:
**https://rossfw.github.io/Among-Us-IRL/**

Share this URL with players - it never changes!

---

## 📝 Setup (One-Time)

### Enable GitHub Pages

1. Go to your GitHub repo: https://github.com/RossFW/Among-Us-IRL
2. Click **Settings** (top right)
3. Scroll down to **Pages** (left sidebar)
4. Under **Source**, select:
   - Branch: `main`
   - Folder: `/docs`
5. Click **Save**
6. Wait 1-2 minutes, then visit https://rossfw.github.io/Among-Us-IRL/

✅ Done! Your landing page is now live.

---

## 🎮 Using the Landing Page (Before Each Game)

### Step 1: Start Your Server
```bash
cd among-us-pwa
python run.py --tunnel
```

Copy the Cloudflare URL from the output (e.g., `https://xxxx-yyyy.trycloudflare.com`)

### Step 2: Update the Landing Page
Edit `docs/index.html`:

1. **Uncomment** the "Join Game" button (lines ~124-127)
2. **Paste your Cloudflare URL** in the `href`
3. **Comment out** the "No active game" message (line ~130)
4. **Optional:** Uncomment and update the "Last updated" date in the footer

Example:
```html
<!-- WHEN GAME IS ACTIVE: Uncomment this and update the URL -->
<a href="https://your-actual-url.trycloudflare.com" class="join-btn">
    Join Game
</a>

<!-- WHEN NO GAME: Comment this out -->
<!-- <p class="no-game">No active game right now.<br>Check back when the host starts a session!</p> -->
```

### Step 3: Commit and Push
```bash
git add docs/index.html
git commit -m "Update game URL for session"
git push
```

### Step 4: Share the Link
Give players: **https://rossfw.github.io/Among-Us-IRL/**

GitHub Pages updates in ~30 seconds after pushing.

---

## 🛑 After the Game

Reverse the changes to show "No active game":

1. **Comment out** the "Join Game" button
2. **Uncomment** the "No active game" message
3. Commit and push

```bash
git add docs/index.html
git commit -m "Game session ended"
git push
```

---

## 🎯 Why Use This?

- **Consistent URL:** Share the same GitHub Pages URL every time
- **No confusion:** Players don't need to remember new Cloudflare URLs
- **Clean UX:** Landing page looks professional and provides instructions
- **Easy updates:** Just edit one file and push

---

## 📋 Quick Reference

| Action | Command |
|--------|---------|
| Start server + tunnel | `python run.py --tunnel` |
| Edit landing page | `vim docs/index.html` (or any editor) |
| Commit change | `git add docs/index.html && git commit -m "Update URL" && git push` |
| View live page | https://rossfw.github.io/Among-Us-IRL/ |

---

## 🔧 Customization

Feel free to customize `index.html`:
- Change colors (see CSS variables)
- Update instructions
- Add game rules or announcements
- Add a game schedule

Just edit, commit, and push!
