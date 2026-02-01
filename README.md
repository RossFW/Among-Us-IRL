# Among Us IRL

A Progressive Web App for playing Among Us in real life.

## Quick Start

### 1. Install dependencies

```bash
cd among-us-pwa
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run locally

```bash
python run.py
```

Open http://localhost:8000 in your browser.

### 3. Run with public URL (for phones)

```bash
# First, install Cloudflare tunnel:
brew install cloudflared

# Then run with tunnel:
python run.py --tunnel
```

This will give you a public URL like `https://xxxxx-yyyy.trycloudflare.com` that players can access on their phones.

## How to Play

1. **Create a game** - One person creates the game and gets a 4-letter code
2. **Share the code** - Other players enter their name and the code to join
3. **Configure** - The host sets the number of tasks, impostors, and special roles
4. **Start** - When everyone's ready, the host starts the game
5. **Play** - Players see their role and tasks on their phone:
   - **Crewmates**: Go complete your physical tasks and tap to check them off
   - **Impostors**: Pretend to do tasks, eliminate crewmates
   - **Special roles**: Follow your unique win condition
6. **Meetings** - Anyone can call a meeting. Discuss and vote in person!
7. **Win** - Crewmates win by completing all tasks. Impostors win by eliminating enough crewmates.

## Roles & Win Conditions

| Role | Win Condition |
|------|---------------|
| **Crewmate** | Complete all tasks OR vote out all impostors |
| **Impostor** | Eliminate crewmates until impostors >= crewmates |
| **Jester** | Get yourself voted out during a meeting |
| **Lone Wolf** | Be one of last 2 alive with no impostors remaining |
| **Minion** | Help impostors win (cannot kill, knows who impostors are) |

## Features

- **Multiple roles**: Crewmate, Impostor, Jester, Lone Wolf, Minion
- **Real-time updates**: Task progress syncs across all players
- **Reconnection**: If someone closes the app, they just reopen and rejoin
- **Mobile-first**: Designed for phones, installable as PWA
- **Meeting system**: Call meetings, see task progress, then vote in person
- **Custom tasks**: Add or remove physical tasks before the game
- **Rules modal**: In-app explanation of all roles and win conditions

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Vanilla JS, CSS
- **Real-time**: WebSockets
- **Hosting**: Self-hosted with Cloudflare Tunnel

## Project Structure

```
among-us-pwa/
├── server/
│   ├── main.py              # FastAPI app
│   ├── models.py            # Data models
│   ├── database.py          # In-memory game storage
│   ├── routes/              # API endpoints
│   └── services/            # Game logic, WebSocket manager
├── static/                  # CSS, JS, sounds, icons
├── requirements.txt
└── run.py                   # Startup script
```

## GitHub Pages (Stable URL)

The `docs/` folder contains a landing page for GitHub Pages. This gives you a stable URL to share with friends:

1. Push this repo to GitHub
2. Go to Settings → Pages → Deploy from `docs/` folder
3. Your URL will be: `yourusername.github.io/among-us-irl`

**Before each game session:**
1. Start your server: `python run.py --tunnel`
2. Copy the Cloudflare URL
3. Edit `docs/index.html` - update the URL in the link
4. Commit and push

Friends can always go to the same GitHub Pages URL to find the current game link!

## License

MIT
