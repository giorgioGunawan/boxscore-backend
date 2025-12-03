const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const path = require('path');

// Determine if we're running on Render with a persistent disk
const isRender = process.env.RENDER === 'true';
const renderDataDir = '/data'; // Render persistent disk mount point

// Choose the appropriate data directory
let dataDir;
let dbPath;

if (isRender && fs.existsSync(renderDataDir)) {
  console.log('Running on Render with persistent disk at /data');
  dataDir = renderDataDir;
  dbPath = path.join(dataDir, 'f1races.db');
} else {
  console.log('Running in local development mode');
  dataDir = path.join(__dirname, 'data');
  dbPath = path.join(dataDir, 'f1races.db');
}

console.log(`Using database path: ${dbPath}`);

// Ensure data directory exists
if (!fs.existsSync(dataDir)) {
  console.log(`Creating data directory: ${dataDir}`);
  fs.mkdirSync(dataDir, { recursive: true });
}

// Check if database exists at the target location
const dbExists = fs.existsSync(dbPath);

// If we're on Render and the DB doesn't exist in /data, try to copy from local repo
if (isRender && !dbExists && fs.existsSync(renderDataDir)) {
  const localDbPath = path.join(__dirname, 'data', 'f1races.db');
  if (fs.existsSync(localDbPath)) {
    console.log(`Copying database from ${localDbPath} to ${dbPath}`);
    fs.copyFileSync(localDbPath, dbPath);
    console.log('Database copied successfully');
  }
}

// Create a new database or open existing
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message);
    console.error('Current directory:', __dirname);
    console.error('Data directory:', dataDir);
    console.error('Directory contents:', fs.readdirSync(__dirname));
    if (fs.existsSync(dataDir)) {
      console.error('Data directory contents:', fs.readdirSync(dataDir));
    }
    process.exit(1);
  }
  console.log('Connected to the SQLite database.');
});

// Create tables if they don't exist
db.serialize(() => {
  // Races table
  db.run(`CREATE TABLE IF NOT EXISTS races (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round INTEGER,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    datetime_fp1 INTEGER,
    datetime_fp2 INTEGER,
    datetime_fp3 INTEGER,
    datetime_sprint INTEGER,
    datetime_qualifying INTEGER,
    datetime_race INTEGER NOT NULL,
    first_place TEXT,
    second_place TEXT,
    third_place TEXT
  )`, (err) => {
    if (err) console.error('Error creating races table:', err.message);
    else console.log('Races table ready');
  });

  // Results table
  db.run(`CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL,
    session_type TEXT NOT NULL,
    position INTEGER NOT NULL,
    driver_name TEXT NOT NULL,
    team_name TEXT NOT NULL,
    time TEXT,
    laps INTEGER,
    points REAL,
    FOREIGN KEY (race_id) REFERENCES races (id)
  )`, (err) => {
    if (err) console.error('Error creating results table:', err.message);
    else console.log('Results table ready');
  });

  // Driver standings table
  db.run(`CREATE TABLE IF NOT EXISTS driver_standings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_name TEXT NOT NULL,
    team_name TEXT NOT NULL,
    points REAL NOT NULL
  )`, (err) => {
    if (err) console.error('Error creating driver_standings table:', err.message);
    else console.log('Driver standings table ready');
  });

  // Constructor standings table
  db.run(`CREATE TABLE IF NOT EXISTS constructor_standings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    constructor_name TEXT NOT NULL,
    points REAL NOT NULL
  )`, (err) => {
    if (err) console.error('Error creating constructor_standings table:', err.message);
    else console.log('Constructor standings table ready');
  });

  // Live race table
  db.run(`CREATE TABLE IF NOT EXISTS live_race (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_name TEXT NOT NULL,
    team_name TEXT NOT NULL,
    car_number INTEGER NOT NULL,
    position INTEGER NOT NULL,
    time_behind TEXT,
    current_lap INTEGER,
    is_dnf INTEGER DEFAULT 0
  )`, (err) => {
    if (err) console.error('Error creating live_race table:', err.message);
    else console.log('Live race table ready');
  });

  console.log('All tables created successfully.');
});

// Close the database connection
db.close((err) => {
  if (err) {
    console.error('Error closing database:', err.message);
  } else {
    console.log('Database connection closed');
  }
}); 