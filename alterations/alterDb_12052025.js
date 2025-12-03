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
    db.run(`ALTER TABLE constructor_standings DROP COLUMN driver_name_1`, (err) => {
      if (err) {
        console.error('Error dropping driver_name_3 column:', err.message);
      } else {
        console.log('Successfully dropped driver_name_3 column');
      }
    });
    db.run(`ALTER TABLE constructor_standings DROP COLUMN driver_name_2`, (err) => {
      if (err) {
        console.error('Error dropping driver_name_3 column:', err.message);
      } else {
        console.log('Successfully dropped driver_name_3 column');
      }
    });
    db.run(`ALTER TABLE constructor_standings DROP COLUMN driver_name_3`, (err) => {
      if (err) {
        console.error('Error dropping driver_name_3 column:', err.message);
      } else {
        console.log('Successfully dropped driver_name_3 column');
      }
    });
    
    db.run(`ALTER TABLE constructor_standings ADD COLUMN driver_id_1 INTEGER REFERENCES driver_standings(id)`, (err) => {
      if (err) {
        console.error('Error adding driver_id_1 column:', err.message);
      } else {
        console.log('Successfully added driver_id_1 column');
      }
    });
    
    db.run(`ALTER TABLE constructor_standings ADD COLUMN driver_id_2 INTEGER REFERENCES driver_standings(id)`, (err) => {
      if (err) {
        console.error('Error adding driver_id_2 column:', err.message);
      } else {
        console.log('Successfully added driver_id_2 column');
      }
    });
    
    db.run(`ALTER TABLE constructor_standings ADD COLUMN driver_id_3 INTEGER REFERENCES driver_standings(id)`, (err) => {
      if (err) {
        console.error('Error adding driver_id_3 column:', err.message);
      } else {
        console.log('Successfully added driver_id_3 column');
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
