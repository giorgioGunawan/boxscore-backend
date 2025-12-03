// Database alteration script - May 12, 2025
// Adds display_name column to driver_standings table

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');

// Determine if we're running on Render with a persistent disk
const isRender = process.env.RENDER === 'true';
const renderDataDir = '/data'; // Render persistent disk mount point

// Choose the appropriate database path
let dbPath;
if (isRender && fs.existsSync(renderDataDir)) {
  dbPath = path.join(renderDataDir, 'f1races.db');
  console.log('Using Render persistent disk database at:', dbPath);
} else {
  dbPath = path.join(__dirname, '..', 'data', 'f1races.db');
  console.log('Using local database at:', dbPath);
}

// Connect to the database
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message);
    process.exit(1);
  }
  console.log('Connected to the F1 races database for alteration');
  
  // Execute each SQL statement separately
  db.serialize(() => {
    db.run(`ALTER TABLE races ADD COLUMN shortname VARCHAR(255);`, (err) => {
      if (err) {
        console.error('Error adding shortname column:', err.message);
      } else {
        console.log('Successfully added shortname column');
      }
    });
  });
  
  // Close the database connection
  db.close((err) => {
    if (err) {
      console.error('Error closing database:', err.message);
    } else {
      console.log('Database connection closed');
    }
  });
});

