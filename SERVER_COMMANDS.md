# Among Us IRL - Server Commands Quick Reference

## 🚀 Start Server + Tunnel

### Option 1: Two Terminals (Recommended)

**Terminal 1 - Start Server:**
```bash
cd /Users/rosswilliams/Desktop/Among\ Us/among-us-pwa
source venv/bin/activate
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Start Tunnel:**
```bash
cloudflared tunnel run --token eyJhIjoiNWVmYzVhYTAzNmI1Y2QyZmY5YWJmMGY2YjI4MTYzNzgiLCJ0IjoiNWJiYmMzZjYtMGI1OC00YzM1LThmYjUtNDdmN2ZkOTc4MTM0IiwicyI6IllXSXdZbVpoWVRVdE9Ea3lNaTAwTmpreUxXRXhPVFV0TXpnM01qWTJORGt5TTJNNSJ9
```

### Option 2: Background (One Terminal)

```bash
cd /Users/rosswilliams/Desktop/Among\ Us/among-us-pwa
source venv/bin/activate
uvicorn server.main:app --host 0.0.0.0 --port 8000 &
cloudflared tunnel run --token eyJhIjoiNWVmYzVhYTAzNmI1Y2QyZmY5YWJmMGY2YjI4MTYzNzgiLCJ0IjoiNWJiYmMzZjYtMGI1OC00YzM1LThmYjUtNDdmN2ZkOTc4MTM0IiwicyI6IllXSXdZbVpoWVRVdE9Ea3lNaTAwTmpreUxXRXhPVFV0TXpnM01qWTJORGt5TTJNNSJ9
```

---

## 🔍 Check if Server is Running

### Check Server Status
```bash
lsof -i:8000
```
- **If output shown** = Server running ✅
- **If empty** = Server not running ❌

### Check Tunnel Status
```bash
ps aux | grep cloudflared
```
- **If processes shown** = Tunnel running ✅
- **If empty** = Tunnel not running ❌

### Test URL Directly
```bash
curl https://imposter.rossfw.com
```
- **If HTML returned** = Working ✅
- **If timeout/error** = Not working ❌

### Quick Browser Test
Just visit: **https://imposter.rossfw.com**

---

## 🛑 Stop Everything

### Kill Server
```bash
lsof -ti:8000 | xargs kill -9
```

### Kill Tunnel
```bash
pkill -f cloudflared
```

### Kill Both (Nuclear Option)
```bash
lsof -ti:8000 | xargs kill -9
pkill -f cloudflared
```

---

## 🧪 Run Tests

### Quick Test (Basic Flow)
```bash
cd /Users/rosswilliams/Desktop/Among\ Us/among-us-pwa
source venv/bin/activate
python test_game_flow.py
```

### Comprehensive Tests
```bash
# All test suites (~5 min)
python test_game_flow.py all

# Specific suites
python test_game_flow.py voting      # Voting scenarios
python test_game_flow.py abilities   # Role abilities
python test_game_flow.py sabotage    # Sabotage mechanics
python test_game_flow.py edge        # Edge cases
```

---

## 🎮 Share with Players

**Your Permanent Game URL:**
```
https://imposter.rossfw.com
```

No setup needed - just share this URL and you're good to go!

---

## 📝 Game Day Checklist

1. ✅ Open terminal
2. ✅ Start server + tunnel (use Option 1 or 2 above)
3. ✅ Verify it's running: `curl https://imposter.rossfw.com`
4. ✅ Share URL with players: `https://imposter.rossfw.com`
5. ✅ Players create/join games and play!
6. ✅ When done: Kill server + tunnel

---

## 🐛 Troubleshooting

**"Port 8000 already in use"**
```bash
lsof -ti:8000 | xargs kill -9
```

**"Tunnel not connecting"**
- Check if cloudflared is installed: `which cloudflared`
- Restart the tunnel (kill and restart)

**"URL not loading"**
- Check server is running: `lsof -i:8000`
- Check tunnel is running: `ps aux | grep cloudflared`
- Wait 30 seconds after starting (Cloudflare DNS propagation)

**"Game acting weird"**
- Restart server: kill it and start fresh
- Clear browser cache
- Check console for errors (F12 in browser)

---

## 💡 Tips

- **Keep both terminals visible** so you can see logs
- **Use `Ctrl+C`** to gracefully stop server/tunnel (preferred over kill)
- **Test locally first** before sharing with others: `http://localhost:8000`
- **One game at a time** - server handles multiple games but test with small groups first

---

## 📊 Server Logs

### View Live Server Logs
If running in background, check:
```bash
tail -f /private/tmp/claude-501/-Users-rosswilliams-Desktop-Among-Us/tasks/*.output
```

### Common Log Messages
- `Application startup complete` = Server ready ✅
- `Registered tunnel connection` = Tunnel connected ✅
- `WebSocket connected` = Player joined ✅

---

**Last Updated:** February 5, 2026
**Domain:** imposter.rossfw.com
**Server:** FastAPI (Python) on localhost:8000
**Tunnel:** Cloudflare (imposters-irl)
