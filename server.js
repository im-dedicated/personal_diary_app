const express = require('express');
const session = require('express-session');
const bcrypt = require('bcryptjs');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_DIR = path.join(__dirname, 'data');
const USERS_FILE = path.join(DATA_DIR, 'users.json');
const ENTRIES_FILE = path.join(DATA_DIR, 'entries.json');

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({
  secret: 'diary-secret-key',
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false }
}));

function ensureDataFiles() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(USERS_FILE)) fs.writeFileSync(USERS_FILE, JSON.stringify([], null, 2));
  if (!fs.existsSync(ENTRIES_FILE)) fs.writeFileSync(ENTRIES_FILE, JSON.stringify([], null, 2));
}

function readJson(filePath) {
  ensureDataFiles();
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
}

function requireAuth(req, res, next) {
  if (!req.session.userId) {
    return res.status(401).json({ error: 'Please log in first' });
  }
  next();
}

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }

  const users = readJson(USERS_FILE);
  const existing = users.find((u) => u.username === username);
  if (existing) {
    return res.status(409).json({ error: 'Username already exists' });
  }

  const hashedPassword = await bcrypt.hash(password, 10);
  users.push({ id: Date.now().toString(), username, password: hashedPassword });
  writeJson(USERS_FILE, users);
  res.status(201).json({ message: 'User registered successfully' });
});

app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  const users = readJson(USERS_FILE);
  const user = users.find((u) => u.username === username);
  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const valid = await bcrypt.compare(password, user.password);
  if (!valid) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  req.session.userId = user.id;
  req.session.username = user.username;
  res.json({ message: 'Login successful', username: user.username });
});

app.post('/api/logout', (req, res) => {
  req.session.destroy(() => {
    res.json({ message: 'Logout successful' });
  });
});

app.get('/api/entries', requireAuth, (req, res) => {
  const entries = readJson(ENTRIES_FILE).filter((entry) => entry.userId === req.session.userId);
  res.json(entries);
});

app.post('/api/entries', requireAuth, (req, res) => {
  const { title, content } = req.body;
  if (!title || !content) {
    return res.status(400).json({ error: 'Title and content are required' });
  }

  const entries = readJson(ENTRIES_FILE);
  const newEntry = {
    id: Date.now().toString(),
    userId: req.session.userId,
    title,
    content,
    createdAt: new Date().toISOString()
  };
  entries.push(newEntry);
  writeJson(ENTRIES_FILE, entries);
  res.status(201).json(newEntry);
});

app.put('/api/entries/:id', requireAuth, (req, res) => {
  const { title, content } = req.body;
  const entries = readJson(ENTRIES_FILE);
  const index = entries.findIndex((entry) => entry.id === req.params.id && entry.userId === req.session.userId);
  if (index === -1) {
    return res.status(404).json({ error: 'Entry not found' });
  }

  entries[index] = { ...entries[index], title, content, updatedAt: new Date().toISOString() };
  writeJson(ENTRIES_FILE, entries);
  res.json(entries[index]);
});

app.delete('/api/entries/:id', requireAuth, (req, res) => {
  const entries = readJson(ENTRIES_FILE);
  const filtered = entries.filter((entry) => !(entry.id === req.params.id && entry.userId === req.session.userId));
  if (filtered.length === entries.length) {
    return res.status(404).json({ error: 'Entry not found' });
  }

  writeJson(ENTRIES_FILE, filtered);
  res.json({ message: 'Entry deleted successfully' });
});

app.get('/api/session', (req, res) => {
  if (!req.session.userId) {
    return res.json({ loggedIn: false });
  }
  res.json({ loggedIn: true, username: req.session.username });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});

module.exports = { app, readJson, writeJson, ensureDataFiles };
