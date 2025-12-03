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

// Create a new database or open existing
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message);
    process.exit(1);
  }
  console.log('Connected to the SQLite database.');
});

// Alter tables to add new columns
db.serialize(() => {
  // Alter driver_standings table to add driver_number column
  db.run(`ALTER TABLE driver_standings ADD COLUMN driver_number INTEGER`, (err) => {
    if (err) {
      // SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS
      // If error occurs, it might be because the column already exists
      console.log('Note: driver_number column might already exist or other error occurred:', err.message);
    } else {
      console.log('Added driver_number column to driver_standings table');
    }
  });

  // Alter constructor_standings table to add driver columns
  db.run(`ALTER TABLE constructor_standings ADD COLUMN driver_name_1 TEXT`, (err) => {
    if (err) {
      console.log('Note: driver_name_1 column might already exist or other error occurred:', err.message);
    } else {
      console.log('Added driver_name_1 column to constructor_standings table');
    }
  });

  db.run(`ALTER TABLE constructor_standings ADD COLUMN driver_name_2 TEXT`, (err) => {
    if (err) {
      console.log('Note: driver_name_2 column might already exist or other error occurred:', err.message);
    } else {
      console.log('Added driver_name_2 column to constructor_standings table');
    }
  });

  db.run(`ALTER TABLE constructor_standings ADD COLUMN driver_name_3 TEXT`, (err) => {
    if (err) {
      console.log('Note: driver_name_3 column might already exist or other error occurred:', err.message);
    } else {
      console.log('Added driver_name_3 column to constructor_standings table');
    }
  });

  console.log('Database schema update completed.');
});

// Close the database connection
db.close((err) => {
  if (err) {
    console.error('Error closing database:', err.message);
  } else {
    console.log('Database connection closed');
  }
});
